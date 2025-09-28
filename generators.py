# generators.py
import os
import base64
from typing import AsyncIterator, List, Dict, Any

from openai import AsyncOpenAI
from dotenv import load_dotenv

# -----------------------------------------------------------------------------
# init
# -----------------------------------------------------------------------------
load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("OPENAI_API_KEY is not set")

base_url       = os.getenv("OPENAI_BASE_URL")  # можно не указывать
TEXT_MODEL     = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
VISION_MODEL   = os.getenv("OPENAI_VISION_MODEL", TEXT_MODEL)   # для OCR можно поставить "gpt-4o"
MAX_TOKENS_ENV = int(os.getenv("OPENAI_MAX_TOKENS", "900"))     # ограничим длину ответа

client = AsyncOpenAI(api_key=api_key, base_url=base_url or None)

# -----------------------------------------------------------------------------
# системные инструкции (жёсткие, всегда добавляются)
# -----------------------------------------------------------------------------
SYSTEM_SCHOOL = (
    "Ты — школьный помощник-репетитор. Всегда отвечай на русском. "
    "Работай по всем школьным предметам: математика, физика, химия, биология, география, история, обществознание, "
    "русский язык, литература, информатика, английский (переводы/объяснения по-русски), а также проекты/рефераты. "
    "Правила:\n"
    "1) Отвечай кратко и по шагам, без воды. При необходимости структурируй в пункты.\n"
    "2) В задачах по точным наукам показывай: краткую запись (ДАНО/НАЙТИ), формулы, подстановку, вычисления с единицами, "
    "проверку размерностей (если уместно) и в конце 'ИТОГ: ...' одной строкой.\n"
    "3) Если данных не хватает — явно укажи каких и предложи разумные предположения; не выдумывай факты.\n"
    "4) По русскому и литературе: дай тезисный план, подбери аргументы, анализируй средства выразительности и композицию; "
    "сочинение пиши логично и без плагиата.\n"
    "5) По гуманитарным предметам: чёткие определения, краткие сравнения, хронология (если нужна), ключевые мысли.\n"
)

# Строгий формат под Telegram (без LaTeX)
SCHOOL_FORMAT_NOTE = (
    "Форматируй строго без LaTeX/TeX (никаких $, \\, \\( \\), \\frac и т.п.). "
    "Используй обычные символы и единицы СИ. Дроби — через '/', умножение — '*', степень — '^'.\n"
    "Рекомендуемый шаблон для задач:\n"
    "ДАНО:\n- ...\nНАЙТИ:\n- ...\nФОРМУЛЫ:\n- ...\nРЕШЕНИЕ:\n- ...\nПОДСТАНОВКА:\n- ...\nИТОГ: ...\n"
    "Для сочинений: сначала короткий план (3–5 пунктов), затем связный текст на 8–12 предложений."
)

# -----------------------------------------------------------------------------
# helpers
# -----------------------------------------------------------------------------
async def _chat_stream(messages: List[Dict[str, Any]], *, model: str) -> AsyncIterator[str]:
    """
    Общий стример для chat.completions с фолбэком модели.
    """
    try:
        stream = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.4,
            max_tokens=MAX_TOKENS_ENV,
            stream=True,
        )
    except Exception:
        # Фолбэк на gpt-4o-mini, если указанная модель недоступна
        fb = "gpt-4o-mini"
        stream = await client.chat.completions.create(
            model=fb,
            messages=messages,
            temperature=0.4,
            max_tokens=MAX_TOKENS_ENV,
            stream=True,
        )

    async for chunk in stream:
        delta = (chunk.choices[0].delta.content or "")
        if delta:
            yield delta

# -----------------------------------------------------------------------------
# public API
# -----------------------------------------------------------------------------
async def stream_response_text(user_text: str, history: List[Dict[str, str]]) -> AsyncIterator[str]:
    """
    Стриминг ответа с учётом истории. Всегда включает SYSTEM_SCHOOL + SCHOOL_FORMAT_NOTE.
    """
    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_SCHOOL},
        {"role": "system", "content": SCHOOL_FORMAT_NOTE},
    ]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_text})

    async for delta in _chat_stream(messages, model=TEXT_MODEL):
        yield delta


async def solve_from_image(image_bytes: bytes, hint: str, history: List[Dict[str, str]]) -> str:
    """
    Решение задачи с изображения (мультимодальный chat.completions).
    Передаём картинку как data-url в image_url.
    """
    data_url = "data:image/jpeg;base64," + base64.b64encode(image_bytes).decode("utf-8")

    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_SCHOOL},
        {"role": "system", "content": SCHOOL_FORMAT_NOTE},
    ]
    if history:
        messages.extend(history)
    messages.append({
        "role": "user",
        "content": [
            {"type": "text", "text": hint or "Распознай условие с фото и реши задачу по шагам в указанном формате."},
            {"type": "image_url", "image_url": {"url": data_url}},
        ],
    })

    try:
        resp = await client.chat.completions.create(
            model=VISION_MODEL,
            messages=messages,
            temperature=0.3,
            max_tokens=MAX_TOKENS_ENV,
        )
    except Exception:
        # фолбэк на 4o-mini
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.3,
            max_tokens=MAX_TOKENS_ENV,
        )

    return resp.choices[0].message.content or ""
