# handlers.py
import os
import asyncio
import time
from io import BytesIO
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote_plus

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

from generators import stream_response_text, solve_from_image, quiz_from_answer
from db import (
    ensure_user, can_use, inc_usage, get_status_text,
    get_all_chat_ids, drop_chat, set_optin,
    # prefs / voice
    get_prefs, get_pref_bool, set_pref,
    get_voice_settings, set_voice_settings,
    is_teacher_mode, set_teacher_mode,
    get_priority, set_priority,
    get_answer_style, set_answer_style,
    # history & bookmarks
    add_history, get_history, clear_history,
    remember_bookmark, forget_last_bookmark, get_last_bookmark,
    # рефералка
    get_or_create_ref_code, get_referral_stats,
    find_user_by_ref_code, set_referrer_once,
)

from utils_export import pdf_from_answer_text
from tts import tts_voice_ogg, split_for_tts

router = Router()

# ---------- Константы/окружение ----------
COOLDOWN_SECONDS   = 5
MIN_INTERVAL_SEND  = 1.1
MIN_EDIT_INTERVAL  = 0.25
MAX_TG_LEN         = 4096

TRIBUTE_LITE_STARTAPP = os.getenv("TRIBUTE_LITE_STARTAPP", "")
TRIBUTE_PRO_STARTAPP  = os.getenv("TRIBUTE_PRO_STARTAPP", "")
TRIBUTE_LITE_PRICE    = os.getenv("TRIBUTE_LITE_PRICE", "200")
TRIBUTE_PRO_PRICE     = os.getenv("TRIBUTE_PRO_PRICE", "300")

# Рефералка
BOT_USERNAME          = os.getenv("BOT_USERNAME", "your_bot").lstrip("@")  # без @
REF_BONUS_THRESHOLD   = int(os.getenv("REF_BONUS_THRESHOLD", "6"))         # каждые N оплат = +1 месяц PRO

# Параметры TTS
TTS_ENABLED_DEFAULT_PRO = True
TTS_CHUNK_LIMIT = 2500

def tribute_url(code: str) -> str:
    return f"https://t.me/tribute/app?startapp={code}"

# ---------- План/клавиатуры ----------
async def _plan_flags(chat_id: int) -> Tuple[bool, bool, bool]:
    """return (is_free, is_lite, is_pro)"""
    t = (await get_status_text(chat_id)).lower()
    return ("план: free" in t, "план: lite" in t, "план: pro" in t)

def plans_kb(show_back: bool = False) -> InlineKeyboardMarkup:
    row = [
        InlineKeyboardButton(text=f"🪙 LITE {TRIBUTE_LITE_PRICE} ₽", url=tribute_url(TRIBUTE_LITE_STARTAPP)),
        InlineKeyboardButton(text=f"🚀 PRO {TRIBUTE_PRO_PRICE} ₽",  url=tribute_url(TRIBUTE_PRO_STARTAPP)),
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
            [KeyboardButton(text="⚙️ Настройки"),     KeyboardButton(text="🎁 Бонус за друзей")],
        ]
    else:
        keyboard = [
            [KeyboardButton(text="🧾 Мои подписки"),  KeyboardButton(text="FAQ / Помощь")],
            [KeyboardButton(text="⚙️ Настройки"),     KeyboardButton(text="🎁 Бонус за друзей")],
        ]
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Напишите вопрос или пришлите фото…",
    )

SETTINGS_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🔔 Включить авто-озвучку"), KeyboardButton(text="🔕 Выключить авто-озвучку")],
        [KeyboardButton(text="👩‍🏫 Включить режим Учителя"), KeyboardButton(text="👨‍🎓 Выключить режим Учителя")],
        [KeyboardButton(text="🧹 Сброс контекста")],
        [KeyboardButton(text="◀️ Назад в меню")],
    ],
    resize_keyboard=True,
)

# ---------- Рейтконтроль ----------
_last_send_ts: Dict[int, float] = {}
_next_allowed_by_chat: Dict[int, float] = {}

