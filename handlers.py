import os
import json
import asyncio
import time
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote_plus, urlencode, urlparse, parse_qsl, urlunparse

from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardRemove,
    BufferedInputFile,
    InputMediaPhoto,
)
from aiogram.filters import CommandStart, StateFilter, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.exceptions import TelegramRetryAfter, TelegramBadRequest
from aiogram.enums import ChatAction, ParseMode
from aiogram.utils.keyboard import InlineKeyboardBuilder

from generators import stream_response_text, solve_from_image, quiz_from_answer
from db import (
    ensure_user, can_use, inc_usage, get_status_text,
    get_all_chat_ids, drop_chat, set_optin,
    get_prefs, get_pref_bool, set_pref,
    get_voice_settings, set_voice_settings,
    is_teacher_mode, set_teacher_mode,
    get_priority, set_priority,
    get_answer_style, set_answer_style,
    add_history, get_history, clear_history,
    remember_bookmark, forget_last_bookmark, get_last_bookmark,
    get_or_create_ref_code, get_referral_stats,
    find_user_by_ref_code, set_referrer_once,
    apply_promocode_access,
    payment_create, payment_set_status,
)

from payshark_client import PaysharkClient, build_external_id

from utils_export import pdf_from_answer_text
from tts import tts_voice_ogg, split_for_tts

router = Router()

COOLDOWN_SECONDS = 5
MIN_INTERVAL_SEND = 1.1
MIN_EDIT_INTERVAL = 0.25
MAX_TG_LEN = 4096

LITE_PRICE = (os.getenv("PAYSHARK_LITE_PRICE") or os.getenv("LITE_PRICE_RUB") or os.getenv("LITE_PRICE") or os.getenv("TRIBUTE_LITE_PRICE") or "199.99").strip()
PRO_PRICE = (os.getenv("PAYSHARK_PRO_PRICE") or os.getenv("PRO_PRICE_RUB") or os.getenv("PRO_PRICE") or os.getenv("TRIBUTE_PRO_PRICE") or "299.99").strip()
PAYSHARK_LITE_URL = os.getenv("PAYSHARK_LITE_URL", "").strip()
PAYSHARK_PRO_URL = os.getenv("PAYSHARK_PRO_URL", "").strip()
PAYSHARK_CURRENCY = (os.getenv("PAYSHARK_CURRENCY") or "RUB").strip() or "RUB"
PUBLIC_BASE_URL = (os.getenv("PUBLIC_BASE_URL") or "").strip().rstrip("/")
SUPPORT_CONTACT = os.getenv("SUPPORT_CONTACT", "@gptEDU_support").strip() or "@gptEDU_support"
PROMO_CODE = os.getenv("PROMO_CODE", "uStudyPromoTest").strip()
PROMO_PRO_DAYS = int(os.getenv("PROMO_PRO_DAYS", "365"))


BOT_USERNAME = os.getenv("BOT_USERNAME", "your_bot").lstrip("@")
REF_BONUS_THRESHOLD = int(os.getenv("REF_BONUS_THRESHOLD", "6"))

TTS_ENABLED_DEFAULT_PRO = False
TTS_CHUNK_LIMIT = 2500

# ----------------- ЯЗЫК / I18N -----------------

LANGUAGES: Dict[str, str] = {
    "ru": "Русский",
    "en": "English",
    "uz": "Oʻzbek",
    "kk": "Қазақша",
    "de": "Deutsch",
    "fr": "Français",
    "es": "Español",
    "tr": "Türkçe",
    "ar": "العربية",
    "hi": "हिन्दी",
}

LANG_BUTTONS: Dict[str, str] = {
    "🇷🇺 Русский": "ru",
    "🇬🇧 English": "en",
    "🇺🇿 Oʻzbek": "uz",
    "🇰🇿 Қазақша": "kk",
    "🇩🇪 Deutsch": "de",
    "🇫🇷 Français": "fr",
    "🇪🇸 Español": "es",
    "🇹🇷 Türkçe": "tr",
    "🇦🇪 العربية": "ar",
    "🇮🇳 हिन्दी": "hi",
}

LANGUAGE_HINTS: Dict[str, str] = {
    "ru": "Всегда отвечай пользователю только на русском языке, если он явно не просит другой язык.",
    "en": "Always respond to the user only in English unless they explicitly ask for another language.",
    "uz": "Always respond to the user only in Uzbek unless they explicitly ask for another language.",
    "kk": "Always respond to the user only in Kazakh unless they explicitly ask for another language.",
    "de": "Always respond to the user only in German unless they explicitly ask for another language.",
    "fr": "Always respond to the user only in French unless they explicitly ask for another language.",
    "es": "Always respond to the user only in Spanish unless they explicitly ask for another language.",
    "tr": "Always respond to the user only in Turkish unless they explicitly ask for another language.",
    "ar": "Always respond to the user only in Arabic unless they explicitly ask for another language.",
    "hi": "Always respond to the user only in Hindi unless they explicitly ask for another language.",
}

DEFAULT_LANG = "ru"

LANG_SELECT_KB = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="🇷🇺 Русский"),
            KeyboardButton(text="🇬🇧 English"),
        ],
        [
            KeyboardButton(text="🇺🇿 Oʻzbek"),
            KeyboardButton(text="🇰🇿 Қазақша"),
        ],
        [
            KeyboardButton(text="🇩🇪 Deutsch"),
            KeyboardButton(text="🇫🇷 Français"),
        ],
        [
            KeyboardButton(text="🇪🇸 Español"),
            KeyboardButton(text="🇹🇷 Türkçe"),
        ],
        [
            KeyboardButton(text="🇦🇪 العربية"),
            KeyboardButton(text="🇮🇳 हिन्दी"),
        ],
    ],
    resize_keyboard=True,
    is_persistent=True,
    input_field_placeholder="🌐 Choose language / Выберите язык…",
)

async def get_user_lang(chat_id: int) -> str:
    prefs = await get_prefs(chat_id)
    lang = (prefs or {}).get("lang")
    if isinstance(lang, str) and lang in LANGUAGES:
        return lang
    return DEFAULT_LANG

async def ensure_language_selected(message: Message) -> Optional[str]:
    """
    Проверяем, выбран ли язык. Если нет — просим выбрать и НЕ продолжаем обработку.
    """
    prefs = await get_prefs(message.chat.id)
    lang = (prefs or {}).get("lang")
    if isinstance(lang, str) and lang in LANGUAGES:
        return lang
    await message.answer(
        "🌐 Выберите язык бота (интерфейс + ответы).\n"
        "Choose the bot language (interface + answers).",
        reply_markup=LANG_SELECT_KB,
    )
    return None

def build_greeting(lang: str, is_free: bool, mode_title: str) -> str:
    if lang == "en":
        return (
            "👋 Hi! I'm a study assistant for school and university.\n\n"
            "What I can do:\n"
            "• Solve problems step by step (math, physics, etc.)\n"
            "• Explain theory in simple words\n"
            "• Write essays, outlines and reports\n"
            "• Help with code and formatting of solutions\n"
            "• Understand photos/screenshots of tasks 📷\n\n"
            "How to start:\n"
            "— Send a photo of the task or describe it in text.\n"
            "— Need help? Tap “FAQ / Help”.\n"
            f"— {'Upgrade plan — button below.' if is_free else 'Access status — “🧾 My subscriptions”.'}\n"
            "— 🎁 Friends bonus: invite friends and get PRO.\n\n"
            f"Current bot mode: {mode_title}\n"
            "You can change it in ⚙️ Settings → 🎛 Bot mode."
        )
    # default Russian
    return (
        "👋 Привет! Я — учебный помощник для школы и вузов.\n\n"
        "Что я умею:\n"
        "• Разбирать задачи по шагам (математика, физика и др.)\n"
        "• Пояснять теорию простым языком\n"
        "• Писать сочинения, эссе, конспекты, рефераты\n"
        "• Помогать с кодом и оформлением решений\n"
        "• Понимать фото/скриншоты задач 📷\n\n"
        "Как начать:\n"
        "— Пришли фото задачи или напиши текстом, что нужно.\n"
        "— Нужна справка — жми «FAQ / Помощь».\n"
        f"— {'Обновить план — кнопка ниже.' if is_free else 'Статус доступа — «🧾 Мои подписки».'}\n"
        "— 🎁 Бонус за друзей: пригласи друзей и получай PRO.\n\n"
        f"Текущий тип работы бота: {mode_title}\n"
        "Изменить можно в ⚙️ Настройки → 🎛 Тип работы бота."
    )

# ----------------- РЕЖИМЫ БОТА -----------------

