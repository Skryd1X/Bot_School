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
    ReplyKeyboardRemove,  # --- added admin ---
)
from aiogram.filters import CommandStart, StateFilter, Command
# from aiogram.filters import Text  # --- removed, not in aiogram 3.x ---
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State  # --- added admin ---
from aiogram.exceptions import TelegramRetryAfter, TelegramBadRequest
from aiogram.enums import ChatAction

from generators import stream_response_text, solve_from_image
from db import (
    ensure_user, can_use, inc_usage, get_status_text,  # лимиты / статус
    get_all_chat_ids, drop_chat, set_optin            # --- added admin ---
)

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
        [KeyboardButton(text="FAQ / Помощь")],  # ← добавлено
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
        "— Нужна справка или условия — жми «FAQ / Помощь».\n"
        "— Статус доступа и пакеты — «🧾 Мои подписки».\n"
    )

    # Приветствие + показать клавиатуру
    await message.answer(greeting, reply_markup=MAIN_KB)

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
    await message.answer(
        "📘 Как пользоваться ботом:\n\n"
        "1) Отправьте фото задачи → бот даст пошаговый разбор.\n"
        "2) Можно вводить текстом — бот тоже понимает.\n"
        "3) Расширенные функции доступны после оплаты внутри бота."
    )

@router.message(F.text == "Частые вопросы")
async def faq_questions(message: Message):
    await message.answer(
        "❓ Частые вопросы:\n\n"
        "• Можно ли вернуть деньги?\n"
        "  Оплаченные услуги возврату не подлежат, поскольку оплата осуществляется добровольно, "
        "а Пользователь до момента приобретения имел возможность ознакомиться с содержанием и "
        "условиями предоставляемой услуги.\n\n"
        "• Как происходит оплата?\n"
        "  Оплата осуществляется добровольно через доступные в боте способы.\n\n"
        "• Что делает бот?\n"
        "  Помогает с разбором учебных задач и пояснениями по шагам, но не заменяет преподавателя."
    )

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
    # длинный текст аккуратно отправим кусками
    if len(offer_text) > MAX_TG_LEN:
        await send_long_text(message, offer_text)
    else:
        await message.answer(offer_text)

@router.message(F.text == "Назад")
async def faq_back(message: Message):
    await message.answer("Возврат в главное меню", reply_markup=MAIN_KB)

# ---------- Admin panel: вход по секретному коду, рассылки ----------

# Хранилище админов (до 2-х), доступ по секретному коду из .env
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

# Секретный вход (сообщение целиком равно секретному коду)
@router.message(lambda m: (m.text or "").strip() in SECRET_ADMIN_CODES)
async def secret_code_grant(message: Message):
    uid = message.from_user.id
    if is_admin(uid):
        return await message.answer("Вы уже в админ-режиме.", reply_markup=ADMIN_KB)

    if len(ADMINS) >= MAX_ADMINS:
        return await message.answer("Нельзя добавить нового админа — достигнут лимит (2 админа).", reply_markup=MAIN_KB)

    ADMINS.add(uid)
    _save_admins()
    await message.answer("✅ Вы добавлены как админ. Открываю админ-панель.", reply_markup=ADMIN_KB)

# Переоткрыть панель, если уже админ
@router.message(Command("admin"))
async def cmd_admin_open(message: Message):
    if not is_admin(message.from_user.id):
        return await message.answer("⛔ Доступно только админам.")
    await message.answer("Админ-панель:", reply_markup=ADMIN_KB)

# Выход из админ-режима
@router.message(F.text == "⏪ Выйти из админ режима")
async def admin_logout(message: Message):
    uid = message.from_user.id
    if is_admin(uid):
        ADMINS.discard(uid)
        _save_admins()
        await message.answer("Вы вышли из админ-режима.", reply_markup=MAIN_KB)
    else:
        await message.answer("Вы не в админ-режиме.", reply_markup=MAIN_KB)

# Подписка/отписка для пользователей (опционально; пригодится для рассылок)
@router.message(Command("unsubscribe"))
async def cmd_unsub(message: Message):
    await set_optin(message.chat.id, False)
    await message.answer("❌ Вы отписаны от рассылок. Включить снова: /subscribe")

@router.message(Command("subscribe"))
async def cmd_sub(message: Message):
    await set_optin(message.chat.id, True)
    await message.answer("✅ Вы подписаны на рассылки. Отключить: /unsubscribe")

# Состояния для рассылок
class AdminBroadcastStates(StatesGroup):
    waiting_for_text = State()
    waiting_for_photo = State()
    waiting_for_caption = State()
    confirm = State()  # --- admin confirm/progress ---

