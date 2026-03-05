import os
import json
import base64
import datetime as dt
from typing import Any, Dict, Optional, Tuple

import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse

from db import (
    payment_create,
    payment_set_status,
    payment_mark_processed,
    payment_get,
    payment_find_by_external_id,
    set_subscription,
)

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import load_pem_public_key

app = FastAPI()

NOTIFY_ON_PAYMENT = (os.getenv("NOTIFY_ON_PAYMENT") or "true").lower() == "true"
DEBUG_WATA_WEBHOOK = (os.getenv("DEBUG_WATA_WEBHOOK") or "true").lower() in {"1", "true", "yes", "y"}

WATA_BASE_URL = (os.getenv("WATA_BASE_URL") or "https://api.wata.pro/api/h2h").rstrip("/")
WATA_VERIFY_SIGNATURE = (os.getenv("WATA_VERIFY_SIGNATURE") or "true").lower() in {"1", "true", "yes", "y"}
WATA_PUBLIC_KEY_TTL_MIN = int(os.getenv("WATA_PUBLIC_KEY_TTL_MIN", "60"))
WATA_TIMEOUT_SEC = float(os.getenv("WATA_TIMEOUT_SEC", "60"))

LITE_PRICE = float(os.getenv("WATA_LITE_PRICE") or os.getenv("LITE_PRICE") or "200")
PRO_PRICE = float(os.getenv("WATA_PRO_PRICE") or os.getenv("PRO_PRICE") or "300")


def _now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _safe_json_loads(raw: bytes) -> Dict[str, Any]:
    try:
        obj = json.loads(raw.decode("utf-8"))
        return obj if isinstance(obj, dict) else {"_": obj}
    except Exception:
        return {}


def _parse_int(v: Any) -> Optional[int]:
    try:
        if v is None or isinstance(v, bool):
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


async def get_payment(pay_id_or_external: str) -> Optional[Dict[str, Any]]:
    p = await payment_get(pay_id_or_external)
    if p:
        return p
    return await payment_find_by_external_id(pay_id_or_external)


async def mark_payment_status(
    pay_id: str,
    status: str,
    external_id: Optional[str] = None,
    raw: Optional[Dict[str, Any]] = None,
) -> None:
    await payment_set_status(pay_id, status=status, raw_event=raw, external_id=external_id)


async def grant_paid_access(
    chat_id: int,
    plan: str,
    source: str = "wata",
    pay_id: Optional[str] = None,
    external_id: Optional[str] = None,
    amount: Optional[float] = None,
    currency: Optional[str] = None,
    raw: Optional[Dict[str, Any]] = None,
) -> None:
    pay_key = str(pay_id or external_id or f"{chat_id}:{plan}")

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
            provider=str(source or "wata"),
            raw_create=raw,
        )

    await payment_set_status(
        pay_key,
        status="paid",
        raw_event=raw,
        external_id=external_id,
    )

    await set_subscription(int(chat_id), plan=str(plan))
    await payment_mark_processed(pay_key)


def _parse_chat_plan_from_external_id(external_id: str) -> Tuple[Optional[int], Optional[str]]:
    # ожидаем: tg-<chat_id>-<plan>-<uuid>
    if not external_id:
        return None, None
    s = str(external_id).strip()
    if not s:
        return None, None
    low = s.lower()

    if low.startswith("tg-"):
        parts = s.split("-")
        if len(parts) >= 3:
            chat = _parse_int(parts[1])
            plan = str(parts[2] or "").strip().lower()
            if plan in {"lite", "pro"}:
                return chat, plan

    plan = "pro" if "pro" in low else ("lite" if "lite" in low else None)
    chat = None
    try:
        import re
        m = re.search(r"(\d{5,})", low)
        if m:
            chat = _parse_int(m.group(1))
    except Exception:
        pass

    return chat, plan


def _wata_status(payload: Dict[str, Any]) -> Optional[str]:
    st = payload.get("transactionStatus") or payload.get("status")
    return st.strip().lower() if isinstance(st, str) else None


def _wata_is_paid(payload: Dict[str, Any]) -> bool:
    return _wata_status(payload) == "paid"


def _wata_is_declined(payload: Dict[str, Any]) -> bool:
    return _wata_status(payload) == "declined"


def _extract_amount_currency(payload: Dict[str, Any]) -> Tuple[Optional[float], Optional[str]]:
    amount = _parse_float(payload.get("amount"))
    currency = payload.get("currency")
    return amount, (str(currency) if currency is not None else None)


# --- Public key cache ---
_wata_pubkey_obj = None
_wata_pubkey_loaded_at: Optional[dt.datetime] = None


async def _wata_load_public_key() -> None:
    global _wata_pubkey_obj, _wata_pubkey_loaded_at
    now = _now_utc()

    if _wata_pubkey_obj and _wata_pubkey_loaded_at:
        if (now - _wata_pubkey_loaded_at) < dt.timedelta(minutes=WATA_PUBLIC_KEY_TTL_MIN):
            return

    url = f"{WATA_BASE_URL}/public-key"
    async with httpx.AsyncClient(timeout=WATA_TIMEOUT_SEC) as client:
        r = await client.get(url, headers={"Accept": "application/json"})

    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"WATA public-key HTTP {r.status_code}")

    data = r.json()
    pem = (data or {}).get("value")
    if not isinstance(pem, str) or "BEGIN" not in pem:
        raise HTTPException(status_code=502, detail="Invalid WATA public key payload")

    _wata_pubkey_obj = load_pem_public_key(pem.encode("utf-8"))
    _wata_pubkey_loaded_at = now