BOT_MODES: Dict[str, Dict[str, str]] = {
    "default": {
        "title": "👨‍🏫 Нормальный учитель",
        "description": "Классический режим: структурные объяснения, примеры и аккуратный разбор задач.",
        "prompt": "",
    },
    "simple": {
        "title": "🧸 Объяснять по-простому",
        "description": "Объяснения максимально простым языком, с аналогиями из жизни и короткими пояснениями.",
        "prompt": (
            "Объясняй материал максимально простым и понятным языком, как для 10-летнего ребёнка. "
            "Избегай сложной терминологии, используй аналогии из повседневной жизни и короткие предложения. "
            "Если тема сложная, сначала дай интуитивное объяснение, а затем можешь добавить чуть больше деталей."
        ),
    },
    "coach": {
        "title": "🎯 Коучинг вопросами",
        "description": "Не даёт готовое решение сразу, а ведёт ученика вопросами и подсказками.",
        "prompt": (
            "Работай в коучинговом сократическом режиме. Не давай сразу готовое решение. "
            "Разбей задачу на шаги и в ответе сначала задай 2–4 наводящих вопроса, которые помогут пользователю "
            "самому продвинуться. При необходимости можно добавить короткие подсказки, но полный разбор решения "
            "оставь на отдельный явный запрос пользователя."
        ),
    },
    "exam": {
        "title": "📝 Экзаменатор",
        "description": "Фокус на проверочных вопросах и оценке знаний, а не на длинных лекциях.",
        "prompt": (
            "Работай как экзаменатор. По запросу формируй 3–7 проверочных вопросов по теме, чтобы оценить знания "
            "пользователя. Сначала выдай вопросы без подробных решений. К каждому вопросу можно дать очень короткий "
            "комментарий. Полные разборы и решения показывай только по отдельному запросу."
        ),
    },
    "solve_full": {
        "title": "📐 Решение задач с объяснением",
        "description": "Полный разбор задач: переписать условие, план решения, шаги и итог.",
        "prompt": (
            "Если запрос похож на задачу, сначала коротко перепиши условие своими словами, затем обозначь план решения "
            "(1–3 шага), после этого реши по шагам с пояснениями и в конце подведи итог, почему результат логичен. "
            "Если запрос не является задачей, отвечай как обычно, но по возможности тоже структурировано."
        ),
    },
    "hint": {
        "title": "💡 Только подсказки",
        "description": "Делает упор на намёки и направление мысли, без полного решения.",
        "prompt": (
            "Давай только подсказки к решению задачи, а не полное решение. В ответе укажи 2–4 шага-намёка: "
            "какие понятия вспомнить, какую формулу применить, какие величины найти. Не пиши окончательный ответ, "
            "пока пользователь явно не попросит показать полное решение."
        ),
    },
    "check": {
        "title": "✅ Проверка моего решения",
        "description": "Проверяет уже сделанное решение ученика, показывает ошибки и улучшения.",
        "prompt": (
            "Считай, что пользователь присылает своё решение задачи. Не решай задачу с нуля. "
            "Сначала оцени, верен ли итоговый ответ, затем покажи, на каких шагах есть ошибки или сомнительные места. "
            "Предложи улучшенную или исправленную версию решения и дай 1–2 совета, как в будущем избегать таких ошибок."
        ),
    },
    "notes": {
        "title": "📓 Конспект по теме",
        "description": "Преобразует запрос в структурированный учебный конспект.",
        "prompt": (
            "Преобразуй запрос пользователя в структурированный учебный конспект. "
            "Структура: краткое введение, основные определения и формулы, ключевые идеи, "
            "2–3 типовых примера и небольшой блок вопросов для самопроверки в конце."
        ),
    },
    "test": {
        "title": "🧪 Генератор тестов",
        "description": "Создаёт небольшой тест по теме с ответами и разбором.",
        "prompt": (
            "Сгенерируй небольшой учебный тест по теме из запроса. Сделай 5–10 вопросов разных типов "
            "(выбор ответа, краткий ответ). В первой части ответа перечисли вопросы без ответов, "
            "а во второй части перечисли правильные ответы и краткий разбор по каждому вопросу."
        ),
    },
    "cards": {
        "title": "🎴 Карточки по теме",
        "description": "Делает набор учебных flashcards: вопрос/ответ.",
        "prompt": (
            "Сделай набор учебных карточек (flashcards) по теме из запроса. "
            "Для каждой карточки укажи: сторона A — вопрос или термин, сторона B — краткое объяснение, формула или ответ. "
            "Сделай 8–20 карточек, если явно не указано другое количество."
        ),
    },
    "cheatsheet": {
        "title": "📌 Шпаргалка",
        "description": "Максимально компактная шпаргалка: формулы и ключевые тезисы.",
        "prompt": (
            "Сделай максимально компактную шпаргалку по теме из запроса. "
            "Только ключевые формулы, определения и 3–7 самых важных тезисов. Без лишней воды."
        ),
    },
    "mindmap": {
        "title": "🧠 Mind-map по теме",
        "description": "Строит текстовую mind-map: тема → ветки → подветки.",
        "prompt": (
            "Построй текстовую mind-map по теме из запроса. "
            "Сначала укажи центральную тему, затем ветки первого уровня с подветками. "
            "Используй вложенные маркеры, чтобы было понятно, что к чему относится."
        ),
    },
    "study_plan": {
        "title": "📅 Учебный план по теме",
        "description": "Составляет персональный учебный план по теме.",
        "prompt": (
            "Составь персональный учебный план по теме из запроса. "
            "Если явно не указаны сроки и доступное время, сделай разумные предположения и обозначь их в начале ответа. "
            "Разбей план по дням или неделям, укажи, что изучать, какие задачи решать и как проверять прогресс."
        ),
    },
}

MODE_BUTTON_TEXT_TO_KEY: Dict[str, str] = {
    "👨‍🏫 Нормальный учитель": "default",
    "🧸 Объяснять по-простому": "simple",
    "🎯 Коучинг вопросами": "coach",
    "📝 Экзаменатор": "exam",
    "📐 Решение задач с объяснением": "solve_full",
    "💡 Только подсказки": "hint",
    "✅ Проверка моего решения": "check",
    "📓 Конспект по теме": "notes",
    "🧪 Генератор тестов": "test",
    "🎴 Карточки по теме": "cards",
    "📌 Шпаргалка": "cheatsheet",
    "🧠 Mind-map по теме": "mindmap",
    "📅 Учебный план по теме": "study_plan",
}

def _inject_query(url: str, extra: Dict[str, str]) -> str:
    try:
        u = urlparse(url)
        q = dict(parse_qsl(u.query, keep_blank_values=True))
        for k, v in (extra or {}).items():
            if v is None:
                continue
            vv = str(v).strip()
            if vv == "":
                continue
            q[k] = vv
        nq = urlencode(q)
        return urlunparse((u.scheme, u.netloc, u.path, u.params, nq, u.fragment))
    except Exception:
        return url

def payshark_plan_url(plan: str, chat_id: int, username: Optional[str]) -> str:
    base = PAYSHARK_LITE_URL if plan == "lite" else PAYSHARK_PRO_URL
    if not base:
        return ""
    base = base.replace("{chat_id}", str(chat_id)).replace("{user_id}", str(chat_id)).replace("{client_id}", str(chat_id)).replace("{plan}", plan)
    base = base.replace("{username}", (username or ""))
    return _inject_query(base, {"chat_id": str(chat_id), "client_id": str(chat_id), "plan": plan, "username": username or ""})


def _as_float_price(value: str) -> float:
    s = (value or "").strip().replace(",", ".")
    try:
        return float(s)
    except Exception:
        return 0.0


def _normalize_currency(cur: str) -> str:
    import re

    cur = (cur or "").upper().strip()
    m = re.search(r"[A-Z]{3}", cur)
    code = m.group(0) if m else ""
    allowed = {"RUB", "RUR", "USD", "EUR", "KZT", "UZS"}
    return code if code in allowed else "RUB"


def _format_payment_detail(detail: Any) -> str:
    """Pretty-format payment_detail from H2H response (string/dict/list/etc)."""
    if detail is None:
        return ""
    if isinstance(detail, str):
        return detail.strip()
    if isinstance(detail, (int, float, bool)):
        return str(detail)
    if isinstance(detail, list):
        parts: List[str] = []
        for it in detail:
            s = _format_payment_detail(it)
            if s:
                parts.append(s)
        return "\n".join(parts)
    if isinstance(detail, dict):
        lines: List[str] = []
        for k, v in detail.items():
            if v is None:
                continue
            kk = str(k).strip()
            vv = v
            if isinstance(v, (dict, list)):
                vv = json.dumps(v, ensure_ascii=False)
            vv_s = str(vv).strip()
            if not vv_s:
                continue
            if kk:
                lines.append(f"• {kk}: {vv_s}")
            else:
                lines.append(f"• {vv_s}")
        return "\n".join(lines)
    return str(detail)

async def get_current_mode(chat_id: int) -> str:
    prefs = await get_prefs(chat_id)
    mode = (prefs or {}).get("mode")
    if mode in BOT_MODES:
        return mode
    return "default"

async def set_current_mode(chat_id: int, mode: str) -> None:
    key = mode if mode in BOT_MODES else "default"
    await set_pref(chat_id, "mode", key)

async def apply_mode_to_text(chat_id: int, text: str) -> str:
    """
    Добавляем к запросу промпт выбранного режима И языковой хинт.
    """
    mode = await get_current_mode(chat_id)
    cfg = BOT_MODES.get(mode) or BOT_MODES["default"]
    prompt = cfg.get("prompt") or ""
    lang = await get_user_lang(chat_id)
    lang_hint = LANGUAGE_HINTS.get(lang, "")
    parts: List[str] = []
    if lang_hint:
        parts.append(lang_hint)
    if prompt:
        parts.append(prompt)
    if not parts:
        return text
    return "\n\n".join(parts) + "\n\n" + text

async def _plan_flags(chat_id: int) -> Tuple[bool, bool, bool]:
    t = (await get_status_text(chat_id)).lower()
    return ("план: free" in t, "план: lite" in t, "план: pro" in t)

