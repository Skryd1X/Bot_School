from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

LANGUAGES: dict[str, str] = {
    "ru": "Русский",
    "en": "English",
    "uz": "O‘zbek",
    "kk": "Қазақша",
    "de": "Deutsch",
    "fr": "Français",
    "es": "Español",
    "tr": "Türkçe",
    "ar": "العربية",
    "hi": "हिन्दी",
}

_LANG_BUTTONS_LIST: list[tuple[str, str]] = [
    ("🇷🇺 Русский", "ru"),
    ("🇬🇧 English", "en"),
    ("🇺🇿 O‘zbek", "uz"),
    ("🇰🇿 Қазақша", "kk"),
    ("🇩🇪 Deutsch", "de"),
    ("🇫🇷 Français", "fr"),
    ("🇪🇸 Español", "es"),
    ("🇹🇷 Türkçe", "tr"),
    ("🇸🇦 العربية", "ar"),
    ("🇮🇳 हिन्दी", "hi"),
]

LANG_BUTTONS: dict[str, str] = {text: code for text, code in _LANG_BUTTONS_LIST}

LANG_SELECT_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🇷🇺 Русский"), KeyboardButton(text="🇬🇧 English")],
        [KeyboardButton(text="🇺🇿 O‘zbek"), KeyboardButton(text="🇰🇿 Қазақша")],
        [KeyboardButton(text="🇩🇪 Deutsch"), KeyboardButton(text="🇫🇷 Français")],
        [KeyboardButton(text="🇪🇸 Español"), KeyboardButton(text="🇹🇷 Türkçe")],
        [KeyboardButton(text="🇸🇦 العربية"), KeyboardButton(text="🇮🇳 हिन्दी")],
    ],
    resize_keyboard=True,
    one_time_keyboard=True,
)
