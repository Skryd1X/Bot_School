from __future__ import annotations

from typing import Dict, List, Optional

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


# =========================
#   LANGUAGES / CORE
# =========================

DEFAULT_LANG = "ru"

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

# Указание модели на языке (чтобы ответы и интерфейс были в выбранном языке)
LANGUAGE_HINTS: Dict[str, str] = {
    "ru": "Всегда отвечай пользователю только на русском языке, если он явно не просит другой язык.",
    "en": "Always respond only in English unless the user explicitly asks for another language.",
    "uz": "Har doim foydalanuvchiga faqat o‘zbek tilida javob ber, agar u boshqa tilni aniq so‘ramasa.",
    "kk": "Пайдаланушы басқа тілді нақты сұрамаса, әрқашан тек қазақ тілінде жауап бер.",
    "de": "Antworte immer nur auf Deutsch, es sei denn, der Nutzer fordert ausdrücklich eine andere Sprache an.",
    "fr": "Réponds toujours uniquement en français, sauf si l’utilisateur demande explicitement une autre langue.",
    "es": "Responde siempre solo en español, a menos que el usuario pida explícitamente otro idioma.",
    "tr": "Kullanıcı açıkça başka bir dil istemedikçe her zaman yalnızca Türkçe yanıt ver.",
    "ar": "أجب دائمًا باللغة العربية فقط ما لم يطلب المستخدم صراحةً لغة أخرى.",
    "hi": "हमेशा केवल हिन्दी में उत्तर दें, जब तक उपयोगकर्ता स्पष्ट रूप से किसी अन्य भाषा के लिए न कहे।",
}


# =========================
#   KEYBOARDS
# =========================

def lang_select_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
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


# =========================
#   TEXTS (UI)
# =========================

UI_TEXT: Dict[str, Dict[str, str]] = {
    "choose_language_prompt": {
        "ru": "🌐 Выберите язык бота (интерфейс + ответы).",
        "en": "🌐 Choose the bot language (interface + answers).",
        "uz": "🌐 Bot tilini tanlang (interfeys + javoblar).",
        "kk": "🌐 Бот тілін таңдаңыз (интерфейс + жауаптар).",
        "de": "🌐 Wähle die Bot-Sprache (Interface + Antworten).",
        "fr": "🌐 Choisissez la langue du bot (interface + réponses).",
        "es": "🌐 Elige el idioma del bot (interfaz + respuestas).",
        "tr": "🌐 Bot dilini seçin (arayüz + cevaplar).",
        "ar": "🌐 اختر لغة البوت (الواجهة + الردود).",
        "hi": "🌐 बॉट की भाषा चुनें (इंटरफ़ेस + उत्तर)।",
    },
    "language_saved": {
        "ru": "✅ Язык сохранён: {title}.",
        "en": "✅ Language saved: {title}.",
        "uz": "✅ Til saqlandi: {title}.",
        "kk": "✅ Тіл сақталды: {title}.",
        "de": "✅ Sprache gespeichert: {title}.",
        "fr": "✅ Langue enregistrée : {title}.",
        "es": "✅ Idioma guardado: {title}.",
        "tr": "✅ Dil kaydedildi: {title}.",
        "ar": "✅ تم حفظ اللغة: {title}.",
        "hi": "✅ भाषा सहेजी गई: {title}।",
    },
    "thinking": {
        "ru": "Думаю…",
        "en": "Thinking…",
        "uz": "O‘ylayapman…",
        "kk": "Ойланудамын…",
        "de": "Ich denke…",
        "fr": "Je réfléchis…",
        "es": "Pensando…",
        "tr": "Düşünüyorum…",
        "ar": "أفكر…",
        "hi": "सोच रहा हूँ…",
    },
    "photo_recognizing": {
        "ru": "Распознаю задачу с фото…",
        "en": "Recognizing the task from the photo…",
        "uz": "Rasmda berilgan vazifani tanimoqdaman…",
        "kk": "Суреттен тапсырманы танып жатырмын…",
        "de": "Ich erkenne die Aufgabe vom Foto…",
        "fr": "Je reconnais l’exercice à partir de la photo…",
        "es": "Reconociendo la tarea de la foto…",
        "tr": "Fotoğraftaki görevi tanıyorum…",
        "ar": "أتعرف على المسألة من الصورة…",
        "hi": "फोटो से प्रश्न पहचान रहा हूँ…",
    },
    "empty_answer": {
        "ru": "Пустой ответ 😕",
        "en": "Empty answer 😕",
        "uz": "Javob bo‘sh 😕",
        "kk": "Бос жауап 😕",
        "de": "Leere Antwort 😕",
        "fr": "Réponse vide 😕",
        "es": "Respuesta vacía 😕",
        "tr": "Boş cevap 😕",
        "ar": "إجابة فارغة 😕",
        "hi": "खाली उत्तर 😕",
    },
}