def plans_kb(show_back: bool = False) -> InlineKeyboardMarkup:
    row = [
        InlineKeyboardButton(text=f"🪙 LITE {LITE_PRICE} ₽", callback_data="pay_lite"),
        InlineKeyboardButton(text=f"🚀 PRO {PRO_PRICE} ₽", callback_data="pay_pro"),
    ]
    kb: list[list[InlineKeyboardButton]] = [row]
    if show_back:
        kb.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_subs")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def available_btn_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="📦 Доступные пакеты", callback_data="show_plans")]]
    )

def answer_actions_kb(is_pro: bool) -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = [[]]
    if is_pro:
        rows[0].append(InlineKeyboardButton(text="🎙 Озвучить", callback_data="tts_say"))
        rows[0].append(InlineKeyboardButton(text="📄 PDF", callback_data="export_pdf"))
        rows[0].append(InlineKeyboardButton(text="🧠 Проверить себя", callback_data="quiz_make"))
    else:
        rows[0].append(InlineKeyboardButton(text="🔒 PDF (PRO)", callback_data="need_pro_pdf"))
        rows[0].append(InlineKeyboardButton(text="🔒 Проверить себя (PRO)", callback_data="need_pro_quiz"))
    return InlineKeyboardMarkup(inline_keyboard=rows)

def main_kb_for_plan(is_free: bool) -> ReplyKeyboardMarkup:
    if is_free:
        keyboard = [
            [KeyboardButton(text="🔼 Обновить план"), KeyboardButton(text="FAQ / Помощь")],
            [KeyboardButton(text="⚙️ Настройки"), KeyboardButton(text="🎁 Бонус за друзей")],
        ]
    else:
        keyboard = [
            [KeyboardButton(text="🧾 Мои подписки"), KeyboardButton(text="FAQ / Помощь")],
            [KeyboardButton(text="⚙️ Настройки"), KeyboardButton(text="🎁 Бонус за друзей")],
        ]
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Напишите вопрос или пришлите фото… / Type a question or send a photo…",
    )

SETTINGS_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🔔 Включить авто-озвучку"), KeyboardButton(text="🔕 Выключить авто-озвучку")],
        [KeyboardButton(text="👩‍🏫 Включить режим Учителя"), KeyboardButton(text="👨‍🎓 Выключить режим Учителя")],
        [KeyboardButton(text="🧹 Сброс контекста")],
        [KeyboardButton(text="🎛 Тип работы бота")],
        [KeyboardButton(text="🌐 Язык бота")],
        [KeyboardButton(text="◀️ Назад в меню")],
    ],
    resize_keyboard=True,
)

MODE_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="👨‍🏫 Нормальный учитель"), KeyboardButton(text="🧸 Объяснять по-простому")],
        [KeyboardButton(text="🎯 Коучинг вопросами"), KeyboardButton(text="📝 Экзаменатор")],
        [KeyboardButton(text="📐 Решение задач с объяснением"), KeyboardButton(text="💡 Только подсказки")],
        [KeyboardButton(text="✅ Проверка моего решения"), KeyboardButton(text="📓 Конспект по теме")],
        [KeyboardButton(text="🧪 Генератор тестов"), KeyboardButton(text="🎴 Карточки по теме")],
        [KeyboardButton(text="📌 Шпаргалка"), KeyboardButton(text="🧠 Mind-map по теме")],
        [KeyboardButton(text="📅 Учебный план по теме")],
        [KeyboardButton(text="◀️ Назад в настройки")],
    ],
    resize_keyboard=True,
)

_last_send_ts: Dict[int, float] = {}
_next_allowed_by_chat: Dict[int, float] = {}
_export_lock: Dict[int, float] = {}
QUIZ_STATE: Dict[int, Dict] = {}

async def _is_pro(chat_id: int) -> bool:
    _, _, pro = await _plan_flags(chat_id)
    return pro

async def _is_free(chat_id: int) -> bool:
    free, _, _ = await _plan_flags(chat_id)
    return free

async def _last_assistant_text(chat_id: int) -> Optional[str]:
    hist = await get_history(chat_id)
    for item in reversed(hist):
        if item.get("role") == "assistant":
            return item.get("content") or ""
    return None

def _ref_link_from_code(code: str) -> str:
    return f"https://t.me/{BOT_USERNAME}?start=ref_{code}"

def _share_button(link: str, caption: str) -> InlineKeyboardButton:
    share_url = f"https://t.me/share/url?url={quote_plus(link)}&text={quote_plus(caption)}"
    return InlineKeyboardButton(text="📤 Поделиться", url=share_url)

async def _send_referral_card(message: Message):
    stats = await get_referral_stats(message.chat.id)
    code = stats.get("ref_code") or await get_or_create_ref_code(message.chat.id)
    link = _ref_link_from_code(code)
    paid = int(stats.get("referred_paid_count") or 0)
    total = int(stats.get("referred_count") or 0)
    threshold = globals().get("REF_BONUS_THRESHOLD", int(os.getenv("REF_BONUS_THRESHOLD", "6")))
    progress = paid % threshold
    left = max(0, threshold - progress)
    meter = "█" * progress + "—" * (threshold - progress)
    text = (
        "🎁 <b>Бонус за друзей</b>\n\n"
        f"Приглашай друзей по персональной ссылке.\n"
        f"За каждые <b>{threshold}</b> покупок (LITE/PRO) по твоей ссылке — <b>+1 месяц PRO</b>.\n\n"
        f"🔗 <b>Твоя ссылка:</b>\n<code>{link}</code>\n\n"
        f"📊 <b>Статистика</b>\n"
        f"— Всего приглашено: <b>{total}</b>\n"
        f"— Купили подписку: <b>{paid}</b>\n"
        f"— Прогресс до подарка: [{meter}] {progress}/{threshold}\n"
        f"— До следующего подарка: <b>{left}</b>\n\n"
        "Поделись ссылкой с одногруппниками, в чатах курса или друзьям 👇"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🔗 Открыть ссылку", url=link),
        _share_button(link, "Помощник для учёбы — моя реф. ссылка:")
    ]])
    await message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)

async def _respect_rate_limit(chat_id: int):
    now = time.monotonic()
    last = _last_send_ts.get(chat_id, 0.0)
    wait = last + MIN_INTERVAL_SEND - now
    if wait > 0:
        await asyncio.sleep(wait)
    _last_send_ts[chat_id] = time.monotonic()

async def safe_send(message: Message, text: str, **kwargs):
    await _respect_rate_limit(message.chat.id)
    try:
        return await message.answer(text, **kwargs)
    except TelegramRetryAfter as e:
        await asyncio.sleep(e.retry_after + 1)
        await _respect_rate_limit(message.chat.id)
        return await message.answer(text, **kwargs)
    except TelegramBadRequest as e:
        if "too many requests" in str(e).lower() or "flood control exceeded" in str(e).lower():
            await asyncio.sleep(2)
            await _respect_rate_limit(message.chat.id)
            return await message.answer(text, **kwargs)
        raise

async def safe_edit(message: Message, message_id: int, text: str, reply_markup: Optional[InlineKeyboardMarkup] = None):
    try:
        await message.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=message_id,
            text=text,
            reply_markup=reply_markup
        )
    except TelegramBadRequest as e:
        low = str(e).lower()
        if "message is not modified" in low:
            return
        if "too many requests" in low or "flood control exceeded" in low:
            await asyncio.sleep(1)
            try:
                await message.bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=message_id,
                    text=text,
                    reply_markup=reply_markup
                )
            except Exception:
                pass

async def safe_delete(msg):
    try:
        await msg.delete()
    except Exception:
        pass

async def show_cooldown_counter(message: Message, seconds_left: int):
    counter = await safe_send(message, f"🕒 Включен медленный режим (антиспам): {seconds_left} сек")
    try:
        while seconds_left > 0:
            await asyncio.sleep(1)
            seconds_left -= 1
            try:
                await message.bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=counter.message_id,
                    text=f"🕒 Медленный режим: {seconds_left} сек"
                )
            except TelegramBadRequest as e:
                if "message is not modified" in str(e).lower():
                    continue
                raise
        await safe_delete(counter)
    except Exception:
        await safe_delete(counter)

async def send_long_text(message: Message, text: str):
    if not text:
        await message.answer("Пустой ответ 😕", reply_markup=main_kb_for_plan(await _is_free(message.chat.id)))
        return
    for i in range(0, len(text), MAX_TG_LEN):
        await message.answer(
            text[i:i + MAX_TG_LEN],
            reply_markup=main_kb_for_plan(await _is_free(message.chat.id)) if i + MAX_TG_LEN >= len(text) else None
        )

async def show_subscriptions(message: Message):
    text = await get_status_text(message.chat.id)
    low = text.lower()
    if "план: free" in low:
        await message.answer(text, reply_markup=available_btn_kb())
    elif "план: lite" in low:
        text2 = text + "\n\n⬆️ Доступно обновление до PRO для безлимита и приоритета."
        await message.answer(text2, reply_markup=available_btn_kb())
    else:
        await message.answer(text)

# ----------------- START / ЯЗЫК -----------------

