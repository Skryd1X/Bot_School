from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from .buttons import btn

def main_menu_kb(lang: str, is_free: bool) -> ReplyKeyboardMarkup:
    if is_free:
        keyboard = [
            [KeyboardButton(text=btn(lang, "upgrade_plan")), KeyboardButton(text=btn(lang, "faq"))],
            [KeyboardButton(text=btn(lang, "settings")), KeyboardButton(text=btn(lang, "ref_bonus"))],
        ]
    else:
        keyboard = [
            [KeyboardButton(text=btn(lang, "my_subs")), KeyboardButton(text=btn(lang, "faq"))],
            [KeyboardButton(text=btn(lang, "settings")), KeyboardButton(text=btn(lang, "ref_bonus"))],
        ]
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Напишите вопрос или пришлите фото… / Type a question or send a photo…",
    )

def settings_kb(lang: str) -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text=btn(lang, "voice_on")), KeyboardButton(text=btn(lang, "voice_off"))],
        [KeyboardButton(text=btn(lang, "teacher_on")), KeyboardButton(text=btn(lang, "teacher_off"))],
        [KeyboardButton(text=btn(lang, "reset_ctx"))],
        [KeyboardButton(text=btn(lang, "bot_mode"))],
        [KeyboardButton(text=btn(lang, "bot_language"))],
        [KeyboardButton(text=btn(lang, "back_menu"))],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def faq_kb(lang: str) -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text=btn(lang, "faq_how"))],
        [KeyboardButton(text=btn(lang, "faq_questions"))],
        [KeyboardButton(text=btn(lang, "user_agreement"))],
        [KeyboardButton(text=btn(lang, "back"))],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def modes_kb(lang: str, titles: dict[str, str]) -> ReplyKeyboardMarkup:
    # titles: key->title already localized
    keyboard = [
        [KeyboardButton(text=titles["default"]), KeyboardButton(text=titles["simple"])],
        [KeyboardButton(text=titles["coach"]), KeyboardButton(text=titles["exam"])],
        [KeyboardButton(text=titles["solve_full"]), KeyboardButton(text=titles["hint"])],
        [KeyboardButton(text=titles["check"]), KeyboardButton(text=titles["notes"])],
        [KeyboardButton(text=titles["test"]), KeyboardButton(text=titles["cards"])],
        [KeyboardButton(text=titles["cheatsheet"]), KeyboardButton(text=titles["mindmap"])],
        [KeyboardButton(text=titles["study_plan"])],
        [KeyboardButton(text=btn(lang, "back_settings"))],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
