# webhooks.py
import os
import json
import logging
from typing import Any, Dict, Optional, Tuple

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

import httpx

from db import set_subscription, db, ensure_user  # db для идемпотентности/миграций

app = FastAPI()
log = logging.getLogger("tribute")

# ------------ ENV ------------
TRIBUTE_API_KEY        = os.getenv("TRIBUTE_API_KEY", "")
TRIBUTE_LITE_STARTAPP  = os.getenv("TRIBUTE_LITE_STARTAPP", "")  # код из кнопки LITE
TRIBUTE_PRO_STARTAPP   = os.getenv("TRIBUTE_PRO_STARTAPP", "")   # код из кнопки PRO
SUBSCRIPTION_DAYS      = int(os.getenv("SUBSCRIPTION_DAYS", "30"))

BOT_TOKEN              = os.getenv("BOT_TOKEN", "")
NOTIFY_ON_PAYMENT      = os.getenv("NOTIFY_ON_PAYMENT", "false").lower() == "true"

# Необязательная резервная карта распознавания по сумме (если Tribute не шлет startapp/title)
# Пример: "284.00" -> "pro", "200.00" -> "lite"
AMOUNT_PLAN_MAP_RAW = os.getenv("AMOUNT_PLAN_MAP", "")  # формат: pro=284;lite=200
AMOUNT_PLAN_MAP: Dict[str, float] = {}
for pair in AMOUNT_PLAN_MAP_RAW.split(";"):
    if "=" in pair:
        k, v = pair.split("=", 1)
        try:
            AMOUNT_PLAN_MAP[k.strip().lower()] = float(v)
        except Exception:
            pass

# коллекция для защиты от повторной обработки одного и того же события
payments = db["payments"]  # _id = event_id/payment_id


# ------------ helpers ------------
def _ok(payload: dict | None = None):
    return JSONResponse({"ok": True, **(payload or {})})

def _bad(msg: str, code: int = 400):
    raise HTTPException(status_code=code, detail=msg)