def t(lang: str, key: str, **kwargs) -> str:
    """Простой переводчик: t(lang, 'key', var=value)."""
    lang = lang if lang in LANGUAGES else DEFAULT_LANG
    data = UI_TEXT.get(key, {})
    text = data.get(lang) or data.get(DEFAULT_LANG) or key
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text


# =========================
#   GREETING
# =========================

def greeting(lang: str, is_free: bool, mode_title: str) -> str:
    lang = lang if lang in LANGUAGES else DEFAULT_LANG

    # короткие варианты для всех языков
    plans_line = {
        "ru": "— Обновить план — кнопка ниже." if is_free else "— Статус доступа — «🧾 Мои подписки».",
        "en": "— Upgrade plan — button below." if is_free else "— Access status — “🧾 My subscriptions”.",
        "uz": "— Rejani yangilash — pastdagi tugma." if is_free else "— Holat — “🧾 Mening obunalarim”.",
        "kk": "— Жоспарды жаңарту — төмендегі батырма." if is_free else "— Күйі — “🧾 Менің жазылымдарым”.",
        "de": "— Tarif upgraden — Button unten." if is_free else "— Zugriff — “🧾 Meine Abos”.",
        "fr": "— Mettre à niveau — bouton ci-dessous." if is_free else "— Statut — «🧾 Mes abonnements ».",
        "es": "— Mejorar plan — botón abajo." if is_free else "— Estado — “🧾 Mis suscripciones”.",
        "tr": "— Plan yükselt — aşağıdaki düğme." if is_free else "— Durum — “🧾 Aboneliklerim”.",
        "ar": "— ترقية الخطة — الزر بالأسفل." if is_free else "— الحالة — «🧾 اشتراكاتي».",
        "hi": "— प्लान अपग्रेड — नीचे बटन।" if is_free else "— स्थिति — “🧾 मेरी सदस्यताएँ”。",
    }.get(lang, "")

    # приветствие (полная структура)
    if lang == "ru":
        return (
            "👋 Привет! Я — учебный помощник для школы и вузов.\n\n"
            "Что я умею:\n"
            "• Разбирать задачи по шагам\n"
            "• Пояснять теорию простым языком\n"
            "• Писать эссе, конспекты, рефераты\n"
            "• Помогать с кодом и оформлением\n"
            "• Понимать фото/скриншоты задач 📷\n\n"
            "Как начать:\n"
            "— Пришли фото задачи или напиши текстом.\n"
            "— Нужна справка — жми «FAQ / Помощь».\n"
            f"{plans_line}\n"
            "— 🎁 Бонус за друзей: пригласи друзей и получай PRO.\n\n"
            f"Текущий режим: {mode_title}\n"
            "Изменить можно в ⚙️ Настройки → 🎛 Тип работы бота."
        )

    # English fallback, and other languages: simpler but понятный
    return (
        "👋 Hi! I’m a study assistant for school & university.\n\n"
        "What I can do:\n"
        "• Solve tasks step by step\n"
        "• Explain theory simply\n"
        "• Write essays/notes/reports\n"
        "• Help with code and formatting\n"
        "• Understand photos/screenshots 📷\n\n"
        "How to start:\n"
        "— Send a photo or write the task in text.\n"
        "— Need help? Tap “FAQ / Help”.\n"
        f"{plans_line}\n\n"
        f"Current mode: {mode_title}\n"
        "Change it in ⚙️ Settings → 🎛 Bot mode."
    )


# =========================
#   FAQ TEXTS (HTML)
# =========================

