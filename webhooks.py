# webhooks.py
# FastAPI + Telegram webhook (aiogram v3) + Tribute webhook.
# Без "незакрытых сессий" благодаря lifespan.

import os
import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

from aiogram import Bot, Dispatcher
from aiogram.types import Update
from aiogram.client.session.aiohttp import AiohttpSession

from db import set_subscription, db
from handlers import router as handlers_router

log = logging.getLogger("webhooks")

# ---------- ENV ----------
BOT_TOKEN             = os.getenv("BOT_TOKEN", "")
PUBLIC_BASE_URL       = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")  # https://<app>.onrender.com
TELEGRAM_WEBHOOK_PATH = os.getenv("TELEGRAM_WEBHOOK_PATH", "/webhook/telegram")
TELEGRAM_SECRET_TOKEN = os.getenv("TELEGRAM_WEBHOOK_SECRET", "change-me-please")

TRIBUTE_API_KEY       = os.getenv("TRIBUTE_API_KEY", "")
TRIBUTE_LITE_STARTAPP = os.getenv("TRIBUTE_LITE_STARTAPP", "")
TRIBUTE_PRO_STARTAPP  = os.getenv("TRIBUTE_PRO_STARTAPP", "")
SUBSCRIPTION_DAYS     = int(os.getenv("SUBSCRIPTION_DAYS", "30"))

NOTIFY_ON_PAYMENT     = os.getenv("NOTIFY_ON_PAYMENT", "false").lower() == "true"

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

payments = db["payments"]  # идемпотентность

# ---------- helpers ----------
def _ok(payload: dict | None = None):
    return JSONResponse({"ok": True, **(payload or {})})

def _bad(msg: str, code: int = 400):
    raise HTTPException(status_code=code, detail=msg)

def _get_api_key(req: Request) -> str | None:
    return (
        req.headers.get("X-Api-Key")
        or req.headers.get("x-tribute-api-key")
        or req.query_params.get("key")
    )

def _bool(v):
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    return s in {"1", "true", "yes", "y", "on"}

def _extract(data: dict):
    """
    Универсальный парсер Tribute: возвращает
    event_id, is_test, status, paid, amount, currency, startapp, telegram_user_id
    """
    is_test = _bool(data.get("test")) or data.get("mode") in {"test", "sandbox"}

    event_id = (
        data.get("id")
        or data.get("event_id")
        or data.get("payment", {}).get("id")
        or data.get("invoice", {}).get("id")
    )

    payment = data.get("payment", {})
    invoice = data.get("invoice", {})
    product = data.get("product", {})

    status = (data.get("status") or payment.get("status") or invoice.get("status") or "").lower()

    paid = (
        _bool(data.get("paid"))
        or _bool(payment.get("paid"))
        or status in {"succeeded", "success", "paid", "completed"}
    )

    amount = data.get("amount") or payment.get("amount") or invoice.get("amount") or 0
    try:
        amount = float(amount)
    except Exception:
        amount = 0.0

    currency = (data.get("currency") or payment.get("currency") or invoice.get("currency") or "").upper()
    startapp = (data.get("startapp") or product.get("startapp") or product.get("code") or "").strip()

    telegram_user_id = (
        data.get("telegram_user_id")
        or data.get("from_id")
        or data.get("buyer", {}).get("telegram_id")
        or data.get("user", {}).get("id")
        or payment.get("telegram_user_id")
    )

    return event_id, is_test, status, paid, amount, currency, startapp, telegram_user_id

