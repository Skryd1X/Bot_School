# handlers.py
import os
import asyncio
import time
from io import BytesIO
from typing import Dict, List, Optional

from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.filters import CommandStart, StateFilter, Command
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramRetryAfter, TelegramBadRequest
from aiogram.enums import ChatAction

from generators import stream_response_text, solve_from_image
from db import ensure_user, can_use, inc_usage, get_status_text  # лимиты / статус

router = Router()

# ---------- Константы/окружение ----------
COOLDOWN_SECONDS   = 5
MIN_INTERVAL_SEND  = 1.1
MIN_EDIT_INTERVAL  = 0.25
MAX_TURNS          = 12
MAX_TG_LEN         = 4096

TRIBUTE_LITE_STARTAPP = os.getenv("TRIBUTE_LITE_STARTAPP", "")
TRIBUTE_PRO_STARTAPP  = os.getenv("TRIBUTE_PRO_STARTAPP", "")
TRIBUTE_LITE_PRICE    = os.getenv("TRIBUTE_LITE_PRICE", "200")
TRIBUTE_PRO_PRICE     = os.getenv("TRIBUTE_PRO_PRICE", "300")

def tribute_url(code: str) -> str:
    return f"https://t.me/tribute/app?startapp={code}"

# Меню «Доступные пакеты»
def plans_kb(show_back: bool = False) -> InlineKeyboardMarkup:
    row = [
        InlineKeyboardButton(text=f"🪙 LITE {TRIBUTE_LITE_PRICE} ₽", url=tribute_url(TRIBUTE_LITE_STARTAPP)),
        InlineKeyboardButton(text=f"🚀 PRO {TRIBUTE_PRO_PRICE} ₽",  url=tribute_url(TRIBUTE_PRO_STARTAPP)),
    ]
    kb: list[list[InlineKeyboardButton]] = [row]
    if show_back:
        kb.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_subs")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

# Кнопка «Доступные пакеты» под статусом
def available_btn_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="📦 Доступные пакеты", callback_data="show_plans")]]
    )

# Постоянная нижняя Reply-клавиатура
MAIN_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🧾 Мои подписки"), KeyboardButton(text="🧹 Сброс")],
    ],
    resize_keyboard=True,
    is_persistent=True,
    input_field_placeholder="Напишите вопрос или пришлите фото…",
)

# ---------- Память диалога ----------
_last_send_ts: Dict[int, float] = {}
_next_allowed_by_chat: Dict[int, float] = {}
HISTORY: Dict[int, List[Dict[str, str]]] = {}  # chat_id -> [{role, content}...]

def _remember(chat_id: int, role: str, content: str):
    hist = HISTORY.setdefault(chat_id, [])
    hist.append({"role": role, "content": content})
    if len(hist) > MAX_TURNS * 2:
        HISTORY[chat_id] = hist[-MAX_TURNS * 2 :]

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
        if "Too Many Requests" in str(e) or "Flood control exceeded" in str(e):
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
        await message.answer("Пустой ответ 😕", reply_markup=MAIN_KB)
        return
    for i in range(0, len(text), MAX_TG_LEN):
        await message.answer(text[i:i+MAX_TG_LEN], reply_markup=MAIN_KB if i + MAX_TG_LEN >= len(text) else None)

# ---------- Экран «Мои подписки» ----------
async def show_subscriptions(message: Message):
    """Показывает статус. Для LITE добавляет кнопку 'Доступные пакеты'. Для PRO — без кнопок.
       Для FREE — сразу выводит меню покупки LITE/PRO."""
    text = await get_status_text(message.chat.id)

    # Грубая эвристика по тексту статуса:
    low = text.lower()
    if "план: free" in low:
        # FREE — предлагаем пакеты
        await message.answer(text, reply_markup=plans_kb(show_back=False))
    elif "план: lite" in low:
        # LITE — показать апгрейд
        text2 = text + "\n\n⬆️ Доступно обновление до PRO для безлимита и приоритета."
        await message.answer(text2, reply_markup=available_btn_kb())
    else:
        # PRO — просто статус
        await message.answer(text, reply_markup=MAIN_KB)