BROADCAST_CONCURRENCY = 20
BROADCAST_DELAY_SEC   = 0.03

def _progress_bar(pct: float, width: int = 12) -> str:
    """Вернёт строку прогресс-бара вида [██████----] 50%"""
    done = int(round(pct * width))
    return f"[{'█'*done}{'—'*(width-done)}] {int(pct*100)}%"

def _confirm_kb(kind: str) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения: kind='text'|'photo'"""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"bcast_confirm_{kind}"),
        InlineKeyboardButton(text="❌ Отменить",    callback_data="bcast_cancel"),
    ]])

# ---------- РАССЫЛКА ТЕКСТОМ (с подтверждением и прогрессом) ----------
@router.message(F.text == "📢 Рассылка — текст")
async def admin_broadcast_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(AdminBroadcastStates.waiting_for_text)
    await message.answer("📝 Пришлите текст рассылки (или /cancel):", reply_markup=ReplyKeyboardRemove())

@router.message(AdminBroadcastStates.waiting_for_text)
async def admin_broadcast_receive_text(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        return

    text = (message.text or "").strip()
    if not text:
        await message.answer("Пустой текст — отмена.", reply_markup=ADMIN_KB)
        await state.clear()
        return

    # Посчитаем аудиторию и спросим подтверждение
    chat_ids = await get_all_chat_ids(optin_only=True)
    await state.update_data(kind="text", text=text, audience=chat_ids)
    await state.set_state(AdminBroadcastStates.confirm)
    await message.answer(
        f"Будет отправлено *текстовое* сообщение {len(chat_ids)} получателям.\nПодтверждаете?",
        reply_markup=_confirm_kb("text"),
        parse_mode="Markdown"
    )

# ---------- РАССЫЛКА ФОТО (с подтверждением и прогрессом) ----------
@router.message(F.text == "🖼️ Рассылка — фото")
async def admin_broadcast_photo_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(AdminBroadcastStates.waiting_for_photo)
    await message.answer("🖼️ Пришлите фото (файл/URL/file_id) для рассылки, или /cancel:", reply_markup=ReplyKeyboardRemove())

@router.message(AdminBroadcastStates.waiting_for_photo)
async def admin_broadcast_photo_received(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        return

    photo_file_id = None
    if message.photo:
        photo_file_id = message.photo[-1].file_id
    else:
        txt = (message.text or "").strip()
        if txt:
            photo_file_id = txt  # URL или file_id

    if not photo_file_id:
        await message.answer("Не распознано фото/URL. Отмена.", reply_markup=ADMIN_KB)
        await state.clear()
        return

    # Спросим подпись
    await state.update_data(photo_file_id=photo_file_id)
    await state.set_state(AdminBroadcastStates.waiting_for_caption)
    await message.answer("Пришлите подпись (или пустое сообщение, чтобы без подписи):", reply_markup=ReplyKeyboardRemove())

@router.message(AdminBroadcastStates.waiting_for_caption)
async def admin_broadcast_photo_caption(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    data = await state.get_data()
    photo_file_id = data.get("photo_file_id")
    caption = (message.text or "").strip() or None

    # Посчитаем аудиторию и спросим подтверждение
    chat_ids = await get_all_chat_ids(optin_only=True)
    await state.update_data(kind="photo", photo_file_id=photo_file_id, caption=caption, audience=chat_ids)
    await state.set_state(AdminBroadcastStates.confirm)
    await message.answer(
        f"Будет отправлено *фото* {len(chat_ids)} получателям.\nПодтверждаете?",
        reply_markup=_confirm_kb("photo"),
        parse_mode="Markdown"
    )

# ---------- Подтверждение / Отмена ----------
@router.callback_query(F.data == "bcast_cancel")
async def bcast_cancel(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return await call.answer("Нет доступа")
    await state.clear()
    await call.message.edit_text("❌ Рассылка отменена.")
    await call.message.answer("Возвращаю админ-меню.", reply_markup=ADMIN_KB)
    await call.answer()

@router.callback_query(F.data == "bcast_confirm_text")
async def bcast_confirm_text(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return await call.answer("Нет доступа")
    data = await state.get_data()
    if data.get("kind") != "text":
        return await call.answer("Нет данных для рассылки", show_alert=True)

    text: str = data["text"]
    chat_ids: List[int] = data["audience"]
    await state.clear()

    # Статусное сообщение с прогресс-баром
    total = len(chat_ids)
    sent = 0
    failed = 0
    status_msg = await call.message.edit_text(f"🚀 Старт рассылки (текст)\n{_progress_bar(0)}\n0 / {total}")
    lock = asyncio.Lock()

    sem = asyncio.Semaphore(BROADCAST_CONCURRENCY)
    last_edit_ts = time.monotonic()

    async def worker(cid: int):
        nonlocal sent, failed, last_edit_ts
        async with sem:
            try:
                await call.message.bot.send_message(cid, text)
                sent += 1
            except Exception:
                try:
                    await drop_chat(cid)
                except Exception:
                    pass
                failed += 1
            # обновление прогресса не чаще раза в 0.5 сек
            now_ts = time.monotonic()
            if now_ts - last_edit_ts >= 0.5:
                async with lock:
                    last_edit_ts = time.monotonic()
                    pct = (sent + failed) / total if total else 1.0
                    try:
                        await call.message.bot.edit_message_text(
                            chat_id=status_msg.chat.id,
                            message_id=status_msg.message_id,
                            text=f"🚀 Старт рассылки (текст)\n{_progress_bar(pct)}\n{sent+failed} / {total}"
                        )
                    except TelegramBadRequest:
                        pass
            await asyncio.sleep(BROADCAST_DELAY_SEC)

    await asyncio.gather(*(worker(cid) for cid in chat_ids))

    # финальный отчёт
    try:
        await call.message.bot.edit_message_text(
            chat_id=status_msg.chat.id,
            message_id=status_msg.message_id,
            text=f"✅ Рассылка завершена.\nВсего: {total}\nОтправлено: {sent}\nОшибок/очищено: {failed}"
        )
    except TelegramBadRequest:
        await call.message.answer(f"✅ Рассылка завершена.\nВсего: {total}\nОтправлено: {sent}\nОшибок/очищено: {failed}")
    await call.message.answer("Готово. Возвращаю админ-меню.", reply_markup=ADMIN_KB)
    await call.answer()

@router.callback_query(F.data == "bcast_confirm_photo")
async def bcast_confirm_photo(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return await call.answer("Нет доступа")
    data = await state.get_data()
    if data.get("kind") != "photo":
        return await call.answer("Нет данных для рассылки", show_alert=True)

    photo_file_id: str = data["photo_file_id"]
    caption: Optional[str] = data.get("caption")
    chat_ids: List[int] = data["audience"]
    await state.clear()

    total = len(chat_ids)
    sent = 0
    failed = 0
    status_msg = await call.message.edit_text(f"🚀 Старт рассылки (фото)\n{_progress_bar(0)}\n0 / {total}")
    lock = asyncio.Lock()

    sem = asyncio.Semaphore(BROADCAST_CONCURRENCY)
    last_edit_ts = time.monotonic()

    async def worker(cid: int):
        nonlocal sent, failed, last_edit_ts
        async with sem:
            try:
                await call.message.bot.send_photo(cid, photo=photo_file_id, caption=caption)
                sent += 1
            except Exception:
                try:
                    await drop_chat(cid)
                except Exception:
                    pass
                failed += 1
            now_ts = time.monotonic()
            if now_ts - last_edit_ts >= 0.5:
                async with lock:
                    last_edit_ts = time.monotonic()
                    pct = (sent + failed) / total if total else 1.0
                    try:
                        await call.message.bot.edit_message_text(
                            chat_id=status_msg.chat.id,
                            message_id=status_msg.message_id,
                            text=f"🚀 Старт рассылки (фото)\n{_progress_bar(pct)}\n{sent+failed} / {total}"
                        )
                    except TelegramBadRequest:
                        pass
            await asyncio.sleep(BROADCAST_DELAY_SEC)

    await asyncio.gather(*(worker(cid) for cid in chat_ids))

    # финальный отчёт
    try:
        await call.message.bot.edit_message_text(
            chat_id=status_msg.chat.id,
            message_id=status_msg.message_id,
            text=f"✅ Рассылка (фото) завершена.\nВсего: {total}\nОтправлено: {sent}\nОшибок/очищено: {failed}"
        )
    except TelegramBadRequest:
        await call.message.answer(f"✅ Рассылка (фото) завершена.\nВсего: {total}\nОтправлено: {sent}\nОшибок/очищено: {failed}")
    await call.message.answer("Готово. Возвращаю админ-меню.", reply_markup=ADMIN_KB)
    await call.answer()

@router.message(F.text == "📊 Кол-во подписчиков")
async def admin_count(message: Message):
    if not is_admin(message.from_user.id):
        return
    chat_ids = await get_all_chat_ids(optin_only=True)
    await message.answer(f"Всего подписчиков (optin=True): {len(chat_ids)}", reply_markup=ADMIN_KB)

@router.message(Command("cancel"))
async def admin_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Действие отменено.", reply_markup=ADMIN_KB if is_admin(message.from_user.id) else MAIN_KB)

# ---------- Callback-кнопки под статусом ----------
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