async def _notify_user(chat_id: int, text: str):
    """Уведомление через Telegram Bot API (без aiogram) — безопасно вызывать из вебхука Tribute."""
    if not (NOTIFY_ON_PAYMENT and BOT_TOKEN):
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": text, "disable_web_page_preview": True}
    timeout = httpx.Timeout(10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            await client.post(url, data=data)
        except Exception as e:
            log.warning("notify fail: %s", e)

# ---------- lifespan: создаём/закрываем bot/dispatcher корректно ----------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # отдельная aiohttp-сессия с таймаутом (иначе может зависать)
    session = AiohttpSession(timeout=120)
    bot = Bot(token=BOT_TOKEN, session=session)
    dp = Dispatcher()
    dp.include_router(handlers_router)

    app.state.bot = bot
    app.state.dp = dp

    # ставим Telegram webhook, если PUBLIC_BASE_URL задан
    if PUBLIC_BASE_URL:
        url = f"{PUBLIC_BASE_URL}{TELEGRAM_WEBHOOK_PATH}"
        try:
            await bot.delete_webhook(drop_pending_updates=True)
            await bot.set_webhook(url=url, secret_token=TELEGRAM_SECRET_TOKEN, drop_pending_updates=True)
            me = await bot.get_me()
            log.info("Telegram webhook set to %s for @%s", url, me.username)
        except Exception as e:
            log.error("Failed to set Telegram webhook: %s", e)
            # важно: даже при ошибке старта мы всё равно закроем сессию в finally
            # пробрасываем исключение, чтобы Render увидел неуспешный деплой
            raise
    else:
        log.warning("PUBLIC_BASE_URL is not set — Telegram webhook won't be configured.")

    try:
        yield
    finally:
        # снимаем вебхук и закрываем сессию аккуратно
        try:
            await bot.delete_webhook(drop_pending_updates=False)
        except Exception:
            pass
        try:
            await bot.session.close()
        except Exception:
            pass

app = FastAPI(lifespan=lifespan)

# ---------- Health ----------
@app.get("/health")
async def health():
    return _ok({"health": "ok"})

# ---------- Telegram webhook endpoint ----------
@app.post(TELEGRAM_WEBHOOK_PATH)
async def telegram_handler(request: Request):
    # проверка секрета Telegram
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if TELEGRAM_SECRET_TOKEN and secret != TELEGRAM_SECRET_TOKEN:
        raise HTTPException(status_code=401, detail="bad telegram secret")

    data = await request.json()
    update = Update.model_validate(data)

    bot: Bot = request.app.state.bot
    dp: Dispatcher = request.app.state.dp

    await dp.feed_update(bot, update)
    return _ok()

# ---------- Tribute webhook ----------
@app.get("/webhook/tribute")
async def tribute_ping():
    return _ok({"ping": True})

@app.post("/webhook/tribute")
async def tribute_webhook(request: Request):
    # 1) api-key
    key = _get_api_key(request)
    if TRIBUTE_API_KEY and key != TRIBUTE_API_KEY:
        _bad("bad api key", 401)

    # 2) payload
    try:
        data = await request.json()
    except Exception:
        _bad("invalid json")

    log.info("Tribute webhook payload: %s", data)

    (
        event_id, is_test, status, paid, amount, currency,
        startapp, telegram_user_id
    ) = _extract(data)

    # 3) тесты/пинги
    if is_test or data.get("event") in {"test", "ping"}:
        return _ok({"ignored": "test"})

    # 4) признаём только реальную оплату
    if not paid:
        return _ok({"ignored": "not_paid"})
    if amount <= 0:
        return _ok({"ignored": "zero_amount"})
    if not telegram_user_id:
        _bad("telegram_user_id missing")

    # 5) идемпотентность
    if event_id:
        res = await payments.update_one(
            {"_id": str(event_id)},
            {"$setOnInsert": {"raw": data, "processed_at": None}},
            upsert=True,
        )
        if not res.upserted_id:
            return _ok({"dup": True})

    # 6) применяем подписку
    chat_id = int(telegram_user_id)
    plan = None
    if startapp == TRIBUTE_LITE_STARTAPP:
        await set_subscription(chat_id, "lite", days=SUBSCRIPTION_DAYS)
        plan = "lite"
        await _notify_user(chat_id, "✅ LITE активирован на 30 дней. Приятной учёбы!")
    elif startapp == TRIBUTE_PRO_STARTAPP:
        await set_subscription(chat_id, "pro", days=SUBSCRIPTION_DAYS)
        plan = "pro"
        await _notify_user(chat_id, "⭐ Спасибо за покупку PRO на 30 дней! Безлимит и приоритет включены.")
    else:
        return _ok({"ignored": "unknown_startapp", "startapp": startapp})

    if event_id:
        await payments.update_one(
            {"_id": str(event_id)},
            {"$set": {"processed_at": True, "plan": plan, "days": SUBSCRIPTION_DAYS}}
        )

    return _ok({"plan": plan, "days": SUBSCRIPTION_DAYS, "chat_id": chat_id})