# ---------- Команды/кнопки ----------
@router.message(CommandStart())
async def cmd_start(message: Message):
    await ensure_user(message.chat.id)
    # Покажем приветствие и актуальный статус
    await message.answer(
        "👋 Привет! Я помощник для школьных задач.\n"
        "Пиши вопрос или пришли фото — решу по шагам.",
        reply_markup=MAIN_KB
    )
    # Сразу покажем экран подписок (он сам разрулит FREE/LITE/PRO)
    await show_subscriptions(message)

@router.message(Command("plan"))
async def cmd_plan(message: Message):
    await message.answer("Доступные пакеты:", reply_markup=plans_kb(show_back=True))

@router.message(Command("status"))
async def cmd_status(message: Message):
    await show_subscriptions(message)

@router.message(Command("reset"))
async def cmd_reset(message: Message):
    HISTORY.pop(message.chat.id, None)
    await message.answer("🧹 Контекст очищен", reply_markup=MAIN_KB)

# Нажатия по нижней Reply-клавиатуре
@router.message(F.text == "🧾 Мои подписки")
async def kb_subs(message: Message):
    await show_subscriptions(message)

@router.message(F.text == "🧹 Сброс")
async def kb_reset(message: Message, state: FSMContext):
    await state.clear()
    await cmd_reset(message)

# Callback-кнопки под статусом
@router.callback_query(F.data == "show_plans")
async def cb_show_plans(call: CallbackQuery):
    await call.message.edit_text("Доступные пакеты:", reply_markup=plans_kb(show_back=True))
    await call.answer()

@router.callback_query(F.data == "back_to_subs")
async def cb_back_to_subs(call: CallbackQuery):
    # перерисуем статус в том же сообщении
    text = await get_status_text(call.message.chat.id)
    kb: Optional[InlineKeyboardMarkup] = None
    low = text.lower()
    if "план: lite" in low:
        text += "\n\n⬆️ Доступно обновление до PRO для безлимита и приоритета."
        kb = available_btn_kb()
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()

# ---------- Генерация текста ----------
@router.message(StateFilter('generating'))
async def wait_response(message: Message):
    await safe_send(message, "⏳ Ответ генерируется... дождитесь окончания предыдущего запроса!")

# не перехватываем команды
@router.message(F.text & ~F.text.startswith("/"))
async def generate_answer(message: Message, state: FSMContext):
    chat_id = message.chat.id
    user_text = (message.text or "").strip()
    if not user_text:
        return

    # антиспам
    now = time.monotonic()
    next_allowed = _next_allowed_by_chat.get(chat_id, 0.0)
    if now < next_allowed:
        seconds_left = int(next_allowed - now + 0.999)
        asyncio.create_task(show_cooldown_counter(message, seconds_left))
        return
    _next_allowed_by_chat[chat_id] = now + COOLDOWN_SECONDS

    # учёт лимитов
    await ensure_user(chat_id)
    allowed, msg = await can_use(await ensure_user(chat_id), "text")
    if not allowed:
        await message.answer(msg, reply_markup=plans_kb(show_back=True))
        return

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
        history = HISTORY.get(chat_id, [])
        async for delta in stream_response_text(user_text, history):
            accumulated += delta
            t = asyncio.get_event_loop().time()
            if t - last_edit >= MIN_EDIT_INTERVAL:
                await safe_edit(message, draft.message_id, accumulated or "…")
                last_edit = t

        if accumulated:
            if len(accumulated) > MAX_TG_LEN:
                await safe_delete(draft)
                await send_long_text(message, accumulated)
            else:
                await safe_edit(message, draft.message_id, accumulated)
        else:
            await safe_edit(message, draft.message_id, "Пустой ответ 😕")

        _remember(chat_id, "user", user_text)
        _remember(chat_id, "assistant", accumulated or "")
        await inc_usage(chat_id, "text")

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

        answer = await solve_from_image(
            image_bytes,
            hint="Распознай условие и реши задачу. Покажи формулы, вычисления и итог.",
            history=HISTORY.get(chat_id, [])
        )

        if answer and len(answer) > MAX_TG_LEN:
            await safe_delete(draft)
            await send_long_text(message, answer)
        else:
            await safe_edit(message, draft.message_id, answer or "Не удалось распознать задачу.")

        _remember(chat_id, "user", "[Фото задачи]")
        _remember(chat_id, "assistant", answer or "")
        await inc_usage(chat_id, "photo")

    except Exception as e:
        await safe_edit(message, draft.message_id, f"❌ Ошибка по фото: {e}")

    finally:
        await state.clear()
