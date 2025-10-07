# generators.py
import os
import base64
import json
import re
from typing import AsyncIterator, List, Dict, Any, Literal, Tuple, Optional

from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("OPENAI_API_KEY is not set")

base_url     = os.getenv("OPENAI_BASE_URL")  # опционально
TEXT_MODEL   = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
VISION_MODEL = os.getenv("OPENAI_VISION_MODEL", TEXT_MODEL)

client = AsyncOpenAI(api_key=api_key, base_url=base_url or None)

# --- Базовая системка (для всех предметов) ---
SYSTEM_SCHOOL = (
    "Ты — помощник-репетитор. Отвечай на русском, чётко и по делу. "
    "Поддерживаешь задачи от школы до ВУЗа: математика, физика, химия, "
    "инженерные дисциплины (сопромат/теормех/МС), гуманитарные, языки и т.д. "
    "Если данных не хватает для ответа — кратко напомни, чего не хватает, "
    "и не выдумывай отсутствующие числа."
)

# --- Формат по умолчанию (коротко, структурировано) ---
SCHOOL_FORMAT_NOTE = (
    "Форматируй строго обычным текстом (без LaTeX). "
    "Не используй \\( \\), \\[ \\], конструкции вида \\frac{..}{..}, ^{ }, _{ }. "
    "Если задача расчётная — показывай кратко ключевые шаги и финальные числа с единицами."
)

# --- Инженерный режим для сопромата / МС / статики ---
ENGINEERING_RULES = (
    "РЕЖИМ: ИНЖЕНЕРНЫЕ РАСЧЁТЫ (статика/балки/фермы/МС).\n"
    "Требования к ответу:\n"
    "1) Чётко распарсить исходные данные: тип опор/закреплений, элементы схемы, участки, приложенные нагрузки.\n"
    "2) Если чисел нет или не хватает — ДОСПРОСИ недостающие (например: q, F, координаты, M, L, EI и т.п.). "
    "   Не переходи к итогам без численных значений ключевых величин.\n"
    "3) Выписать уравнения равновесия (ΣFy=0, ΣMx=0) с обозначениями реакций. Указать выбранную точку для моментов.\n"
    "4) Найти реакции опор ЧИСЛАМИ. Привести подстановку и единицы (кН, кН·м, м и т.д.).\n"
    "5) Если задача про балки — задать Q(x) и M(x) по участкам (коротко, только нужные куски), "
    "   показать ключевые значения (экстремумы/границы участков) и финальные максимумы |Q|, |M|.\n"
    "6) Контроль: ΣFy≈0 и ΣM≈0 (с округлением).\n"
    "7) Итог: компактный список найденных величин с единицами. Никакой LaTeX.\n"
    "8) Если система статически неопределима — явно скажи степень неопределимости и какой метод нужен (метод сил/трёх моментов/канонические уравнения), "
    "   какие доп.параметры требуются (например EI), и что без них численно не решить.\n"
)

# --- Триггеры для включения инженерного режима ---
ENGINEERING_KEYWORDS = {
    "балка","ферма","опора","шарнир","защемление","реакция","реакции",
    "кн","кн/м","н/м","кн*м","кн·м","момент","изгибающий","поперечная сила",
    "диаграмма","q(","q=","f=","m=","ei","сопромат","статик","мс","прочность"
}

def _needs_engineering_mode(text: str) -> bool:
    t = (text or "").lower()
    return any(k in t for k in ENGINEERING_KEYWORDS)

# ---------- Профили/шаблоны ----------
AnswerTemplate = Literal["default", "conspect", "ege", "code_skeleton", "essay_outline"]

TEMPLATES: Dict[AnswerTemplate, str] = {
    "default": "",
    "conspect": (
        "Сформируй КОНСПЕКТ: блоки — Введение, Определения/формулы, Ключевые идеи, "
        "Примеры (минимум 2), Итог. Маркдауны и списки, без воды."
    ),
    "ege": (
        "Сделай РАЗБОР в стиле ЕГЭ: Условие (кратко), Что требуется, Решение по шагам, "
        "Проверка, Ответ. Если есть формулы — пиши словами и символами ASCII, без LaTeX."
    ),
    "code_skeleton": (
        "Выдай СКЕЛЕТ КОДА: краткий план функций/классов, заготовки, комментарии-шаблоны, "
        "минимальные тесты. Язык выбрать по контексту запроса."
    ),
    "essay_outline": (
        "Выдай ПЛАН РЕФЕРАТА/ЭССЕ: Тезисы, аргументы, источники (общие), "
        "структура: Введение — Основные разделы — Заключение."
    ),
}

TEACHER_MODE = (
    "Поясни максимально ПРОСТО, как учитель. Структура: 1) Интуиция/аналогия; "
    "2) Пошаговое решение; 3) Типичные ошибки; 4) Мини-проверка (3 коротких вопроса с ответами в конце блока)."
)