@router.message(CommandStart())
async def cmd_start(message: Message):
    await ensure_user(message.chat.id)

    # обработка реферального кода
    payload = None
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) > 1:
        payload = parts[1].strip()
    if payload and payload.startswith("ref_"):
        code = payload[4:]
        ref_id = await find_user_by_ref_code(code)
        if ref_id:
            await set_referrer_once(message.chat.id, ref_id)

    # обязательно сначала выбрать язык
    prefs = await get_prefs(message.chat.id)
    lang = (prefs or {}).get("lang")
    if not isinstance(lang, str) or lang not in LANGUAGES:
        await message.answer(
            "🌐 Выберите язык бота (интерфейс + ответы).\n"
            "Choose the bot language (interface + answers).",
            reply_markup=LANG_SELECT_KB,
        )
        return

    # авто-озвучка для PRO по умолчанию (если включено в конфиге)
    if TTS_ENABLED_DEFAULT_PRO and await _is_pro(message.chat.id):
        vs = await get_voice_settings(message.chat.id)
        if not vs.get("auto"):
            await set_voice_settings(message.chat.id, auto=True)

    is_free = await _is_free(message.chat.id)
    kb = main_kb_for_plan(is_free)
    mode_key = await get_current_mode(message.chat.id)
    mode_cfg = BOT_MODES.get(mode_key) or BOT_MODES["default"]
    greeting = build_greeting(lang, is_free, mode_cfg["title"])
    await message.answer(greeting, reply_markup=kb)

@router.message(Command("language"))
async def cmd_language(message: Message):
    await message.answer(
        "🌐 Выберите язык бота (интерфейс + ответы).\n"
        "Choose the bot language (interface + answers).",
        reply_markup=LANG_SELECT_KB,
    )

@router.message(F.text == "🌐 Язык бота")
async def settings_language(message: Message):
    await cmd_language(message)

@router.message(F.text.in_(list(LANG_BUTTONS.keys())))
async def language_chosen(message: Message):
    text = (message.text or "").strip()
    code = LANG_BUTTONS.get(text)
    if not code:
        return
    await set_pref(message.chat.id, "lang", code)
    title = LANGUAGES.get(code, code)
    is_free = await _is_free(message.chat.id)
    kb = main_kb_for_plan(is_free)
    mode_key = await get_current_mode(message.chat.id)
    mode_cfg = BOT_MODES.get(mode_key) or BOT_MODES["default"]
    greeting = build_greeting(code, is_free, mode_cfg["title"])
    await message.answer(
        f"✅ Язык сохранён: {title}.\n\n{greeting}",
        reply_markup=kb,
    )

# ----------------- МЕНЮ, НАСТРОЙКИ, FAQ -----------------

@router.message(F.text == "🎁 Бонус за друзей")
async def kb_referral(message: Message):
    await _send_referral_card(message)

@router.message(Command("ref"))
async def cmd_ref(message: Message):
    await _send_referral_card(message)

@router.message(F.text == "🧾 Мои подписки")
async def kb_subscriptions(message: Message):
    await show_subscriptions(message)

@router.message(F.text == "🔼 Обновить план")
async def kb_upgrade(message: Message):
    await message.answer("Выберите пакет:", reply_markup=plans_kb(show_back=False))

@router.message(Command("plan"))
async def cmd_plan(message: Message):
    await message.answer("Доступные пакеты:", reply_markup=plans_kb(show_back=True))

@router.message(Command("status"))
async def cmd_status(message: Message):
    await show_subscriptions(message)

@router.message(Command("reset"))
async def cmd_reset(message: Message):
    await clear_history(message.chat.id)
    await message.answer("🧹 Контекст очищен", reply_markup=main_kb_for_plan(await _is_free(message.chat.id)))

@router.message(F.text == "⚙️ Настройки")
async def open_settings(message: Message):
    _, is_lite, is_pro = await _plan_flags(message.chat.id)
    extra = "" if is_pro else "\n\nℹ️ Учитель, авто-озвучка, PDF и мини-тест — в PRO."
    await message.answer(
        "Настройки профиля:\n— авто-озвучка\n— режим Учителя\n— сброс контекста\n— тип работы бота" + extra,
        reply_markup=SETTINGS_KB
    )

@router.message(F.text == "🎛 Тип работы бота")
async def open_modes_menu(message: Message):
    mode_key = await get_current_mode(message.chat.id)
    cfg = BOT_MODES.get(mode_key) or BOT_MODES["default"]
    text = (
        "Выберите, как бот будет вести себя по умолчанию.\n\n"
        f"Текущий режим: {cfg['title']}\n"
        f"{cfg['description']}"
    )
    await message.answer(text, reply_markup=MODE_KB)

@router.message(F.text.in_(tuple(MODE_BUTTON_TEXT_TO_KEY.keys())))
async def set_mode_from_button(message: Message):
    key = MODE_BUTTON_TEXT_TO_KEY.get((message.text or "").strip())
    if not key:
        return
    await set_current_mode(message.chat.id, key)
    cfg = BOT_MODES.get(key) or BOT_MODES["default"]
    text = f"Режим обновлён: {cfg['title']}\n\n{cfg['description']}"
    await message.answer(text, reply_markup=MODE_KB)

@router.message(F.text == "◀️ Назад в настройки")
async def back_to_settings_from_modes(message: Message):
    await open_settings(message)

@router.message(F.text == "◀️ Назад в меню")
async def back_from_settings(message: Message):
    await message.answer("Готово.", reply_markup=main_kb_for_plan(await _is_free(message.chat.id)))

@router.message(F.text == "🧹 Сброс контекста")
async def settings_reset_ctx(message: Message):
    await cmd_reset(message)

@router.message(F.text == "👩‍🏫 Включить режим Учителя")
async def settings_teacher_on(message: Message):
    if not await _is_pro(message.chat.id):
        return await message.answer("👩‍🏫 Режим Учителя доступен только в PRO.", reply_markup=available_btn_kb())
    await set_teacher_mode(message.chat.id, True)
    await message.answer("👩‍🏫 Режим Учителя: ВКЛ.")

@router.message(F.text == "👨‍🎓 Выключить режим Учителя")
async def settings_teacher_off(message: Message):
    await set_teacher_mode(message.chat.id, False)
    await message.answer("👩‍🏫 Режим Учителя: ВЫКЛ.")

@router.message(F.text == "🔔 Включить авто-озвучку")
async def settings_voice_on(message: Message):
    if not await _is_pro(message.chat.id):
        return await message.answer("🎙 Авто-озвучка доступна только в PRO.", reply_markup=available_btn_kb())
    await set_voice_settings(message.chat.id, auto=True)
    await message.answer("🔔 Авто-озвучка: ВКЛ.")

@router.message(F.text == "🔕 Выключить авто-озвучку")
async def settings_voice_off(message: Message):
    await set_voice_settings(message.chat.id, auto=False)
    await message.answer("🔕 Авто-озвучка: ВЫКЛ.")

@router.message(Command("voice_on"))
async def cmd_voice_on(message: Message):
    if not await _is_pro(message.chat.id):
        return await message.answer("🎙 Озвучка доступна только в PRO. Обновите план: /plan")
    await set_voice_settings(message.chat.id, auto=True)
    await message.answer("🎙 Озвучка ответов: ВКЛ. Буду присылать voice после текста.")

@router.message(Command("voice_off"))
async def cmd_voice_off(message: Message):
    await set_voice_settings(message.chat.id, auto=False)
    await message.answer("🎙 Озвучка ответов: ВЫКЛ. Кнопка «Озвучить» останется под ответами.")

@router.message(Command("voice"))
async def cmd_voice_name(message: Message):
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        return await message.answer("Пример: /voice aria")
    await set_voice_settings(message.chat.id, name=parts[1].strip())
    await message.answer(f"🎙 Голос: {parts[1].strip()}")

@router.message(Command("voice_speed"))
async def cmd_voice_speed(message: Message):
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        return await message.answer("Пример: /voice_speed 0.9 (диапазон 0.5–1.6)")
    try:
        v = float(parts[1].strip())
    except Exception:
        return await message.answer("Укажи число, например 1.1")
    await set_voice_settings(message.chat.id, speed=v)
    await message.answer(f"🎛 Скорость озвучки: {max(0.5, min(1.6, v)):.2f}")

@router.message(Command("remember"))
async def cmd_remember(message: Message):
    last = await _last_assistant_text(message.chat.id)
    if not last:
        return await message.answer("Нет последнего ответа для закладки.")
    await remember_bookmark(message.chat.id, last)
    await message.answer("🔖 Сохранено в закладки. Достанешь через /bookmark или /forget для удаления.")

@router.message(Command("bookmark"))
async def cmd_bookmark(message: Message):
    bk = await get_last_bookmark(message.chat.id)
    if not bk:
        return await message.answer("Закладок пока нет.")
    await send_long_text(message, f"🔖 Последняя закладка:\n\n{bk}")

@router.message(Command("forget"))
async def cmd_forget(message: Message):
    ok = await forget_last_bookmark(message.chat.id)
    await message.answer("🗑 Удалил последнюю закладку." if ok else "Закладок не найдено.")

@router.message(Command("explain"))
async def cmd_explain(message: Message, state: FSMContext):
    if not await _is_pro(message.chat.id):
        return await message.answer("👩‍🏫 Режим Учителя доступен только в PRO.", reply_markup=available_btn_kb())
    await message.answer("Отправь вопрос/задачу — объясню как учитель: простые шаги, типичные ошибки и мини-проверка.")
    await set_teacher_mode(message.chat.id, True)

FAQ_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Как пользоваться ботом")],
        [KeyboardButton(text="Частые вопросы")],
        [KeyboardButton(text="Пользовательское соглашение")],
        [KeyboardButton(text="Политика конфиденциальности")],
        [KeyboardButton(text="Назад")],
    ],
    resize_keyboard=True,
)