async def _wata_verify_signature(request: Request, raw_body: bytes) -> None:
    if not WATA_VERIFY_SIGNATURE:
        return

    sig_b64 = request.headers.get("X-Signature") or request.headers.get("x-signature")
    if not sig_b64:
        raise HTTPException(status_code=401, detail="Missing X-Signature")

    try:
        sig = base64.b64decode(sig_b64, validate=True)
    except Exception:
        raise HTTPException(status_code=401, detail="Bad X-Signature (base64)")

    await _wata_load_public_key()
    try:
        _wata_pubkey_obj.verify(sig, raw_body, padding.PKCS1v15(), hashes.SHA512())
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid signature")


@app.get("/health")
async def health() -> Dict[str, Any]:
    return {"ok": True, "ts": _now_utc().isoformat()}


@app.get("/payment/success")
async def payment_success() -> HTMLResponse:
    return HTMLResponse("<h2>✅ Оплата успешна</h2><p>Вернитесь в Telegram-бот — доступ активируется автоматически.</p>")


@app.get("/payment/fail")
async def payment_fail() -> HTMLResponse:
    return HTMLResponse("<h2>❌ Оплата не прошла</h2><p>Попробуйте ещё раз или напишите в поддержку.</p>")


# ВАЖНО: принимаем и со слэшем, и без (на всякий)
@app.post("/wata/webhook")
@app.post("/wata/webhook/")
async def wata_webhook(request: Request) -> JSONResponse:
    raw_body = await request.body()
    payload = _safe_json_loads(raw_body)

    # DEBUG PRINT (до проверки подписи!)
    if DEBUG_WATA_WEBHOOK:
        try:
            hdr = {k.lower(): v for k, v in request.headers.items()}
            print("\n===== WATA WEBHOOK IN =====", flush=True)
            print("ts:", _now_utc().isoformat(), flush=True)
            print("ip:", getattr(request.client, "host", None), flush=True)
            print("ua:", hdr.get("user-agent"), flush=True)
            print("content-type:", hdr.get("content-type"), flush=True)
            print("x-signature-present:", bool(hdr.get("x-signature")), flush=True)
            print("status:", _wata_status(payload), flush=True)
            print("orderId:", payload.get("orderId"), flush=True)
            print("transactionId:", payload.get("transactionId"), flush=True)
            print("paymentLinkId:", payload.get("paymentLinkId"), flush=True)
            print("errorCode:", payload.get("errorCode"), flush=True)
            print("errorDescription:", payload.get("errorDescription"), flush=True)
            raw_text = raw_body.decode("utf-8", errors="replace")
            print("raw(<=4000):", raw_text[:4000], flush=True)
            print("===== /WATA WEBHOOK IN =====\n", flush=True)
        except Exception as e:
            print("WATA DEBUG PRINT FAILED:", repr(e), flush=True)

    # RSA verify
    await _wata_verify_signature(request, raw_body)

    order_id = payload.get("orderId")
    transaction_id = payload.get("transactionId")
    wata_id = payload.get("id")
    payment_link_id = payload.get("paymentLinkId")

    amount, currency = _extract_amount_currency(payload)

    chat_id, plan = (None, None)
    if isinstance(order_id, str) and order_id:
        chat_id, plan = _parse_chat_plan_from_external_id(order_id)

    # fallback by amount
    if plan is None and amount is not None:
        if abs(float(amount) - LITE_PRICE) < 0.0001:
            plan = "lite"
        elif abs(float(amount) - PRO_PRICE) < 0.0001:
            plan = "pro"

    pay_key = str(transaction_id or wata_id or payment_link_id or order_id or "unknown")

    if not chat_id and order_id:
        p = await get_payment(str(order_id))
        if p and p.get("chat_id"):
            chat_id = int(p["chat_id"])
            if not plan and p.get("plan"):
                plan = str(p["plan"]).lower()

    if not chat_id:
        await mark_payment_status(pay_key, status="bad_payload", external_id=str(order_id) if order_id else None, raw=payload)
        raise HTTPException(status_code=400, detail="chat_id is missing (orderId)")

    if plan not in {"lite", "pro"}:
        await mark_payment_status(pay_key, status="bad_payload", external_id=str(order_id) if order_id else None, raw=payload)
        raise HTTPException(status_code=400, detail="plan is missing (lite/pro)")

    # Declined
    if _wata_is_declined(payload):
        await mark_payment_status(pay_key, status="declined", external_id=str(order_id) if order_id else None, raw=payload)
        return JSONResponse({"ok": True, "received": True, "paid": False, "declined": True})

    # Not paid / other statuses
    if not _wata_is_paid(payload):
        await mark_payment_status(pay_key, status="not_paid", external_id=str(order_id) if order_id else None, raw=payload)
        return JSONResponse({"ok": True, "received": True, "paid": False})

    await grant_paid_access(
        chat_id=int(chat_id),
        plan=str(plan),
        source="wata",
        pay_id=pay_key,
        external_id=str(order_id) if order_id else None,
        amount=amount,
        currency=currency,
        raw=payload,
    )

    if NOTIFY_ON_PAYMENT:
        bot = getattr(app.state, "bot", None)
        if bot:
            try:
                txt = "✅ Оплата получена. Подписка LITE активирована на 30 дней." if plan == "lite" else "✅ Оплата получена. Подписка PRO активирована на 30 дней."
                await bot.send_message(int(chat_id), txt)
            except Exception:
                pass

    return JSONResponse({"ok": True, "paid": True})