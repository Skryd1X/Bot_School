from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

LANGUAGES = {
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

LANG_BUTTONS = {
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

LANGUAGE_HINTS = {
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
        [KeyboardButton(text="🇷🇺 Русский"), KeyboardButton(text="🇬🇧 English")],
        [KeyboardButton(text="🇺🇿 Oʻzbek"), KeyboardButton(text="🇰🇿 Қазақша")],
        [KeyboardButton(text="🇩🇪 Deutsch"), KeyboardButton(text="🇫🇷 Français")],
        [KeyboardButton(text="🇪🇸 Español"), KeyboardButton(text="🇹🇷 Türkçe")],
        [KeyboardButton(text="🇦🇪 العربية"), KeyboardButton(text="🇮🇳 हिन्दी")],
    ],
    resize_keyboard=True,
    is_persistent=True,
    input_field_placeholder="🌐 Choose language / Выберите язык…",
)