FAQ_TEXT: Dict[str, Dict[str, str]] = {
    "how": {
        "ru": (
            "<b>📘 Как пользоваться ботом</b>\n\n"
            "👋 <i>Бот понимает и текст, и фото/скрины.</i>\n\n"
            "1️⃣ <b>Отправьте фото задания</b> — получите разбор по шагам.\n"
            "2️⃣ <b>Или напишите текстом</b> задачу/вопрос — бот тоже разберёт.\n"
            "3️⃣ <b>Инструменты под ответом</b> (для PRO): <i>PDF</i>, <i>Проверить себя</i>, <i>Озвучить</i>.\n"
            "4️⃣ <b>Голосовые ответы</b>: <code>/voice_on</code> и <code>/voice_off</code>.\n\n"
            "🧭 <b>Где что искать</b>\n"
            "• <b>⚙️ Настройки</b> — авто-озвучка, режим Учителя, сброс контекста, тип работы.\n"
            "• <b>🧾 Статус</b> — «Мои подписки» (или «Обновить план» в FREE).\n\n"
            "💡 <i>Совет:</i> если не хватает данных, бот подскажет что уточнить."
        ),
        "en": (
            "<b>📘 How to use the bot</b>\n\n"
            "👋 <i>The bot understands both text and photos/screenshots.</i>\n\n"
            "1️⃣ <b>Send a photo of the task</b> — you’ll get a step-by-step solution.\n"
            "2️⃣ <b>Or write the task in text</b> — it will solve it too.\n"
            "3️⃣ <b>Tools under the answer</b> (PRO): <i>PDF</i>, <i>Quiz</i>, <i>Speak</i>.\n"
            "4️⃣ <b>Voice answers</b>: <code>/voice_on</code> and <code>/voice_off</code>.\n\n"
            "🧭 <b>Where to find things</b>\n"
            "• <b>⚙️ Settings</b> — voice, Teacher mode, reset context, bot mode.\n"
            "• <b>🧾 Status</b> — “My subscriptions” (or “Upgrade plan” in FREE).\n\n"
            "💡 <i>Tip:</i> if data is missing, the bot will tell you what to уточнить."
        ),
    },
    "questions": {
        "ru": (
            "<b>❓ Частые вопросы</b>\n\n"
            "• <b>Можно ли вернуть деньги?</b>\n"
            "  Оплаченные услуги <b>не подлежат возврату</b>.\n\n"
            "• <b>Как происходит оплата?</b>\n"
            "  Через встроенные способы в боте.\n\n"
            "• <b>Что умеет бот?</b>\n"
            "  Помогает решать задачи, объяснять теорию, оформлять решение.\n\n"
            "• <b>Где включить озвучку/режим Учителя?</b>\n"
            "  В <b>⚙️ Настройки</b> (PRO). Команды: <code>/voice_on</code>, <code>/voice_off</code>.\n\n"
            "• <b>PDF и мини-тест?</b>\n"
            "  Кнопки под ответом (PRO)."
        ),
        "en": (
            "<b>❓ FAQ</b>\n\n"
            "• <b>Can I get a refund?</b>\n"
            "  Paid services are <b>non-refundable</b>.\n\n"
            "• <b>How does payment work?</b>\n"
            "  Via built-in methods inside the bot.\n\n"
            "• <b>What can the bot do?</b>\n"
            "  Solve tasks, explain theory, format solutions.\n\n"
            "• <b>Where to enable voice/Teacher mode?</b>\n"
            "  In <b>⚙️ Settings</b> (PRO). Commands: <code>/voice_on</code>, <code>/voice_off</code>.\n\n"
            "• <b>PDF and quiz?</b>\n"
            "  Buttons under the answer (PRO)."
        ),
    },
    "offer": {
        "ru": (
            "📑 Пользовательское соглашение\n\n"
            "1. Общие положения\n"
            "1.1. Настоящее соглашение регулирует использование Telegram-бота.\n"
            "1.2. Используя бот, вы соглашаетесь с условиями.\n"
            "1.3. Бот предоставляет образовательные материалы и не является учебным заведением.\n\n"
            "2. Услуги\n"
            "2.1. Бот помогает с задачами и пояснениями.\n"
            "2.2. Доп. функции могут быть платными.\n\n"
            "3. Оплата\n"
            "3.1. Оплата через встроенные методы.\n"
            "3.2. Оплаченные услуги возврату не подлежат.\n\n"
            "Контакт: @gptEDU_support"
        ),
        "en": (
            "📑 User Agreement\n\n"
            "1. General\n"
            "1.1. This agreement governs the use of the Telegram bot.\n"
            "1.2. By using the bot, you accept these terms.\n"
            "1.3. The bot provides educational information and is not an accredited institution.\n\n"
            "2. Services\n"
            "2.1. The bot helps with tasks and explanations.\n"
            "2.2. Extra features may be paid.\n\n"
            "3. Payments\n"
            "3.1. Payments are made via built-in methods.\n"
            "3.2. Paid services are non-refundable.\n\n"
            "Contact: @gptEDU_support"
        ),
    },
}


def faq(lang: str, section: str) -> str:
    lang = lang if lang in LANGUAGES else DEFAULT_LANG
    data = FAQ_TEXT.get(section, {})
    return data.get(lang) or data.get(DEFAULT_LANG) or "…"