# ------------- helpers -------------
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
    code  = stats.get("ref_code") or await get_or_create_ref_code(message.chat.id)
    link  = _ref_link_from_code(code)
    paid  = int(stats.get("referred_paid_count") or 0)
    total = int(stats.get("referred_count") or 0)
    left  = max(0, REF_BONUS_THRESHOLD - (paid % REF_BONUS_THRESHOLD))
    progress = paid % REF_BONUS_THRESHOLD
    meter = "█"*progress + "—"*(REF_BONUS_THRESHOLD-progress)

    text = (
        "🎁 <b>Бонус за друзей</b>\n\n"
        f"Приглашай друзей по персональной ссылке.\n"
        f"За каждые <b>{REF_BONUS_THRESHOLD}</b> покупок (LITE/PRO) по твоей ссылке — <b>+1 месяц PRO</b>.\n\n"
        f"🔗 <b>Твоя ссылка:</b>\n<code>{link}</code>\n\n"
        f"📊 <b>Статистика</b>\n"
        f"— Всего приглашено: <b>{total}</b>\n"
        f"— Купили подписку: <b>{paid}</b>\n"
        f"— Прогресс до подарка: [{meter}] {progress}/{REF_BONUS_THRESHOLD}\n"
        f"— До следующего подарка: <b>{left}</b>\n\n"
        "Поделись ссылкой с одногруппниками, в чатах курса или друзьям 👇"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🔗 Открыть ссылку", url=link),
        _share_button(link, "Помощник для учёбы — моя реф. ссылка:")
    ]])
    await message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)

# ---------- Безопасные отправки/редактирования ----------
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
            text[i:i+MAX_TG_LEN],
            reply_markup=main_kb_for_plan(await _is_free(message.chat.id)) if i + MAX_TG_LEN >= len(text) else None
        )

# ---------- Экран «Мои подписки» ----------
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

# ---------- Команды/кнопки ----------
@router.message(CommandStart())
async def cmd_start(message: Message):
    await ensure_user(message.chat.id)

    # deep-link: /start ref_xxxxxx
    payload = None
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) > 1:
        payload = parts[1].strip()
    if payload and payload.startswith("ref_"):
        code = payload[4:]
        ref_id = await find_user_by_ref_code(code)
        if ref_id:
            await set_referrer_once(message.chat.id, ref_id)

    # авто-включение озвучки для PRO
    if TTS_ENABLED_DEFAULT_PRO and await _is_pro(message.chat.id):
        vs = await get_voice_settings(message.chat.id)
        if not vs.get("auto"):
            await set_voice_settings(message.chat.id, auto=True)

    is_free = await _is_free(message.chat.id)
    kb = main_kb_for_plan(is_free)

    greeting = (
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
        f"— { 'Обновить план — кнопка ниже.' if is_free else 'Статус доступа — «🧾 Мои подписки».' }\n"
        "— 🎁 Бонус за друзей: пригласи друзей и получай PRO."
    )
    await message.answer(greeting, reply_markup=kb)

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

# ===== Раздел «Настройки» =====
@router.message(F.text == "⚙️ Настройки")
async def open_settings(message: Message):
    _, is_lite, is_pro = await _plan_flags(message.chat.id)
    extra = "" if is_pro else "\n\nℹ️ Учитель, авто-озвучка, PDF и мини-тест — в PRO."
    await message.answer(
        "Настройки профиля:\n— авто-озвучка\n— режим Учителя\n— сброс контекста" + extra,
        reply_markup=SETTINGS_KB
    )

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

# Команды для голоса (вне меню)
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

# Закладки
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

# Режим объяснения «Учитель» (разово)
@router.message(Command("explain"))
async def cmd_explain(message: Message, state: FSMContext):
    if not await _is_pro(message.chat.id):
        return await message.answer("👩‍🏫 Режим Учителя доступен только в PRO.", reply_markup=available_btn_kb())
    await message.answer("Отправь вопрос/задачу — объясню как учитель: простые шаги, типичные ошибки и мини-проверка.")
    await set_teacher_mode(message.chat.id, True)

# ---------- FAQ / Помощь ----------
FAQ_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Как пользоваться ботом")],
        [KeyboardButton(text="Частые вопросы")],
        [KeyboardButton(text="Пользовательское соглашение")],
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
        "• <b>⚙️ Настройки</b> — авто-озвучка, режим Учителя, сброс контекста.\n"
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
        "  Через встроенные способы в боте. После оплаты доступ открывается автоматически.\n\n"
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

@router.message(F.text == "Назад")
async def faq_back(message: Message):
    await message.answer("Возврат в главное меню", reply_markup=main_kb_for_plan(await _is_free(message.chat.id)))

# ---------- Admin panel / рассылки ----------
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
        return await message.answer("Нельзя добавить нового админа — достигнут лимит (2 админа).", reply_markup=main_kb_for_plan(await _is_free(message.chat.id)))

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
BROADCAST_DELAY_SEC   = 0.03