@router.message(F.text == "FAQ / Помощь")
async def faq_main(message: Message):
    await message.answer("Выберите раздел:", reply_markup=FAQ_KB)

@router.message(F.text == "Как пользоваться ботом")
async def faq_how(message: Message):
    text = (
        "<b>📘 Как пользоваться ботом</b>\n\n"
        "👋 <i>Бот понимает и текст, и фото/скрины.</i>\n\n"
        "1️⃣ <b>Отправьте фото задания</b> — получите разбор по шагам: "
        "<i>Дано → Требуется → Формулы → Подстановка → Итог</i>.\n"
        "2️⃣ <b>Или напишите текстом</b> задачу/вопрос — бот тоже разберёт.\n"
        "3️⃣ <b>Инструменты под ответом</b> (для PRO): "
        "«<i>PDF</i>», «<i>Проверить себя</i>», «<i>Озвучить</i>».\n"
        "4️⃣ <b>Голосовые ответы</b>: включите <code>/voice_on</code>, выключите <code>/voice_off</code>.\n\n"
        "🧭 <b>Где что искать</b>\n"
        "• <b>⚙️ Настройки</b> — авто-озвучка, режим Учителя, сброс контекста, тип работы бота.\n"
        "• <b>🧾 Статус/тариф</b> — «Мои подписки» (или «Обновить план» в FREE).\n\n"
        "💡 <i>Совет:</i> если не хватает данных (чисел/условий), бот подскажет, что уточнить."
    )
    await message.answer(text, parse_mode=ParseMode.HTML)

@router.message(F.text == "Частые вопросы")
async def faq_questions(message: Message):
    text = (
        "<b>❓ Частые вопросы</b>\n\n"
        "• <b>Можно ли вернуть деньги?</b>\n"
        "  Оплаченные услуги <b>не подлежат возврату</b>, так как оплата совершается добровольно, "
        "а до покупки есть возможность ознакомиться с функционалом.\n\n"
        "• <b>Как происходит оплата?</b>\n"
        "  Через PayShark (платёжная форма). После оплаты доступ открывается автоматически.\n\n"
        "• <b>Что умеет бот?</b>\n"
        "  Он помогает <i>разобрать задачи, пояснить теорию, оформить решение</i>. "
        "Это помощник, а не полноценная замена преподавателя.\n\n"
        "• <b>Где включить озвучку/режим Учителя?</b>\n"
        "  В разделе <b>⚙️ Настройки</b> (доступно в PRO). Команды: "
        "<code>/voice_on</code>, <code>/voice_off</code>.\n\n"
        "• <b>PDF и мини-тест «Проверить себя»?</b>\n"
        "  Кнопки под ответом (в PRO). PDF — аккуратный файл для сдачи, "
        "мини-тест — 3–4 вопроса для самопроверки."
    )
    await message.answer(text, parse_mode=ParseMode.HTML)

@router.message(F.text == "Пользовательское соглашение")
async def faq_offer(message: Message):
    offer_text = (
        "📑 Пользовательское соглашение\n\n"
        "1. Общие положения\n"
        "1.1. Настоящее Пользовательское соглашение (далее – «Соглашение») регулирует порядок использования Telegram-бота «Учебный помощник» (далее – «Бот»).\n"
        "1.2. Используя Бот, Пользователь подтверждает согласие с условиями настоящего Соглашения.\n"
        "1.3. Бот предоставляет информационные и образовательные материалы и не является аккредитованным образовательным учреждением.\n\n"
        "2. Услуги и использование Бота\n"
        "2.1. Бот предоставляет Пользователю возможность загрузки учебных задач и получения пояснений и решений.\n"
        "2.2. Доступ к дополнительным функциям может быть предоставлен на платной основе.\n"
        "2.3. Оплата осуществляется добровольно.\n\n"
        "3. Оплата и возвраты\n"
        "3.1. Оплата производится через встроенные методы в Боте.\n"
        "3.2. Оплаченные услуги возврату не подлежат, поскольку оплата осуществляется добровольно, а Пользователь до момента приобретения имел возможность ознакомиться с содержанием и условиями предоставляемой услуги.\n"
        "3.3. В случае технических сбоев, по которым услуга не была оказана, Пользователь вправе обратиться в службу поддержки.\n\n"
        "4. Ответственность сторон\n"
        "4.1. Пользователь обязуется не использовать Бот для противоправных целей.\n"
        "4.2. Администрация Бота не несёт ответственности за:\n"
        "   – некорректное использование материалов Пользователем;\n"
        "   – невозможность предоставления услуги по причинам, не зависящим от Администрации (сбои сети Интернет, действия сторонних сервисов и т.п.).\n"
        "4.3. Вся ответственность за результаты применения полученной информации лежит на Пользователе.\n\n"
        "5. Обработка данных\n"
        "5.1. Бот обрабатывает следующие данные Пользователя: Telegram ID, username и иные данные, переданные самим Пользователем.\n"
        "5.2. Данные используются исключительно для работы сервиса и не передаются третьим лицам, за исключением случаев, предусмотренных законодательством.\n\n"
        "6. Изменение и прекращение работы\n"
        "6.1. Администрация вправе изменять функционал Бота, приостанавливать или прекращать его работу.\n"
        "6.2. Об изменениях Пользователи уведомляются через интерфейс Бота.\n\n"
        "7. Заключительные положения\n"
        "7.1. Настоящее Соглашение вступает в силу с момента начала использования Бота.\n"
        "7.2. Все возникающие вопросы, не урегулированные Соглашением, решаются в соответствии с действующим законодательством.\n"
        "7.3. Контакт для обращений: @gptEDU_support"
    )
    if len(offer_text) > MAX_TG_LEN:
        await send_long_text(message, offer_text)
    else:
        await message.answer(offer_text)



@router.message(F.text == "Политика конфиденциальности")
async def faq_privacy(message: Message):
    privacy_text = """Политика конфиденциальности


Настоящее соглашение о конфиденциальности использования
персональных данных (далее — Соглашение о
конфиденциальности) регулирует порядок сбора, использования и
разглашения Администрацией МЕРЧАНТ (Агент) информации о
Пользователе (Принципал), которая может быть признана
конфиденциальной или является таковой в соответствии с
законодательством РФ
Термины, используемые в настоящем Соглашении о
конфиденциальности, если не указано иное, применяются на
условиях и в значении, определенном Агентским договором.
Факт использования Пользователем сайта/telegram бота, а также
заключение Агентского договора являются полным и
безоговорочным акцептом настоящего Соглашения. Незнание
указанных соглашений не освобождает Пользователя от
ответственности за несоблюдение их условий.
Если Пользователь не согласен с условиями настоящего
Соглашения или не имеет права на заключение Соглашения,
Пользователю следует незамедлительно прекратить любое
использование сайта/telegram бота.


1 ИСТОЧНИКИ ИНФОРМАЦИИ
1.1 Информация, о которой идёт речь в настоящем соглашении,
может быть персонифицированной (прямо относящейся к
конкретному лицу или ассоциируемой с ним) и не
персонифицированной (данные о Пользователе сайта/telegram
бота, полученные без привязки к конкретному лицу).
1.2 Администрации доступна информация, получаемая
следующими способами: информация, полученная при переписке
Администрации с Пользователями сайта/telegram бота
посредством электронной почты; информация, предоставляемая
Пользователями при регистрации на сайта/telegram бота /
заключении Агентского договора, в рамках мероприятий,
проводимых Администрацией сайта/telegram бота, опросах,
заявках, формах обратной связи, путём внесения записей в
регистрационные онлайн-формы; техническая информация —
данные об интернет-провайдере Пользователя, IP-адресе
Пользователя, характеристиках используемого ПК и программного
обеспечения, данные о загруженных и выгруженных на
сайта/telegram бота файлах и т.п.; статистические данные о
предпочтениях отдельно взятого Пользователя (тематика
просмотренных страниц).
1.3 Конфиденциальной, согласно настоящему Соглашению,
может быть признана лишь информация, хранящаяся в базе
данных сайта/telegram бота в зашифрованном виде и доступная
для просмотра исключительно Администрации сайта/telegram
бота.
1.4 Информация о лице, добровольно размещённая им в общих
разделах сайта/telegram бота при заполнении регистрационных
форм и доступная любому другому пользователю сайта/telegram
бота, или информация, которая может быть свободно получена из
других общедоступных источников, не является
конфиденциальной.


2 БЕЗОПАСНОСТЬ
2.1 Администрация сайта/telegram бота использует современные
технологии обеспечения конфиденциальности персональных
данных, данных, полученных из регистрационных форм,
оставляемых Пользователями сайта/telegram бота, с целью
обеспечения максимальной защиты информации.
2.2 Доступ к личной информации Пользователя осуществляется
через систему авторизации с логином и паролем. Пользователь
обязуется самостоятельно обеспечить сохранность
авторотационных данных и ни под каким предлогом не
разглашать их третьим лицам. Любые изменения личной
информации, внесённые посредством авторотационных данных,
будут считаться осуществлёнными лично Пользователем.
2.3 Сбор, хранение, использование, обработка, разглашение
информации, полученной Администрацией сайта/telegram бота в
результате посещения пользователем сайта/telegram бота и/или
заполнения регистрационных форм, в том числе и персональные
данные пользователей, осуществляется администрацией
сайта/telegram бота в соответствии с законодательством РФ.
2.4 Пользователь осознает и предоставляет согласие на сбор и
обработку своих персональных данных Администрацией
сайта/telegram бота в рамках и с целью, предусмотренными
условиями Агентского договора; обязуется уведомлять
Администрацию сайта/telegram бота об изменениях его
персональных данных.


3 ЗАКЛЮЧИТЕЛЬНЫЕ ПОЛОЖЕНИЯ
3.1 Принципал, заинтересованный в услугах Агента, заполняет
специальную форму на сайта/telegram бота. При оформлении
заказа Принципал указывает UID, ID, Server ID, Zone ID, E-mail
учётной записи игры, на которую приобретается Цифровая
Услуга, а также количество требуемой игровой валюты или
требуемые игровые предметы.
3.2 Деятельность Администрации сайта/telegram бота
осуществляется в соответствии с законодательством РФ. Любые
претензии, споры, официальные обращения будут
рассматриваться исключительно в порядке, предусмотренном
законодательством РФ.
3.3 Администрация сайта/telegram бота не несёт ответственности
за любые прямые или косвенные убытки, понесённые
Пользователями или третьими сторонами, а также за упущенную
выгоду при использовании, невозможности использования или
результатов использования сайта/telegram бота.
3.4 условия настоящего Соглашения могут быть изменены
Администрацией сайта/telegram бота в одностороннем порядке""".strip()
    if len(privacy_text) > MAX_TG_LEN:
        await send_long_text(message, privacy_text)
    else:
        await message.answer(privacy_text)
