# generators.py
import os
import base64
from typing import AsyncIterator, List, Dict, Any

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
    "диаграмма","q(","q=","F=","M=","EI","сопромат","статик","МС","прочность"
}

def _needs_engineering_mode(text: str) -> bool:
    t = (text or "").lower()
    return any(k in t for k in ENGINEERING_KEYWORDS)

def _build_messages(user_text: str, history: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_SCHOOL},
        {"role": "system", "content": SCHOOL_FORMAT_NOTE},
    ]
    if _needs_engineering_mode(user_text):
        messages.append({"role": "system", "content": ENGINEERING_RULES})
        # для инженерных задач делаем модель «построже»
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_text})
    return messages

async def stream_chat(messages: List[Dict[str, Any]], temperature: float = 0.4) -> AsyncIterator[str]:
    stream = await client.chat.completions.create(
        model=TEXT_MODEL,
        messages=messages,
        temperature=temperature,
        stream=True,
    )
    async for chunk in stream:
        delta = (chunk.choices[0].delta.content or "")
        if delta:
            yield delta

async def stream_response_text(user_text: str, history: List[Dict[str, str]]) -> AsyncIterator[str]:
    # Если инженерная задача — жёстче зажимаем температуру
    temp = 0.15 if _needs_engineering_mode(user_text) else 0.4
    messages = _build_messages(user_text, history)
    async for delta in stream_chat(messages, temperature=temp):
        yield delta

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