def _bool(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    return s in {"1", "true", "yes", "y", "on"}

def _to_int(v: Any) -> Optional[int]:
    try:
        return int(v)
    except Exception:
        return None

def _get_api_key(req: Request, body: Dict[str, Any]) -> Optional[str]:
    return (
        req.headers.get("X-Api-Key")
        or req.headers.get("x-tribute-api-key")
        or req.query_params.get("key")
        or body.get("key")
    )

def _deep_get(d: Dict[str, Any], *path, default=None):
    cur = d
    for p in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(p)
    return cur if cur is not None else default

def extract_chat_id(payload: Dict[str, Any]) -> Optional[int]:
    """
    Пытаемся достать Telegram user id из разных мест.
    Tribute/посредники могут прислать:
      telegram_user_id / telegram_id / user_id / payer_id / sender_id /
      from.id / buyer.telegram_id / customer.telegram_id / user.id
    """
    candidates: Tuple[Any, ...] = (
        payload.get("telegram_user_id"),
        payload.get("telegram_id"),
        payload.get("user_id"),
        payload.get("payer_id"),
        payload.get("sender_id"),
        _deep_get(payload, "from", "id"),
        _deep_get(payload, "buyer", "telegram_id"),
        _deep_get(payload, "customer", "telegram_id"),
        _deep_get(payload, "user", "id"),
        _deep_get(payload, "payment", "telegram_user_id"),
    )
    for v in candidates:
        cid = _to_int(v)
        if cid:
            return cid
    return None

def detect_plan_and_days(payload: Dict[str, Any]) -> Optional[Tuple[str, int]]:
    """
    Пытаемся понять, что купили: LITE или PRO и на сколько дней.
    Источники:
      - metadata.plan / metadata.days
      - явные поля plan/days
      - product.title / product.id / product.code
      - title / product_id / startapp
      - резерв по сумме (AMOUNT_PLAN_MAP)
    """
    meta = payload.get("metadata") or {}
    plan = (payload.get("plan") or meta.get("plan") or "").lower()
    days = int(payload.get("days") or meta.get("days") or SUBSCRIPTION_DAYS)

    startapp = (payload.get("startapp")
                or _deep_get(payload, "product", "startapp")
                or _deep_get(payload, "product", "code") or "").strip().lower()

    title = (payload.get("title") or meta.get("title")
             or _deep_get(payload, "product", "title") or "").lower()

    product_id = str(payload.get("product_id")
                     or meta.get("product_id")
                     or _deep_get(payload, "product", "id") or "")

    amount = payload.get("amount") or _deep_get(payload, "payment", "amount") or 0
    try:
        amount = float(amount)
    except Exception:
        amount = 0.0

    # 1) если явно прислали plan
    if plan in ("lite", "pro"):
        return plan, days

    # 2) по startapp
    if startapp:
        if TRIBUTE_PRO_STARTAPP and startapp == TRIBUTE_PRO_STARTAPP.lower():
            return "pro", days
        if TRIBUTE_LITE_STARTAPP and startapp == TRIBUTE_LITE_STARTAPP.lower():
            return "lite", days

    # 3) по названию/ID продукта
    if "pro" in title or product_id.lower().endswith("pro"):
        return "pro", days
    if "lite" in title or product_id.lower().endswith("lite"):
        return "lite", days

    # 4) резерв по сумме (если задана карта)
    if AMOUNT_PLAN_MAP:
        # ищем ближайшее совпадение по округленной сумме
        for p, a in AMOUNT_PLAN_MAP.items():
            if abs(amount - a) < 0.01:
                if p in ("lite", "pro"):
                    return p, days

    return None

def extract_event_fields(data: Dict[str, Any]):
    """
    Универсальный парсер полей из разных форматов Tribute.
    Возвращает:
      event_id, is_test, paid, amount, currency, raw_payload
    """
    is_test = _bool(data.get("test")) or data.get("mode") in {"test", "sandbox"}

    event_id = (
        data.get("id")
        or data.get("event_id")
        or _deep_get(data, "payment", "id")
        or _deep_get(data, "invoice", "id")
    )

    payment = data.get("payment") or {}
    invoice = data.get("invoice") or {}

    status = (data.get("status")
              or payment.get("status")
              or invoice.get("status") or "").lower()

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

    currency = (data.get("currency")
                or payment.get("currency")
                or invoice.get("currency") or "").upper()

    return str(event_id) if event_id else None, is_test, paid, amount, currency, data


async def _notify_user(chat_id: int, text: str):
    """Оповещение пользователя через Bot API (если включено NOTIFY_ON_PAYMENT)."""
    if not (NOTIFY_ON_PAYMENT and BOT_TOKEN and chat_id):
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": chat_id, "text": text, "disable_web_page_preview": True}
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            await client.post(url, data=data)
    except Exception as e:
        log.warning("notify fail: %s", e)


# ------------ endpoints ------------
@app.get("/")
async def root_ok():
    return _ok({"service": "tribute-webhook", "status": "alive"})

@app.get("/webhook/tribute")
async def tribute_ping():
    """Пинг для тестовой кнопки в Tribute/NGROK."""
    return _ok({"ping": True})

@app.post("/webhook/tribute")
async def tribute_webhook(request: Request):
    # 1) Читаем JSON заранее, т.к. ключ может лежать в теле
    try:
        body = await request.json()
    except Exception:
        _bad("invalid json")

    # 2) Проверка API-ключа
    key = _get_api_key(request, body)
    if TRIBUTE_API_KEY and key != TRIBUTE_API_KEY:
        _bad("bad api key", 401)

    # 3) Лог
    log.info("Tribute webhook payload: %s", json.dumps(body, ensure_ascii=False))

    # 4) Извлекаем базовые поля
    event_id, is_test, paid, amount, currency, raw = extract_event_fields(body)
    if is_test or body.get("event") in {"test", "ping"}:
        return _ok({"ignored": "test"})

    if not paid:
        return _ok({"ignored": "not_paid"})
    if amount <= 0:
        return _ok({"ignored": "zero_amount"})

    # 5) Идемпотентность — один event обрабатываем один раз
    if event_id:
        res = await payments.update_one(
            {"_id": event_id},
            {"$setOnInsert": {"raw": raw, "processed_at": None}},
            upsert=True,
        )
        if not res.upserted_id:
            return _ok({"dup": True})

    # 6) Пытаемся узнать chat_id и план
    chat_id = extract_chat_id(body)
    if not chat_id:
        _bad("telegram_user_id missing")

    plan_days = detect_plan_and_days(body)
    if not plan_days:
        return _ok({"ignored": "cannot_detect_plan"})

    plan, days = plan_days

    # 7) Применяем подписку
    await ensure_user(chat_id)
    await set_subscription(chat_id, plan, days=days)

    # 8) Оповещение (по желанию)
    if plan == "pro":
        text = f"⭐️ Спасибо за покупку PRO на {days} дн! Безлимит и приоритет включены."
    else:
        text = f"✅ Спасибо за покупку LITE на {days} дн!"
    await _notify_user(chat_id, text)

    # 9) Закрываем идемпотентность
    if event_id:
        await payments.update_one({"_id": event_id}, {"$set": {"processed_at": True, "plan": plan}})

    return _ok({"plan": plan, "days": days, "chat_id": chat_id})