@router.message(F.text == "Назад")
async def faq_back(message: Message):
    await message.answer("Возврат в главное меню", reply_markup=main_kb_for_plan(await _is_free(message.chat.id)))

# ----------------- АДМИНКА, РАССЫЛКИ -----------------

import json
from pathlib import Path

SECRET_ADMIN_CODES = {c.strip() for c in os.getenv("SECRET_ADMIN_CODES", "").split(",") if c.strip()}
ADMINS_FILE = Path("admins.json")
MAX_ADMINS = 2
ADMINS: set[int] = set()

def _load_admins():
    global ADMINS
    if ADMINS_FILE.exists():
        try:
            data = json.loads(ADMINS_FILE.read_text(encoding="utf-8"))
            if isinstance(data, list):
                ADMINS = set(int(x) for x in data)
        except Exception:
            ADMINS = set()

def _save_admins():
    try:
        ADMINS_FILE.write_text(json.dumps(sorted(list(ADMINS))), encoding="utf-8")
    except Exception:
        pass

_load_admins()

def is_admin(user_id: int) -> bool:
    return user_id in ADMINS

ADMIN_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📢 Рассылка — текст"), KeyboardButton(text="🖼️ Рассылка — фото")],
        [KeyboardButton(text="📊 Кол-во подписчиков"), KeyboardButton(text="⏪ Выйти из админ режима")],
    ],
    resize_keyboard=True,
)

@router.message(lambda m: (m.text or "").strip() in SECRET_ADMIN_CODES)
async def secret_code_grant(message: Message):
    uid = message.from_user.id
    if is_admin(uid):
        return await message.answer("Вы уже в админ-режиме.", reply_markup=ADMIN_KB)
    if len(ADMINS) >= MAX_ADMINS:
        return await message.answer(
            "Нельзя добавить нового админа — достигнут лимит (2 админа).",
            reply_markup=main_kb_for_plan(await _is_free(message.chat.id)),
        )
    ADMINS.add(uid)
    _save_admins()
    await message.answer("✅ Вы добавлены как админ. Открываю админ-панель.", reply_markup=ADMIN_KB)

@router.message(Command("admin"))
async def cmd_admin_open(message: Message):
    if not is_admin(message.from_user.id):
        return await message.answer("⛔ Доступно только админам.")
    await message.answer("Админ-панель:", reply_markup=ADMIN_KB)

@router.message(F.text == "⏪ Выйти из админ режима")
async def admin_logout(message: Message):
    uid = message.from_user.id
    if is_admin(uid):
        ADMINS.discard(uid)
        _save_admins()
        await message.answer("Вы вышли из админ-режима.", reply_markup=main_kb_for_plan(await _is_free(message.chat.id)))
    else:
        await message.answer("Вы не в админ-режиме.", reply_markup=main_kb_for_plan(await _is_free(message.chat.id)))

@router.message(Command("unsubscribe"))
async def cmd_unsub(message: Message):
    await set_optin(message.chat.id, False)
    await message.answer("❌ Вы отписаны от рассылок. Включить снова: /subscribe")

@router.message(Command("subscribe"))
async def cmd_sub(message: Message):
    await set_optin(message.chat.id, True)
    await message.answer("✅ Вы подписаны на рассылки. Отключить: /unsubscribe")

class AdminBroadcastStates(StatesGroup):
    waiting_for_text = State()
    waiting_for_photo = State()
    waiting_for_caption = State()
    confirm = State()

BROADCAST_CONCURRENCY = 20
BROADCAST_DELAY_SEC = 0.03

def _progress_bar(pct: float, width: int = 12) -> str:
    done = int(round(pct * width))
    return f"[{'█' * done}{'—' * (width - done)}] {int(pct * 100)}%"

def _confirm_kb(kind: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"bcast_confirm_{kind}"),
        InlineKeyboardButton(text="❌ Отменить", callback_data="bcast_cancel"),
    ]])

@router.message(F.text == "📊 Кол-во подписчиков")
async def admin_count(message: Message):
    if not is_admin(message.from_user.id):
        return
    ids = await get_all_chat_ids()
    await message.answer(f"Подписчиков (в базе): {len(ids)}")

@router.message(F.text == "📢 Рассылка — текст")
async def admin_broadcast_text_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(AdminBroadcastStates.waiting_for_text)
    await message.answer("Пришлите текст рассылки (plain/markdown).")

@router.message(AdminBroadcastStates.waiting_for_text, F.text)
async def admin_broadcast_text_preview(message: Message, state: FSMContext):
    await state.update_data(kind="text", text=message.text)
    await state.set_state(AdminBroadcastStates.confirm)
    await message.answer("Предпросмотр рассылки:", reply_markup=ReplyKeyboardRemove())
    await message.answer(message.text)
    await message.answer("Разослать?", reply_markup=_confirm_kb("text"))

@router.message(F.text == "🖼️ Рассылка — фото")
async def admin_broadcast_photo_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(AdminBroadcastStates.waiting_for_photo)
    await message.answer("Пришлите фото для рассылки.")

@router.message(AdminBroadcastStates.waiting_for_photo, F.photo)
async def admin_broadcast_photo_got(message: Message, state: FSMContext):
    await state.update_data(kind="photo", file_id=message.photo[-1].file_id)
    await state.set_state(AdminBroadcastStates.waiting_for_caption)
    await message.answer("Добавьте подпись к фото (или пришлите «-» чтобы без подписи).")

@router.message(AdminBroadcastStates.waiting_for_caption, F.text)
async def admin_broadcast_photo_preview(message: Message, state: FSMContext):
    data = await state.get_data()
    caption = None if message.text.strip() == "-" else message.text
    await state.update_data(caption=caption)
    await state.set_state(AdminBroadcastStates.confirm)
    await message.answer("Предпросмотр рассылки:", reply_markup=ReplyKeyboardRemove())
    await message.answer_photo(photo=data["file_id"], caption=caption)
    await message.answer("Разослать?", reply_markup=_confirm_kb("photo"))