def _progress_bar(pct: float, width: int = 12) -> str:
    done = int(round(pct * width))
    return f"[{'█'*done}{'—'*(width-done)}] {int(pct*100)}%"

def _confirm_kb(kind: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"bcast_confirm_{kind}"),
        InlineKeyboardButton(text="❌ Отменить",    callback_data="bcast_cancel"),
    ]])

# ---- Админ кнопки
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
                # удалённый чат/блок — можно почистить
                txt = str(e).lower()
                if "bot was blocked" in txt or "chat not found" in txt:
                    try:
                        await drop_chat(chat_id)
                    except Exception:
                        pass
            except Exception:
                pass
            # прогресс
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

# ---------- Callback-кнопки под статусом ----------
@router.callback_query(F.data == "show_plans")
async def cb_show_plans(call: CallbackQuery):
    await call.message.edit_text("Доступные пакеты:", reply_markup=plans_kb(show_back=True))
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

# ---------- Генерация текста ----------
@router.message(StateFilter('generating'))
async def wait_response(message: Message):
    await safe_send(message, "⏳ Ответ генерируется... дождитесь окончания предыдущего запроса!")

@router.message(F.text == "🧾 Мои подписки")
async def _open_subs_direct(message: Message):
    await show_subscriptions(message)

@router.message(F.text == "🔼 Обновить план")
async def _open_plans_direct(message: Message):
    await kb_upgrade(message)

@router.message(F.text & ~F.text.startswith("/"))
async def generate_answer(message: Message, state: FSMContext):
    chat_id = message.chat.id
    user_text = (message.text or "").strip()
    if not user_text:
        return

    now = time.monotonic()
    next_allowed = _next_allowed_by_chat.get(chat_id, 0.0)
    if now < next_allowed:
        seconds_left = int(next_allowed - now + 0.999)
        asyncio.create_task(show_cooldown_counter(message, seconds_left))
        return
    _next_allowed_by_chat[chat_id] = now + COOLDOWN_SECONDS

    await ensure_user(chat_id)
    allowed, msg = await can_use(await ensure_user(chat_id), "text")
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

# ---------- Фото-задачи ----------
@router.message(F.photo)
async def on_photo(message: Message, state: FSMContext):
    chat_id = message.chat.id

    now = time.monotonic()
    next_allowed = _next_allowed_by_chat.get(chat_id, 0.0)
    if now < next_allowed:
        seconds_left = int(next_allowed - now + 0.999)
        asyncio.create_task(show_cooldown_counter(message, seconds_left))
        return
    _next_allowed_by_chat[chat_id] = now + COOLDOWN_SECONDS

    await ensure_user(chat_id)
    allowed, msg = await can_use(await ensure_user(chat_id), "photo")
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
            teacher_hint = (
                "Объясняй как учитель: короткое введение, пошагово, типичные ошибки, в конце мини-проверка (2–3 вопроса). "
            )

        answer = await solve_from_image(
            image_bytes,
            hint= teacher_hint + "Распознай условие и реши задачу. Покажи формулы, вычисления и итог.",
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

# ---------- TTS & прочие callbacks ----------
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
    answer = await _last_assistant_text(chat_id)
    if not answer:
        await call.answer("Нет текста для экспорта", show_alert=True)
        return
    try:
        pdf = pdf_from_answer_text(answer, title="Разбор задачи", author="Учебный помощник")
        bi = BufferedInputFile(pdf.getvalue(), filename="razbor.pdf")
        await call.message.answer_document(document=bi, caption="📄 Экспортировано в PDF")
        await call.answer()
    except Exception as e:
        await call.answer(f"Ошибка экспорта: {e}", show_alert=True)

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
        # просто отправляем markdown версию
        await call.message.answer(f"🧠 Мини-тест\n\n{md}")
    except Exception as e:
        await call.message.answer(f"❌ Не удалось построить тест: {e}")

# Апселл-замочки
@router.callback_query(F.data.in_(("need_pro_pdf","need_pro_quiz")))
async def cb_need_pro(call: CallbackQuery):
    await call.answer("Функция доступна только в PRO.", show_alert=True)
    await call.message.answer("Оформите PRO, чтобы открыть PDF и мини-тест:", reply_markup=plans_kb(show_back=False))

# ---------- Вспомогательное: отправить TTS по тексту ----------
async def _send_tts_for_text(message: Message, text: str):
    """Режем на части и шлём voice .ogg (Opus) с учётом профиля голоса (имя + скорость)."""
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
