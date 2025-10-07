# generators.py
import os
import base64
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
    "Форматируй строго без LaTeX. Обычный текст. "
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
    "5) Если задача про балки — задать Q(x) и M(x) по участкам (коротко, только нужные куски),\n"
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
    """
    Мэппинг пользовательского стиля из prefs.answer_style -> наш шаблон.
    """
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
        messages.extend(history)
    messages.append({"role": "user", "content": user_text})
    return messages

# ---------- Базовые генераторы ----------
async def stream_chat(
    messages: List[Dict[str, Any]],
    temperature: float = 0.4,
    priority: bool = False,
) -> AsyncIterator[str]:
    """
    priority=True — мягкий флаг для PRO: пробрасываем заголовок/метаданные.
    Сам по себе он не ускоряет API, но полезен для нашего роутинга/логирования.
    """
    extra = {}
    if priority:
        # безопасные «хинты» для собственного балансировщика/проксей
        extra = {"extra_headers": {"X-Queue": "priority", "X-Tier": "pro"},
                 "metadata": {"queue": "priority", "tier": "pro"}}

    stream = await client.chat.completions.create(
        model=TEXT_MODEL,
        messages=messages,
        temperature=temperature,
        stream=True,
        **extra,
    )
    async for chunk in stream:
        delta = (chunk.choices[0].delta.content or "")
        if delta:
            yield delta

async def stream_response_text(
    user_text: str,
    history: List[Dict[str, str]],
    *,
    template: AnswerTemplate = "default",
    teacher_mode: bool = False,
    priority: bool = False,
) -> AsyncIterator[str]:
    # Если инженерная задача — жёстче зажимаем температуру
    temp = 0.15 if _needs_engineering_mode(user_text) else 0.4
    messages = _build_messages(user_text, history, template=template, teacher_mode=teacher_mode)
    async for delta in stream_chat(messages, temperature=temp, priority=priority):
        yield delta

# Нестрриминговая версия с шаблоном/«учителем»
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

    extra = {}
    if priority:
        extra = {"extra_headers": {"X-Queue": "priority", "X-Tier": "pro"},
                 "metadata": {"queue": "priority", "tier": "pro"}}

    resp = await client.chat.completions.create(
        model=TEXT_MODEL,
        messages=messages,
        temperature=temperature,
        **extra,
    )
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

# ---------- Mini-quiz по уже сгенерированному ответу ----------
# Возвращает (markdown, сырой JSON со структурой)
async def quiz_from_answer(answer_text: str, n_questions: int = 4) -> Tuple[str, Dict[str, Any]]:
    """
    Синтезирует короткий тест (A/B/C/D) на основе разборa.
    Возвращает (markdown, data) — удобно и для кнопок, и для простого вывода.
    """
    system = (
        "Ты формируешь мини-тест по присланному объяснению. Строго проверяй соответствие фактам из текста."
    )
    user = (
        f"Сделай {n_questions} вопрос(а) множественного выбора по материалу ниже. "
        "На каждый вопрос — ровно 4 варианта (A–D), один правильный. "
        "Сначала дай JSON со структурой: "
        "{'questions':[{'q':'...','options':['A','B','C','D'],'correct':'A','why':'краткое объяснение'}]} "
        "Затем на новой строке выведи markdown-версию для Telegram c пронумерованными вопросами и вариантами."
        "\n\n=== Исходный разбор ===\n" + (answer_text or "")
    )
    resp = await client.chat.completions.create(
        model=TEXT_MODEL,
        messages=[{"role":"system","content":system},{"role":"user","content":user}],
        temperature=0.2,
    )
    raw = resp.choices[0].message.content or ""
    # Пытаемся аккуратно отделить JSON от markdown (ожидаем, что JSON идёт первым)
    import json, re
    json_obj: Dict[str, Any] = {"questions":[]}
    md = raw
    m = re.search(r"\{.*\}\s*", raw, re.DOTALL)
    if m:
        json_str = m.group(0)
        try:
            json_obj = json.loads(json_str.replace("'", '"'))
        except Exception:
            pass
        md = raw[m.end():].strip()
    return md, json_obj

# ---------- Картинки ----------
async def solve_from_image(image_bytes: bytes, hint: str, history: List[Dict[str, str]]) -> str:
    data_url = "data:image/jpeg;base64," + base64.b64encode(image_bytes).decode("utf-8")

    # усиливаем подсказку для картинок с инженерными схемами
    extra_eng = (
        "Если на изображении инженерная схема (балка/ферма/нагрузки/опоры): "
        "1) считать размеры/сектора/обозначения; 2) выписать ΣFy=0, ΣM=0; "
        "3) найти реакции ЧИСЛАМИ при наличии q, F, M, L; "
        "4) если данных мало — кратко спросить недостающее; "
        "5) итог с единицами. "
    )

    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_SCHOOL},
        {"role": "system", "content": SCHOOL_FORMAT_NOTE},
        {"role": "system", "content": ENGINEERING_RULES},  # подсобит распознаванию инженерных схем
    ]
    if history:
        messages.extend(history)
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