@router.callback_query(F.data == "bcast_cancel")
async def admin_broadcast_cancel(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("Рассылка отменена.")
    await call.answer()

async def _deliver_to_all(bot, send_corofn, progress_msg: Message):
    ids: List[int] = await get_all_chat_ids()
    total = len(ids)
    ok = 0
    sem = asyncio.Semaphore(BROADCAST_CONCURRENCY)

    async def send_one(chat_id: int):
        nonlocal ok
        async with sem:
            try:
                await send_corofn(chat_id)
                ok += 1
            except TelegramRetryAfter as e:
                await asyncio.sleep(e.retry_after + 1)
                try:
                    await send_corofn(chat_id)
                    ok += 1
                except Exception:
                    pass
            except TelegramBadRequest as e:
                txt = str(e).lower()
                if "bot was blocked" in txt or "chat not found" in txt:
                    try:
                        await drop_chat(chat_id)
                    except Exception:
                        pass
            except Exception:
                pass
            try:
                pct = ok / max(1, total)
                await bot.edit_message_text(
                    chat_id=progress_msg.chat.id,
                    message_id=progress_msg.message_id,
                    text=f"Рассылка… {ok}/{total} {_progress_bar(pct)}"
                )
            except Exception:
                pass
            await asyncio.sleep(BROADCAST_DELAY_SEC)

    await asyncio.gather(*(send_one(cid) for cid in ids))
    try:
        await bot.edit_message_text(
            chat_id=progress_msg.chat.id,
            message_id=progress_msg.message_id,
            text=f"Готово ✅ Отправлено: {ok}/{total}"
        )
    except Exception:
        pass

@router.callback_query(F.data.in_(("bcast_confirm_text", "bcast_confirm_photo")))
async def admin_broadcast_confirm(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return await call.answer()
    data = await state.get_data()
    kind = "text" if call.data.endswith("text") else "photo"
    await state.clear()
    progress = await call.message.answer("Рассылка…")
    bot = call.message.bot
    if kind == "text":
        text = data["text"]

        async def sender(chat_id: int):
            await bot.send_message(chat_id, text)

        await _deliver_to_all(bot, sender, progress)
    else:
        file_id = data["file_id"]
        caption = data.get("caption")

        async def sender(chat_id: int):
            await bot.send_photo(chat_id, file_id, caption=caption)

        await _deliver_to_all(bot, sender, progress)
    await call.answer()

@router.callback_query(F.data == "show_plans")
async def cb_show_plans(call: CallbackQuery):
    await call.message.edit_text("Доступные пакеты:", reply_markup=plans_kb(show_back=True))
    await call.answer()

@router.callback_query(F.data.in_(("pay_lite", "pay_pro")))
async def cb_pay_plan(call: CallbackQuery):
    chat_id = call.message.chat.id
    username = (call.from_user.username or "").strip() if call.from_user else ""
    plan = "lite" if call.data == "pay_lite" else "pro"
    price_str = LITE_PRICE if plan == "lite" else PRO_PRICE
    amount_f = _as_float_price(price_str)
    amount_i = int(round(amount_f))
    currency_norm = _normalize_currency(PAYSHARK_CURRENCY)

    if not PUBLIC_BASE_URL:
        await call.message.answer(
            "⚠️ Оплата временно недоступна (не настроен PUBLIC_BASE_URL).\n"
            f"Напишите в поддержку: {SUPPORT_CONTACT}"
        )
        await call.answer()
        return

    external_id = build_external_id(chat_id, plan)
    callback_url = f"{PUBLIC_BASE_URL}/payshark/webhook"

    title = "LITE" if plan == "lite" else "PRO"
    try:
        client = PaysharkClient()
        order = await client.create_h2h_order(
            amount=amount_i,
            currency=currency_norm,
            external_id=external_id,
            callback_url=callback_url,
            client_id=str(chat_id),
            description=f"uStudy plan={plan} chat_id={chat_id} username={username}",
        )
    except Exception as e:
        import logging, re
        log = logging.getLogger('payments')
        code = 'H2H_ERR'
        msg = str(e)
        m = re.search(r'Payshark H2H HTTP\s+(\d{3})', msg)
        if m:
            code = f"H2H_HTTP_{m.group(1)}"

        try:
            import httpx
            if isinstance(e, httpx.HTTPStatusError) and getattr(e, 'response', None) is not None:
                resp = e.response
                code = f"H2H_HTTP_{resp.status_code}"
                log.error('Payshark H2H HTTP %s | chat_id=%s plan=%s ext=%s | body=%s', resp.status_code, chat_id, plan, external_id, (resp.text or '')[:1200])
            else:
                log.exception('Payshark H2H error | chat_id=%s plan=%s ext=%s', chat_id, plan, external_id)
        except Exception:
            log.exception('Payshark H2H error (logging failed)')
        await call.message.answer(
            f"💳 Оплата временно недоступна.\nКод: {code}\nНапишите в поддержку: {SUPPORT_CONTACT}"
        )
        await call.answer()
        return

    # фиксируем в Mongo
    try:
        await payment_create(
            pay_id=str(order.order_id),
            chat_id=int(chat_id),
            plan=str(plan),
            amount=float(amount_i),
            currency=str(order.currency or currency_norm or "RUB"),
            provider="payshark",
            raw_create=order.raw,
        )
        await payment_set_status(
            str(order.order_id),
            status=str(order.status or "created"),
            raw_event=None,
            external_id=str(order.external_id or external_id),
        )
    except Exception:
        # если БД недоступна, всё равно покажем пользователю реквизиты
        pass

    detail_txt = _format_payment_detail(order.payment_detail)

    text_parts: List[str] = [
        f"💳 Оплата {title} через PayShark (H2H)",
        "",
        f"Сумма: {price_str} ₽",
    ]
    if order.order_id:
        text_parts.append(f"ID сделки: {order.order_id}")
    text_parts.append("")
    if detail_txt:
        text_parts.append("Реквизиты для оплаты:")
        text_parts.append(detail_txt)
        text_parts.append("")

    text_parts.append(
        "После оплаты доступ откроется автоматически. "
        f"Если в течение 2–3 минут не открылся — напишите в поддержку {SUPPORT_CONTACT} и приложите чек/ID сделки."
    )

    kb_rows: List[List[InlineKeyboardButton]] = []
    if order.link_page_url:
        kb_rows.append([InlineKeyboardButton(text="💳 Перейти к оплате", url=order.link_page_url)])
    kb_rows.append([InlineKeyboardButton(text="🧾 Проверить статус", callback_data="pay_check_status")])

    await call.message.answer("\n".join(text_parts), reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))
    await call.answer()

@router.callback_query(F.data == "pay_check_status")
async def cb_pay_check_status(call: CallbackQuery):
    await show_subscriptions(call.message)
    await call.answer()


@router.callback_query(F.data == "back_to_subs")
async def cb_back_to_subs(call: CallbackQuery):
    text = await get_status_text(call.message.chat.id)
    kb: Optional[InlineKeyboardMarkup] = None
    low = text.lower()
    if "план: lite" in low or "план: free" in low:
        text += "\n\n⬆️ Доступно обновление до PRO для безлимита и приоритета."
        kb = available_btn_kb()
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()

# ----------------- ОСНОВНОЙ ФЛОУ: ТЕКСТ -----------------

@router.message(StateFilter('generating'))
async def wait_response(message: Message):
    await safe_send(message, "⏳ Ответ генерируется... дождитесь окончания предыдущего запроса!")

@router.message(F.text & ~F.text.startswith("/"))
async def generate_answer(message: Message, state: FSMContext):
    chat_id = message.chat.id
    user_text = (message.text or "").strip()
    if not user_text:
        return

    # нажали кнопку выбора языка — здесь ничего не делаем
    if user_text in LANG_BUTTONS:
        return

    # промокод тестового доступа (школьники-тестировщики)
    if PROMO_CODE and user_text.lower() == PROMO_CODE.lower():
        await ensure_user(chat_id)
        activated, exp = await apply_promocode_access(chat_id, PROMO_CODE, days=PROMO_PRO_DAYS)
        prefs = await get_prefs(chat_id)
        lang_pref = (prefs or {}).get("lang")
        exp_s = exp.strftime("%Y-%m-%d %H:%M UTC") if exp else ""
        if activated:
            msg = f"✅ Промокод активирован! Доступ PRO открыт до {exp_s}."
        else:
            msg = f"ℹ️ Промокод уже активирован. Доступ PRO действует до {exp_s}."
        if not isinstance(lang_pref, str) or lang_pref not in LANGUAGES:
            await message.answer(msg + "\n\n🌐 Теперь выберите язык бота:", reply_markup=LANG_SELECT_KB)
        else:
            await message.answer(msg, reply_markup=main_kb_for_plan(False))
        return

    user_db_id = await ensure_user(chat_id)
    lang = await ensure_language_selected(message)
    if lang is None:
        return

    now = time.monotonic()
    next_allowed = _next_allowed_by_chat.get(chat_id, 0.0)
    if now < next_allowed:
        seconds_left = int(next_allowed - now + 0.999)
        asyncio.create_task(show_cooldown_counter(message, seconds_left))
        return
    _next_allowed_by_chat[chat_id] = now + COOLDOWN_SECONDS

    allowed, msg = await can_use(user_db_id, "text")
    if not allowed:
        await message.answer(msg, reply_markup=plans_kb(show_back=True))
        return
    is_pro = await _is_pro(chat_id)
    if is_pro and await is_teacher_mode(chat_id):
        user_text = (
            "Объясни как опытный учитель: короткое введение, пошаговое решение, "
            "где часто ошибаются, мини-проверка на 2–3 вопроса в конце.\n\nВопрос: "
            + user_text
        )
    user_text = await apply_mode_to_text(chat_id, user_text)
    await state.set_state("generating")
    await message.bot.send_chat_action(chat_id, ChatAction.TYPING)
    draft = await safe_send(message, "Думаю…")
    typing_alive = True

    async def typing_loop():
        while typing_alive:
            try:
                await message.bot.send_chat_action(chat_id, ChatAction.TYPING)
            except Exception:
                pass
            await asyncio.sleep(4)

    typing_task = asyncio.create_task(typing_loop())
    accumulated = ""
    last_edit = 0.0
    try:
        history_msgs = await get_history(chat_id)
        async for delta in stream_response_text(user_text, history_msgs, priority=is_pro, teacher_mode=False):
            accumulated += delta
            t = asyncio.get_event_loop().time()
            if t - last_edit >= MIN_EDIT_INTERVAL:
                await safe_edit(message, draft.message_id, accumulated or "…")
                last_edit = t
        final_text = (f"⚡ PRO-приоритет\n{accumulated}" if is_pro else accumulated) if accumulated else ""
        if final_text:
            if len(final_text) > MAX_TG_LEN:
                await safe_delete(draft)
                await send_long_text(message, final_text)
                await message.answer("Действия с ответом:", reply_markup=answer_actions_kb(is_pro))
            else:
                await safe_edit(message, draft.message_id, final_text, reply_markup=answer_actions_kb(is_pro))
        else:
            await safe_edit(message, draft.message_id, "Пустой ответ 😕")
        await add_history(chat_id, "user", user_text)
        await add_history(chat_id, "assistant", accumulated or "")
        await inc_usage(chat_id, "text")
        if is_pro:
            vs = await get_voice_settings(chat_id)
            if vs.get("auto") and accumulated:
                await _send_tts_for_text(message, accumulated)
    except Exception as e:
        await safe_edit(message, draft.message_id, f"❌ Ошибка: {e}")
    finally:
        typing_alive = False
        typing_task.cancel()
        await state.clear()

# ----------------- ФОТО -----------------

@router.message(F.photo)
async def on_photo(message: Message, state: FSMContext):
    chat_id = message.chat.id
    user_db_id = await ensure_user(chat_id)
    lang = await ensure_language_selected(message)
    if lang is None:
        return

    now = time.monotonic()
    next_allowed = _next_allowed_by_chat.get(chat_id, 0.0)
    if now < next_allowed:
        seconds_left = int(next_allowed - now + 0.999)
        asyncio.create_task(show_cooldown_counter(message, seconds_left))
        return
    _next_allowed_by_chat[chat_id] = now + COOLDOWN_SECONDS

    allowed, msg = await can_use(user_db_id, "photo")
    if not allowed:
        await message.answer(msg, reply_markup=plans_kb(show_back=True))
        return
    await state.set_state("generating")
    await message.bot.send_chat_action(chat_id, ChatAction.TYPING)
    draft = await safe_send(message, "Распознаю задачу с фото…")
    try:
        largest = message.photo[-1]
        file = await message.bot.get_file(largest.file_id)
        buf = BytesIO()
        await message.bot.download_file(file.file_path, buf)
        image_bytes = buf.getvalue()
        teacher_hint = ""
        if await _is_pro(chat_id) and await is_teacher_mode(chat_id):
            teacher_hint = "Объясняй как учитель: короткое введение, пошагово, типичные ошибки, в конце мини-проверка (2–3 вопроса). "
        base_hint = teacher_hint + "Распознай условие и реши задачу. Покажи формулы, вычисления и итог."
        hint_text = await apply_mode_to_text(chat_id, base_hint)
        answer = await solve_from_image(
            image_bytes,
            hint=hint_text,
            history=await get_history(chat_id)
        )
        is_pro = await _is_pro(chat_id)
        final_text = f"⚡ PRO-приоритет\n{answer}" if (is_pro and answer) else (answer or "Не удалось распознать задачу.")
        if len(final_text) > MAX_TG_LEN:
            await safe_delete(draft)
            await send_long_text(message, final_text)
            if answer:
                await message.answer("Действия с ответом:", reply_markup=answer_actions_kb(is_pro))
        else:
            await safe_edit(
                message, draft.message_id, final_text,
                reply_markup=answer_actions_kb(is_pro and bool(answer))
            )
        await add_history(chat_id, "user", "[Фото задачи]")
        await add_history(chat_id, "assistant", answer or "")
        await inc_usage(chat_id, "photo")
        if is_pro:
            vs = await get_voice_settings(chat_id)
            if vs.get("auto") and answer:
                await _send_tts_for_text(message, answer)
    except Exception as e:
        await safe_edit(message, draft.message_id, f"❌ Ошибка по фото: {e}")
    finally:
        await state.clear()

# ----------------- TTS / PDF / QUIZ -----------------

@router.callback_query(F.data == "tts_say")
async def cb_tts_say(call: CallbackQuery):
    chat_id = call.message.chat.id
    if not await _is_pro(chat_id):
        await call.answer("Доступно только в PRO", show_alert=True)
        return
    text = await _last_assistant_text(chat_id)
    if not text:
        await call.answer("Нет текста для озвучки", show_alert=True)
        return
    await call.answer("Озвучиваю…", show_alert=False)
    try:
        await _send_tts_for_text(call.message, text)
    except Exception as e:
        try:
            await call.message.answer(f"❌ Ошибка озвучки: {e}")
        except Exception:
            pass

@router.callback_query(F.data == "export_pdf")
async def cb_export_pdf(call: CallbackQuery):
    chat_id = call.message.chat.id
    if not await _is_pro(chat_id):
        return await call.answer("Экспорт PDF доступен только в PRO.", show_alert=True)
    now = time.monotonic()
    if _export_lock.get(chat_id, 0.0) > now:
        return await call.answer("Уже экспортирую…", show_alert=False)
    _export_lock[chat_id] = now + 6.0
    answer = await _last_assistant_text(chat_id)
    if not answer:
        _export_lock.pop(chat_id, None)
        return await call.answer("Нет текста для экспорта", show_alert=True)
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    try:
        pdf = pdf_from_answer_text(answer, title="Разбор задачи", author="Учебный помощник")
        bi = BufferedInputFile(pdf.getvalue(), filename="razbor.pdf")
        await call.message.answer_document(document=bi, caption="📄 Экспортировано в PDF")
        await call.answer()
    except Exception as e:
        await call.answer(f"Ошибка экспорта: {e}", show_alert=True)
    finally:
        _export_lock.pop(chat_id, None)
        try:
            is_pro = await _is_pro(chat_id)
            await call.message.edit_reply_markup(reply_markup=answer_actions_kb(is_pro))
        except Exception:
            pass

def _quiz_kb(qi: dict, q_index: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    options = (qi.get("options") or [])[:4]
    for i, opt in enumerate(options):
        builder.row(
            InlineKeyboardButton(
                text=f"{chr(65 + i)}) {opt}",
                callback_data=f"quiz_answer:{q_index}:{i}"
            )
        )
    builder.adjust(1)
    return builder.as_markup()

@router.callback_query(F.data == "quiz_make")
async def cb_quiz_make(call: CallbackQuery):
    chat_id = call.message.chat.id
    if not await _is_pro(chat_id):
        return await call.answer("Мини-тест доступен только в PRO.", show_alert=True)
    answer = await _last_assistant_text(chat_id)
    if not answer or len(answer) < 40:
        return await call.answer("Сначала получи разбор/ответ, потом сделаю тест.", show_alert=True)
    await call.answer("Готовлю мини-тест…", show_alert=False)
    try:
        md, data = await quiz_from_answer(answer, n_questions=4)
        items = (data or {}).get("questions") or []
        if not items:
            return await call.message.answer(f"🧠 Мини-тест\n\n{md}")
        QUIZ_STATE[chat_id] = {"idx": 0, "items": items}
        q0 = items[0]
        text = f"🧠 Мини-тест\n\nВопрос 1/{len(items)}:\n{q0.get('q', '')}"
        await call.message.answer(text, reply_markup=_quiz_kb(q0, 0))
    except Exception as e:
        await call.message.answer(f"❌ Не удалось построить тест: {e}")

@router.callback_query(F.data.startswith("quiz_answer:"))
async def cb_quiz_answer(call: CallbackQuery):
    chat_id = call.message.chat.id
    try:
        _, q_index_str, opt_idx_str = call.data.split(":")
        q_idx = int(q_index_str)
        opt_idx = int(opt_idx_str)
        state = QUIZ_STATE.get(chat_id)
        if not state:
            return await call.answer("Тест не найден.", show_alert=True)
        items = state["items"]
        if q_idx >= len(items):
            return await call.answer("Вопрос не найден.", show_alert=True)
        qi = items[q_idx]
        correct_letter = (qi.get("correct") or "A").strip().upper()
        correct_idx = "ABCD".find(correct_letter)
        if correct_idx < 0:
            correct_idx = 0
        ok = (opt_idx == correct_idx)
        await call.answer("Верно! ✅" if ok else f"Неверно. ❌ Правильный ответ: {correct_letter}", show_alert=False)
        next_idx = q_idx + 1
        if next_idx < len(items):
            state["idx"] = next_idx
            qn = items[next_idx]
            await call.message.answer(
                f"Вопрос {next_idx + 1}/{len(items)}:\n{qn.get('q', '')}",
                reply_markup=_quiz_kb(qn, next_idx)
            )
        else:
            QUIZ_STATE.pop(chat_id, None)
            await call.message.answer("Готово! Хочешь ещё раз — жми «🧠 Проверить себя».")
    except Exception:
        await call.answer("Ошибка обработки ответа.", show_alert=True)

@router.callback_query(F.data.in_(("need_pro_pdf", "need_pro_quiz")))
async def cb_need_pro(call: CallbackQuery):
    await call.answer("Функция доступна только в PRO.", show_alert=True)
    await call.message.answer("Оформите PRO, чтобы открыть PDF и мини-тест:", reply_markup=plans_kb(show_back=False))

async def _send_tts_for_text(message: Message, text: str):
    chunks = split_for_tts(text, max_chars=TTS_CHUNK_LIMIT)
    try:
        vs = await get_voice_settings(message.chat.id)
    except Exception:
        vs = {"name": None, "speed": None}
    voice_name = (vs or {}).get("name")
    voice_speed = (vs or {}).get("speed")
    for idx, chunk in enumerate(chunks, 1):
        try:
            voice_bio = await tts_voice_ogg(chunk, voice=voice_name, speed=voice_speed)
            file = BufferedInputFile(voice_bio.getvalue(), filename=voice_bio.name or "voice.ogg")
            cap = f"🎙 Озвучка ({idx}/{len(chunks)})" if len(chunks) > 1 else "🎙 Озвучка"
            await message.answer_voice(voice=file, caption=cap)
            await asyncio.sleep(0.3)
        except Exception as e:
            await message.answer(f"❌ Не удалось озвучить часть {idx}: {e}")
            break