def style_to_template(style: str | None) -> AnswerTemplate:
    s = (style or "").lower()
    if s in {"conspect", "outline"}:
        return "conspect"
    if s in {"ege", "exam"}:
        return "ege"
    if s in {"code", "code_skeleton"}:
        return "code_skeleton"
    if s in {"essay", "essay_outline", "report"}:
        return "essay_outline"
    return "default"

# ---------- Вспомогалка: ужимаем историю (чтоб не плодить токены/мусор) ----------
def _compact_history(history: List[Dict[str, str]], max_items: int = 12) -> List[Dict[str, str]]:
    if not history:
        return []
    # оставляем последние max_items сообщений, чистим пустое
    h = [m for m in history if isinstance(m, dict) and m.get("role") in {"user","assistant"} and (m.get("content") or "").strip()]
    return h[-max_items:]

# ---------- Сборка messages ----------
def _build_messages(
    user_text: str,
    history: List[Dict[str, str]],
    template: AnswerTemplate = "default",
    teacher_mode: bool = False,
) -> List[Dict[str, Any]]:
    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_SCHOOL},
        {"role": "system", "content": SCHOOL_FORMAT_NOTE},
    ]
    if _needs_engineering_mode(user_text):
        messages.append({"role": "system", "content": ENGINEERING_RULES})
    if template != "default":
        messages.append({"role": "system", "content": TEMPLATES[template]})
    if teacher_mode:
        messages.append({"role": "system", "content": TEACHER_MODE})

    if history:
        messages.extend(_compact_history(history))
    messages.append({"role": "user", "content": user_text})
    return messages

# ---------- Базовые генераторы ----------
async def stream_chat(
    messages: List[Dict[str, Any]],
    temperature: float = 0.4,
    priority: bool = False,
) -> AsyncIterator[str]:
    """
    Стрим на chat.completions. Без metadata (чтобы не ловить 400).
    При падении — мягкий fallback на не-стрим.
    """
    kwargs: Dict[str, Any] = dict(model=TEXT_MODEL, messages=messages, temperature=temperature, stream=True)

    # Приоритетные заголовки можно оставить для своей очереди, но это просто HTTP-хедеры.
    if priority:
        kwargs["extra_headers"] = {"X-Queue": "priority", "X-Tier": "pro"}

    try:
        stream = await client.chat.completions.create(**kwargs)
        async for chunk in stream:
            delta = (chunk.choices[0].delta.content or "")
            if delta:
                yield delta
    except Exception:
        # fallback: одним куском
        resp = await client.chat.completions.create(
            model=TEXT_MODEL, messages=messages, temperature=temperature
        )
        text = resp.choices[0].message.content or ""
        if text:
            # режем на маленькие порции, чтобы интерфейс «оживал»
            for i in range(0, len(text), 200):
                yield text[i:i+200]

async def stream_response_text(
    user_text: str,
    history: List[Dict[str, str]],
    *,
    template: AnswerTemplate = "default",
    teacher_mode: bool = False,
    priority: bool = False,
) -> AsyncIterator[str]:
    temp = 0.15 if _needs_engineering_mode(user_text) else 0.4
    messages = _build_messages(user_text, history, template=template, teacher_mode=teacher_mode)
    async for delta in stream_chat(messages, temperature=temp, priority=priority):
        yield delta

async def generate_text(
    user_text: str,
    history: List[Dict[str, str]],
    template: AnswerTemplate = "default",
    teacher_mode: bool = False,
    temperature: Optional[float] = None,
    priority: bool = False,
) -> str:
    if temperature is None:
        temperature = 0.15 if _needs_engineering_mode(user_text) else 0.4
    messages = _build_messages(user_text, history, template=template, teacher_mode=teacher_mode)

    kwargs: Dict[str, Any] = dict(model=TEXT_MODEL, messages=messages, temperature=temperature)
    if priority:
        kwargs["extra_headers"] = {"X-Queue": "priority", "X-Tier": "pro"}

    resp = await client.chat.completions.create(**kwargs)
    return resp.choices[0].message.content or ""

# ---------- «Учитель объясняет» ----------
async def teacher_explain(user_text: str, history: List[Dict[str, str]], *, priority: bool = False) -> str:
    return await generate_text(user_text, history, template="default", teacher_mode=True, temperature=0.2, priority=priority)

# ---------- Шаблоны (конспект/ЕГЭ/код/эссе) ----------
async def generate_by_template(
    user_text: str,
    history: List[Dict[str, str]],
    template: AnswerTemplate,
    *,
    priority: bool = False,
) -> str:
    return await generate_text(user_text, history, template=template, teacher_mode=False, priority=priority)

# ---------- Безопасный парсер JSON из LLM ----------
_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
_FIRST_OBJ_RE  = re.compile(r"\{.*\}", re.DOTALL)

