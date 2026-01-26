import os
import hmac
import hashlib
import json
import datetime as dt
from typing import Any, Dict, Optional, Tuple

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

from db import (
    payment_create,
    payment_set_status,
    payment_mark_processed,
    payment_get,
    payment_find_by_external_id,
    set_subscription,
)

# -----------------------------
# Settings
# -----------------------------
USE_TRIBUTE = os.getenv("USE_TRIBUTE", "false").lower() == "true"
NOTIFY_ON_PAYMENT = os.getenv("NOTIFY_ON_PAYMENT", "true").lower() == "true"

PAYSHARK_WEBHOOK_SECRET = os.getenv("PAYSHARK_WEBHOOK_SECRET", "").strip()

LITE_PRICE = float(os.getenv("LITE_PRICE") or os.getenv("TRIBUTE_LITE_PRICE", "200"))
PRO_PRICE = float(os.getenv("PRO_PRICE") or os.getenv("TRIBUTE_PRO_PRICE", "300"))

app = FastAPI()


def _now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _safe_json_loads(raw: bytes) -> Dict[str, Any]:
    try:
        obj = json.loads(raw.decode("utf-8"))
        return obj if isinstance(obj, dict) else {"_": obj}
    except Exception:
        return {}


def _hmac_sha256_hex(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _consteq(a: str, b: str) -> bool:
    try:
        return hmac.compare_digest(a.strip(), b.strip())
    except Exception:
        return False


def _get(obj: Any, path: str) -> Any:
    """Get nested values by dot path: 'data.payment.id'."""
    cur = obj
    for part in path.split("."):
        if cur is None:
            return None
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def _first(*vals: Any) -> Any:
    for v in vals:
        if v is None:
            continue
        if isinstance(v, str) and not v.strip():
            continue
        return v
    return None


def _parse_int(v: Any) -> Optional[int]:
    try:
        if v is None:
            return None
        if isinstance(v, bool):
            return None
        return int(str(v).strip())
    except Exception:
        return None


def _parse_float(v: Any) -> Optional[float]:
    try:
        if v is None:
            return None
        return float(str(v).replace(",", ".").strip())
    except Exception:
        return None


# -----------------------------
# DB compatibility helpers
# -----------------------------
async def get_payment(order_id: str) -> Optional[Dict[str, Any]]:
    p = await payment_get(order_id)
    if p:
        return p
    return await payment_find_by_external_id(order_id)


async def mark_payment_status(
    pay_id: str,
    status: str,
    payment_id: Optional[str] = None,
    raw: Optional[Dict[str, Any]] = None,
) -> None:
    await payment_set_status(pay_id, status=status, raw_event=raw, external_id=payment_id)


async def grant_paid_access(
    chat_id: int,
    plan: str,
    source: str = "payshark",
    payment_id: Optional[str] = None,
    order_id: Optional[str] = None,
    amount: Optional[float] = None,
    currency: Optional[str] = None,
    raw: Optional[Dict[str, Any]] = None,
) -> None:
    pay_key = str(order_id or payment_id or f"{chat_id}:{plan}")

    cur = await payment_get(pay_key)
    if cur and cur.get("processed") is True:
        return

    if not cur:
        await payment_create(
            pay_id=pay_key,
            chat_id=int(chat_id),
            plan=str(plan),
            amount=float(amount or 0.0),
            currency=str(currency or "RUB"),
            provider=str(source or "payshark"),
            raw_create=raw,
        )

    await payment_set_status(
        pay_key,
        status="paid",
        raw_event=raw,
        external_id=order_id or payment_id,
    )

    # Активируем подписку (days берётся по дефолту из db.py)
    await set_subscription(int(chat_id), plan=str(plan))  # type: ignore[arg-type]

    await payment_mark_processed(pay_key)


# -----------------------------
# Extraction
# -----------------------------
def _extract_chat_and_plan(payload: Dict[str, Any]) -> Tuple[Optional[int], Optional[str]]:
    """Best-effort extraction of chat_id and plan from a webhook payload."""
    meta = _first(
        payload.get("meta"),
        payload.get("metadata"),
        _get(payload, "data.meta"),
        _get(payload, "data.metadata"),
        _get(payload, "data.payment.meta"),
        _get(payload, "data.payment.metadata"),
        _get(payload, "payment.meta"),
        _get(payload, "payment.metadata"),
    )
    if not isinstance(meta, dict):
        meta = {}

    chat_id = _parse_int(
        _first(
            meta.get("chat_id"),
            meta.get("telegram_chat_id"),
            meta.get("telegram_id"),
            meta.get("user_id"),
            meta.get("client_id"),
            payload.get("chat_id"),
            payload.get("user_id"),
            payload.get("client_id"),
            _get(payload, "data.client_id"),
            _get(payload, "data.payment.client_id"),
            _get(payload, "data.user.client_id"),
            _get(payload, "data.chat_id"),
            _get(payload, "data.user.chat_id"),
            _get(payload, "data.user.telegram_id"),
        )
    )

    plan = _first(
        meta.get("plan"),
        meta.get("tariff"),
        meta.get("package"),
        payload.get("plan"),
        _get(payload, "data.plan"),
        _get(payload, "data.tariff"),
    )
    if isinstance(plan, str):
        plan = plan.strip().lower()
        if plan in {"lite", "pro"}:
            return chat_id, plan

    # fallback: try parse from description-like fields
    desc = _first(
        meta.get("description"),
        payload.get("description"),
        payload.get("comment"),
        _get(payload, "data.description"),
        _get(payload, "data.comment"),
        _get(payload, "data.payment.description"),
    )
    if isinstance(desc, str):
        d = desc.lower()
        import re

        m = re.search(r"(chat[_-]?id)\s*[:=]\s*(\d{4,15})", d)
        if not chat_id and m:
            chat_id = _parse_int(m.group(2))
        if "plan=pro" in d or "tariff=pro" in d or " pro " in d:
            plan = "pro"
        if "plan=lite" in d or "tariff=lite" in d or " lite " in d:
            plan = "lite"

    if isinstance(plan, str) and plan in {"lite", "pro"}:
        return chat_id, plan

    return chat_id, None


def _extract_payment_ids(payload: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    payment_id = _first(
        payload.get("payment_id"),
        payload.get("id"),
        _get(payload, "data.id"),
        _get(payload, "data.payment_id"),
        _get(payload, "data.payment.id"),
        _get(payload, "payment.id"),
        _get(payload, "payment.payment_id"),
        _get(payload, "invoice.id"),
        _get(payload, "invoice_id"),
    )
    order_id = _first(
        payload.get("order_id"),
        payload.get("merchant_order_id"),
        payload.get("external_id"),
        _get(payload, "data.order_id"),
        _get(payload, "data.external_id"),
        _get(payload, "data.payment.order_id"),
        _get(payload, "data.payment.external_id"),
        _get(payload, "payment.order_id"),
        _get(payload, "payment.external_id"),
    )
    return (str(payment_id) if payment_id is not None else None, str(order_id) if order_id is not None else None)


def _extract_amount_currency(payload: Dict[str, Any]) -> Tuple[Optional[float], Optional[str]]:
    amount = _parse_float(
        _first(
            payload.get("amount"),
            _get(payload, "data.amount"),
            _get(payload, "data.payment.amount"),
            _get(payload, "payment.amount"),
            _get(payload, "invoice.amount"),
        )
    )
    currency = _first(
        payload.get("currency"),
        _get(payload, "data.currency"),
        _get(payload, "data.payment.currency"),
        _get(payload, "payment.currency"),
        _get(payload, "invoice.currency"),
    )
    return amount, (str(currency) if currency is not None else None)


def _is_paid(payload: Dict[str, Any]) -> bool:
    event = _first(payload.get("event"), payload.get("type"), payload.get("action"), _get(payload, "data.event"))
    status = _first(
        payload.get("status"),
        _get(payload, "data.status"),
        _get(payload, "data.payment.status"),
        _get(payload, "payment.status"),
        _get(payload, "invoice.status"),
    )
    s = ""
    if isinstance(event, str):
        s += " " + event.lower()
    if isinstance(status, str):
        s += " " + status.lower()

    paid_markers = {"paid", "success", "succeeded", "completed", "finished", "confirmed", "ok"}
    return any(m in s for m in paid_markers)


def _verify_signature_if_possible(request: Request, body: bytes) -> None:
    if not PAYSHARK_WEBHOOK_SECRET:
        return

    sig = _first(
        request.headers.get("x-payshark-signature"),
        request.headers.get("payshark-signature"),
        request.headers.get("x-signature"),
        request.headers.get("x-webhook-signature"),
    )
    if not sig:
        return

    expected_hex = _hmac_sha256_hex(PAYSHARK_WEBHOOK_SECRET, body)

    if isinstance(sig, str) and sig.lower().startswith("sha256="):
        sig = sig.split("=", 1)[1]

    if not _consteq(expected_hex, str(sig)):
        raise HTTPException(status_code=401, detail="Invalid signature")


# -----------------------------
# Routes
# -----------------------------
@app.get("/health")
async def health() -> Dict[str, Any]:
    return {"ok": True, "ts": _now_utc().isoformat()}


@app.post("/payshark/webhook")
async def payshark_webhook(request: Request) -> JSONResponse:
    raw_body = await request.body()
    payload = _safe_json_loads(raw_body)

    _verify_signature_if_possible(request, raw_body)

    payment_id, order_id = _extract_payment_ids(payload)
    amount, currency = _extract_amount_currency(payload)
    chat_id, plan = _extract_chat_and_plan(payload)

    # If plan is absent, try infer from amount
    if plan is None and amount is not None:
        if abs(amount - LITE_PRICE) < 0.0001:
            plan = "lite"
        elif abs(amount - PRO_PRICE) < 0.0001:
            plan = "pro"

    if not chat_id:
        # try lookup from our payments collection by order_id
        if order_id:
            p = await get_payment(order_id)
            if p and p.get("chat_id"):
                chat_id = int(p["chat_id"])
                if not plan and p.get("plan"):
                    plan = str(p["plan"]).lower()

    if not chat_id:
        await mark_payment_status(order_id or payment_id or "unknown", status="bad_payload", payment_id=payment_id, raw=payload)
        raise HTTPException(status_code=400, detail="chat_id is missing in webhook payload")

    if plan not in {"lite", "pro"}:
        await mark_payment_status(order_id or payment_id or "unknown", status="bad_payload", payment_id=payment_id, raw=payload)
        raise HTTPException(status_code=400, detail="plan is missing in webhook payload (lite/pro)")

    paid = _is_paid(payload)
    if not paid:
        await mark_payment_status(order_id or payment_id or "unknown", status="not_paid", payment_id=payment_id, raw=payload)
        return JSONResponse({"ok": True, "received": True, "paid": False})

    await grant_paid_access(
        chat_id=chat_id,
        plan=plan,
        source="payshark",
        payment_id=payment_id,
        order_id=order_id,
        amount=amount,
        currency=currency,
        raw=payload,
    )

    # Optional notify user in Telegram
    if NOTIFY_ON_PAYMENT:
        bot = getattr(app.state, "bot", None)
        if bot:
            try:
                txt = "✅ Оплата получена. Подписка LITE активирована на 30 дней." if plan == "lite" else "✅ Оплата получена. Подписка PRO активирована на 30 дней."
                await bot.send_message(chat_id, txt)
            except Exception:
                pass

    return JSONResponse({"ok": True})


# -----------------------------
# Legacy Tribute (optional)
# -----------------------------
if USE_TRIBUTE:

    @app.post("/tribute/webhook")
    async def tribute_webhook(request: Request) -> JSONResponse:
        try:
            payload = await request.json()
        except Exception:
            payload = {}

        if not isinstance(payload, dict):
            payload = {"_": payload}

        event = str(payload.get("event") or payload.get("type") or "").lower()
        status = str(payload.get("status") or "").lower()

        is_paid = ("paid" in event) or ("success" in event) or (status in {"paid", "success", "succeeded"})
        if not is_paid:
            return JSONResponse({"ok": True, "paid": False})

        user_id = payload.get("user_id") or payload.get("chat_id")
        plan = payload.get("plan") or payload.get("tariff")
        try:
            user_id = int(user_id)
        except Exception:
            raise HTTPException(status_code=400, detail="user_id is missing")

        plan = str(plan or "lite").lower()
        if plan not in {"lite", "pro"}:
            plan = "lite"

        await set_subscription(user_id, plan=plan)  # days default in db
        return JSONResponse({"ok": True, "paid": True})