def _safe_load_json(text: str) -> Dict[str, Any]:
    """
    Достаём первый валидный JSON-объект:
    - пробуем fenced-блок ```json
    - иначе берём первую {...}
    - заменяем одинарные кавычки на двойные, убираем висячие запятые
    """
    if not text:
        return {}
    t = text.strip()

    m = _JSON_BLOCK_RE.search(t)
    if not m:
        m = _FIRST_OBJ_RE.search(t)
    if not m:
        return {}

    s = m.group(1) if m.lastindex else m.group(0)
    # грубая нормализация
    s = s.strip()
    # убираем комментарии в стиле // и /* */
    s = re.sub(r"//.*?$", "", s, flags=re.MULTILINE)
    s = re.sub(r"/\*.*?\*/", "", s, flags=re.DOTALL)
    # одиночные → двойные (осторожно)
    if "'" in s and '"' not in s:
        s = s.replace("'", '"')
    # висячие запятые перед закрывающей скобкой/квадратной
    s = re.sub(r",\s*([}\]])", r"\1", s)

    try:
        return json.loads(s)
    except Exception:
        # финальная попытка: удалить непечатаемые символы
        s2 = "".join(ch for ch in s if ord(ch) >= 32)
        try:
            return json.loads(s2)
        except Exception:
            return {}

# ---------- Mini-quiz по уже сгенерированному ответу ----------
# Возвращает (markdown, сырой JSON со структурой)
async def quiz_from_answer(answer_text: str, n_questions: int = 4) -> Tuple[str, Dict[str, Any]]:
    """
    Делаем короткий тест (A/B/C/D) на основе разбора.
    Возвращаем (md, data). md формируем САМИ: варианты — в столбик.
    """
    system = "Ты формируешь мини-тест по присланному объяснению. Строго проверяй соответствие фактам из текста."
    user = (
        f"Сделай {n_questions} вопрос(а) множественного выбора по материалу ниже. "
        "На каждый вопрос — ровно 4 варианта (A–D), один правильный. "
        "СНАЧАЛА верни ТОЛЬКО JSON вида: "
        "{\"questions\":[{\"q\":\"...\",\"options\":[\"A\",\"B\",\"C\",\"D\"],\"correct\":\"A\",\"why\":\"краткое объяснение\"}]}"
        " Без пояснений и текста после JSON.\n\n"
        "=== Исходный разбор ===\n" + (answer_text or "")
    )
    resp = await client.chat.completions.create(
        model=TEXT_MODEL,
        messages=[{"role":"system","content":system},{"role":"user","content":user}],
        temperature=0.2,
    )
    raw = resp.choices[0].message.content or ""

    data = _safe_load_json(raw)
    if not isinstance(data, dict):
        data = {}
    questions = data.get("questions") or []

    # санитизация структуры
    fixed_questions = []
    for q in questions:
        qtext = str(q.get("q","")).strip()
        opts  = list(q.get("options") or [])
        # выравниваем до 4
        opts = (opts + ["—"]*4)[:4]
        corr = str(q.get("correct","A")).strip().upper()[:1]
        if corr not in {"A","B","C","D"}:
            corr = "A"
        why  = str(q.get("why","")).strip()
        fixed_questions.append({"q": qtext, "options": opts, "correct": corr, "why": why})

    data = {"questions": fixed_questions}

    # --- формируем markdown сами: варианты в столбик ---
    lines: List[str] = ["🧠 Мини-тест"]
    ABCD = ["A","B","C","D"]
    total = len(fixed_questions)
    for i, q in enumerate(fixed_questions, 1):
        lines.append(f"\nВопрос {i}/{total}:\n{q['q']}")
        for j, label in enumerate(ABCD):
            lines.append(f"{label}) {q['options'][j]}")
    md = "\n".join(lines).strip()

    return md, data

# ---------- Картинки ----------
async def solve_from_image(image_bytes: bytes, hint: str, history: List[Dict[str, str]]) -> str:
    """
    Вижн-разбор: аккуратно подсовываем картинку и текст-подсказку.
    Автовключаем инженерный режим через ENGINEERING_RULES, чтобы раскладывал балки/реакции.
    """
    data_url = "data:image/jpeg;base64," + base64.b64encode(image_bytes).decode("utf-8")

    extra_eng = (
        "Если на изображении инженерная схема (балка/ферма/нагрузки/опоры): "
        "1) распознай размеры/обозначения; 2) выпиши ΣFy=0, ΣM=0; "
        "3) найди реакции ЧИСЛАМИ при наличии q, F, M, L; "
        "4) если данных мало — кратко спроси недостающее; "
        "5) итог с единицами. "
    )

    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_SCHOOL},
        {"role": "system", "content": SCHOOL_FORMAT_NOTE},
        {"role": "system", "content": ENGINEERING_RULES},
    ]
    if history:
        messages.extend(_compact_history(history))
    messages.append({
        "role": "user",
        "content": [
            {"type": "text", "text": (hint or "Распознай условие и реши по шагам.") + " " + extra_eng},
            {"type": "image_url", "image_url": {"url": data_url}},
        ],
    })

    resp = await client.chat.completions.create(
        model=VISION_MODEL,
        messages=messages,
        temperature=0.15,
    )
    return resp.choices[0].message.content or ""
