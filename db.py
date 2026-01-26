import os
import datetime as dt
from typing import Optional, Literal, Tuple, List, Any, Dict

from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DB = os.getenv("MONGODB_DB", "schoolbot")

if not MONGODB_URI:
    raise RuntimeError("MONGODB_URI is not set in .env")

MAX_TURNS = int(os.getenv("MAX_TURNS", "30"))

client = AsyncIOMotorClient(MONGODB_URI, tz_aware=True, tzinfo=dt.timezone.utc)
db = client[MONGODB_DB]
users = db["users"]
history = db["history"]
bookmarks = db["bookmarks"]
payments = db["payments"]

Plan = Literal["free", "lite", "pro"]

FREE_TEXT_LIMIT = 3
FREE_PHOTO_LIMIT = 2

LITE_TEXT_LIMIT = int(os.getenv("LITE_TEXT_LIMIT", "300"))
LITE_PHOTO_LIMIT = int(os.getenv("LITE_PHOTO_LIMIT", "120"))

UNLIMITED = 10**12

PAYSHARK_LITE_PRICE = os.getenv("PAYSHARK_LITE_PRICE") or os.getenv("LITE_PRICE_RUB") or os.getenv("TRIBUTE_LITE_PRICE") or "199.99"
PAYSHARK_PRO_PRICE = os.getenv("PAYSHARK_PRO_PRICE") or os.getenv("PRO_PRICE_RUB") or os.getenv("TRIBUTE_PRO_PRICE") or "299.99"
SUBSCRIPTION_DAYS = int(os.getenv("SUBSCRIPTION_DAYS", "30"))


def _now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _month_key(d: dt.datetime) -> str:
    return d.strftime("%Y-%m")


def _to_aware_utc(value) -> Optional[dt.datetime]:
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=dt.timezone.utc)
        return value.astimezone(dt.timezone.utc)
    if isinstance(value, str):
        try:
            parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed.astimezone(dt.timezone.utc)
    return None


_DEFAULT_PREFS: Dict[str, Any] = {
    "voice": {
        "auto": False,
        "name": os.getenv("TTS_VOICE", "alloy"),
        "speed": float(os.getenv("DEFAULT_VOICE_SPEED", "1.0")),
    },
    "teacher_mode": False,
    "answer_style": "generic",
    "priority": False,
    "lang": "auto",
    "communication_mode": "normal",
    "task_mode": "auto",
    "materials_mode": "auto",
    "study_mode": "auto",
    "coding_mode": "auto",
}


def _merge_defaults(p: Dict[str, Any] | None) -> Dict[str, Any]:
    out = dict(_DEFAULT_PREFS)
    p = p or {}
    v = dict(_DEFAULT_PREFS["voice"])
    v.update(p.get("voice") or {})
    out["voice"] = v
    for k, default in _DEFAULT_PREFS.items():
        if k == "voice":
            continue
        if k in p:
            out[k] = p[k]
        else:
            out[k] = default
    return out


def _as_price(value: str) -> str:
    s = (value or "").strip().replace(",", ".")
    try:
        v = float(s)
        return f"{v:.2f}".rstrip("0").rstrip(".") if "." in f"{v:.2f}" else f"{v:.2f}"
    except Exception:
        return s or "0"


async def ensure_user(chat_id: int) -> dict:
    now = _now_utc()
    doc = await users.find_one({"chat_id": chat_id})
    if doc:
        if "optin" not in doc:
            await users.update_one({"chat_id": chat_id}, {"$set": {"optin": True}})
            doc["optin"] = True
        merged = _merge_defaults(doc.get("prefs") if isinstance(doc.get("prefs"), dict) else {})
        if doc.get("prefs") != merged:
            await users.update_one({"chat_id": chat_id}, {"$set": {"prefs": merged}})
            doc["prefs"] = merged
        raw_exp = doc.get("sub_expires_at")
        norm_exp = _to_aware_utc(raw_exp)
        if norm_exp != raw_exp:
            await users.update_one({"chat_id": chat_id}, {"$set": {"sub_expires_at": norm_exp}})
            doc["sub_expires_at"] = norm_exp
        month = _month_key(now)
        if doc.get("period_month") != month:
            await users.update_one(
                {"chat_id": chat_id},
                {"$set": {"period_month": month, "text_used": 0, "photo_used": 0}},
            )
            doc["period_month"] = month
            doc["text_used"] = 0
            doc["photo_used"] = 0
        return doc

    doc = {
        "chat_id": chat_id,
        "created_at": now,
        "plan": "free",
        "sub_expires_at": None,
        "period_month": _month_key(now),
        "text_used": 0,
        "photo_used": 0,
        "optin": True,
        "prefs": _merge_defaults({}),
    }
    await users.insert_one(doc)
    return doc


async def _is_subscription_active(doc: dict) -> bool:
    if doc.get("plan") in ("lite", "pro"):
        exp = _to_aware_utc(doc.get("sub_expires_at"))
        return bool(exp and exp > _now_utc())
    return False


async def get_limits(doc: dict) -> Tuple[int, int]:
    plan = doc.get("plan", "free")
    active = await _is_subscription_active(doc)

    if plan == "pro" and active:
        return (UNLIMITED, UNLIMITED)
    if plan == "lite" and active:
        return (LITE_TEXT_LIMIT, LITE_PHOTO_LIMIT)
    return (FREE_TEXT_LIMIT, FREE_PHOTO_LIMIT)


async def can_use(doc: dict, kind: Literal["text", "photo"]) -> Tuple[bool, str]:
    text_limit, photo_limit = await get_limits(doc)
    tu, pu = doc.get("text_used", 0), doc.get("photo_used", 0)
    plan = doc.get("plan", "free")
    active = await _is_subscription_active(doc)

    lite_price = _as_price(PAYSHARK_LITE_PRICE)
    pro_price = _as_price(PAYSHARK_PRO_PRICE)

    def _msg_free() -> str:
        return (
            "🚫 Бесплатные лимиты закончились.\n\n"
            "Оформите подписку, чтобы продолжить:\n"
            f"• LITE — {lite_price} ₽ / {SUBSCRIPTION_DAYS} дней (до {LITE_TEXT_LIMIT} текстовых и до {LITE_PHOTO_LIMIT} фото-решений в месяц)\n"
            f"• PRO — {pro_price} ₽ / {SUBSCRIPTION_DAYS} дней (безлимит + приоритет)\n\n"
            "Откройте «📦 Доступные пакеты» или используйте команду /plan."
        )

    def _msg_lite() -> str:
        if kind == "text":
            return (
                f"🚫 Достигнут лимит LITE по текстовым запросам: {tu}/{text_limit} за месяц.\n\n"
                "Продлите LITE на следующий месяц или перейдите на PRO (безлимит).\n"
                "Откройте «📦 Доступные пакеты» или используйте команду /plan."
            )
        return (
            f"🚫 Достигнут лимит LITE по решениям с фото: {pu}/{photo_limit} за месяц.\n\n"
            "Продлите LITE на следующий месяц или перейдите на PRO (безлимит).\n"
            "Откройте «📦 Доступные пакеты» или используйте команду /plan."
        )

    if kind == "text":
        if tu < text_limit:
            return True, ""
        if plan == "lite" and active:
            return False, _msg_lite()
        return False, _msg_free()

    if kind == "photo":
        if pu < photo_limit:
            return True, ""
        if plan == "lite" and active:
            return False, _msg_lite()
        return False, _msg_free()

    return False, "Неизвестный тип запроса."


async def inc_usage(chat_id: int, kind: Literal["text", "photo"]) -> None:
    field = "text_used" if kind == "text" else "photo_used"
    await users.update_one({"chat_id": chat_id}, {"$inc": {field: 1}})


async def set_subscription(chat_id: int, plan: Plan, days: int = SUBSCRIPTION_DAYS) -> dict:
    now = _now_utc()
    exp = now + dt.timedelta(days=days)
    await users.update_one(
        {"chat_id": chat_id},
        {"$set": {"plan": plan, "sub_expires_at": exp}},
        upsert=True,
    )
    return await users.find_one({"chat_id": chat_id})


async def apply_promocode_access(chat_id: int, code: str, days: int = 365) -> tuple[bool, dt.datetime]:
    now = _now_utc()
    try:
        days_i = max(1, int(days))
    except Exception:
        days_i = 365
    exp_target = now + dt.timedelta(days=days_i)

    existing = await users.find_one({"chat_id": chat_id}, {"promo": 1, "sub_expires_at": 1})
    promo = (existing or {}).get("promo") if isinstance((existing or {}).get("promo"), dict) else None
    if promo and str(promo.get("code") or "") == str(code):
        exp = _to_aware_utc(promo.get("expires_at")) or _to_aware_utc((existing or {}).get("sub_expires_at")) or exp_target
        return False, exp

    cur_exp = _to_aware_utc((existing or {}).get("sub_expires_at"))
    exp = cur_exp if (cur_exp and cur_exp > exp_target) else exp_target

    res = await users.update_one(
        {"chat_id": chat_id, "promo.code": {"$ne": code}},
        {
            "$set": {
                "plan": "pro",
                "sub_expires_at": exp,
                "promo": {"code": code, "activated_at": now, "expires_at": exp},
                "access_source": "promo",
            }
        },
        upsert=True,
    )

    if getattr(res, "matched_count", 0) == 0 and getattr(res, "upserted_id", None) is None:
        u = await users.find_one({"chat_id": chat_id}, {"promo": 1, "sub_expires_at": 1})
        p2 = (u or {}).get("promo") if isinstance((u or {}).get("promo"), dict) else None
        exp2 = _to_aware_utc((p2 or {}).get("expires_at")) or _to_aware_utc((u or {}).get("sub_expires_at")) or exp
        return False, exp2

    return True, exp


async def is_pro_active(chat_id: int) -> bool:
    doc = await ensure_user(chat_id)
    return doc.get("plan") == "pro" and await _is_subscription_active(doc)


async def is_lite_active(chat_id: int) -> bool:
    doc = await ensure_user(chat_id)
    return doc.get("plan") == "lite" and await _is_subscription_active(doc)


async def get_status_text(chat_id: int) -> str:
    doc = await ensure_user(chat_id)
    text_limit, photo_limit = await get_limits(doc)
    active = await _is_subscription_active(doc)
    tu, pu = doc.get("text_used", 0), doc.get("photo_used", 0)
    plan = doc.get("plan", "free")
    exp = _to_aware_utc(doc.get("sub_expires_at"))

    if active and plan == "pro":
        exp_s = exp.strftime("%Y-%m-%d %H:%M UTC") if exp else ""
        return (
            f"📦 План: PRO (активен до {exp_s})\n"
            f"Текстовые запросы: безлимит (использовано {tu})\n"
            f"Решения по фото: безлимит (использовано {pu})"
        )

    if active and plan == "lite":
        exp_s = exp.strftime("%Y-%m-%d %H:%M UTC") if exp else ""
        return (
            f"📦 План: LITE (активен до {exp_s})\n"
            f"Текстовые запросы: {tu}/{text_limit}\n"
            f"Решения по фото: {pu}/{photo_limit}"
        )

    return (
        "📦 План: FREE\n"
        f"Текстовые запросы: {tu}/{text_limit}\n"
        f"Решения по фото: {pu}/{photo_limit}\n\n"
        "Оформить подписку: /plan"
    )


async def set_optin(chat_id: int, optin: bool = True) -> None:
    await users.update_one({"chat_id": chat_id}, {"$set": {"optin": optin}}, upsert=True)


async def set_optin_for_all(value: bool = True) -> int:
    res = await users.update_many({}, {"$set": {"optin": value}})
    return getattr(res, "modified_count", 0)


async def get_all_chat_ids(optin_only: bool = True) -> List[int]:
    if optin_only:
        query = {"$or": [{"optin": True}, {"optin": {"$exists": False}}]}
    else:
        query = {}
    cursor = users.find(query, {"chat_id": 1, "_id": 0})
    return [doc["chat_id"] async for doc in cursor]


async def drop_chat(chat_id: int) -> None:
    await users.delete_one({"chat_id": chat_id})


async def get_prefs(chat_id: int) -> Dict[str, Any]:
    doc = await ensure_user(chat_id)
    return _merge_defaults(doc.get("prefs") if isinstance(doc.get("prefs"), dict) else {})


async def set_pref(chat_id: int, key: str, value: Any) -> None:
    await users.update_one({"chat_id": chat_id}, {"$set": {f"prefs.{key}": value}}, upsert=True)


async def set_prefs(chat_id: int, updates: Dict[str, Any]) -> None:
    if not updates:
        return
    set_doc = {f"prefs.{k}": v for k, v in updates.items()}
    await users.update_one({"chat_id": chat_id}, {"$set": set_doc}, upsert=True)


async def get_pref_bool(chat_id: int, key: str, default: bool = False) -> bool:
    prefs = await get_prefs(chat_id)
    return bool(prefs.get(key, default))


async def get_voice_settings(chat_id: int) -> Dict[str, Any]:
    prefs = await get_prefs(chat_id)
    v = prefs.get("voice") or {}
    vv = dict(_DEFAULT_PREFS["voice"])
    vv.update(v)
    return vv


async def set_voice_settings(
    chat_id: int,
    name: Optional[str] = None,
    speed: Optional[float] = None,
    auto: Optional[bool] = None,
) -> None:
    updates: Dict[str, Any] = {}
    if name is not None:
        updates["prefs.voice.name"] = str(name)
    if speed is not None:
        s = max(0.5, min(1.6, float(speed)))
        updates["prefs.voice.speed"] = s
    if auto is not None:
        updates["prefs.voice.auto"] = bool(auto)
    if updates:
        await users.update_one({"chat_id": chat_id}, {"$set": updates}, upsert=True)


async def is_teacher_mode(chat_id: int) -> bool:
    prefs = await get_prefs(chat_id)
    return bool(prefs.get("teacher_mode", False))


async def set_teacher_mode(chat_id: int, on: bool) -> None:
    await users.update_one({"chat_id": chat_id}, {"$set": {"prefs.teacher_mode": bool(on)}}, upsert=True)


async def get_answer_style(chat_id: int) -> str:
    prefs = await get_prefs(chat_id)
    return str(prefs.get("answer_style", "generic"))


async def set_answer_style(chat_id: int, style: str) -> None:
    await users.update_one({"chat_id": chat_id}, {"$set": {"prefs.answer_style": str(style)}}, upsert=True)


async def get_priority(chat_id: int) -> bool:
    prefs = await get_prefs(chat_id)
    return bool(prefs.get("priority", False))


async def set_priority(chat_id: int, on: bool) -> None:
    await users.update_one({"chat_id": chat_id}, {"$set": {"prefs.priority": bool(on)}}, upsert=True)


async def get_lang(chat_id: int) -> str:
    prefs = await get_prefs(chat_id)
    return str(prefs.get("lang", "auto"))


async def set_lang(chat_id: int, lang: str) -> None:
    await users.update_one(
        {"chat_id": chat_id},
        {"$set": {"prefs.lang": str(lang)}},
        upsert=True,
    )


async def get_modes(chat_id: int) -> Dict[str, Any]:
    prefs = await get_prefs(chat_id)
    return {
        "communication_mode": prefs.get("communication_mode", _DEFAULT_PREFS["communication_mode"]),
        "task_mode": prefs.get("task_mode", _DEFAULT_PREFS["task_mode"]),
        "materials_mode": prefs.get("materials_mode", _DEFAULT_PREFS["materials_mode"]),
        "study_mode": prefs.get("study_mode", _DEFAULT_PREFS["study_mode"]),
        "coding_mode": prefs.get("coding_mode", _DEFAULT_PREFS["coding_mode"]),
    }


async def set_mode(chat_id: int, kind: str, value: str) -> None:
    if kind not in {"communication_mode", "task_mode", "materials_mode", "study_mode", "coding_mode"}:
        return
    await users.update_one(
        {"chat_id": chat_id},
        {"$set": {f"prefs.{kind}": str(value)}},
        upsert=True,
    )


async def set_communication_mode(chat_id: int, value: str) -> None:
    await set_mode(chat_id, "communication_mode", value)


async def set_task_mode(chat_id: int, value: str) -> None:
    await set_mode(chat_id, "task_mode", value)


async def set_materials_mode(chat_id: int, value: str) -> None:
    await set_mode(chat_id, "materials_mode", value)


async def set_study_mode(chat_id: int, value: str) -> None:
    await set_mode(chat_id, "study_mode", value)


async def set_coding_mode(chat_id: int, value: str) -> None:
    await set_mode(chat_id, "coding_mode", value)


async def add_history(
    chat_id: int,
    role: Literal["user", "assistant"],
    content: str,
    ts: Optional[dt.datetime] = None,
) -> None:
    if not content:
        return
    await history.insert_one(
        {
            "chat_id": chat_id,
            "role": role,
            "content": content,
            "ts": ts or _now_utc(),
        }
    )


async def get_history(chat_id: int, max_turns: Optional[int] = None) -> List[Dict[str, str]]:
    limit_pairs = max_turns or MAX_TURNS
    cursor = history.find({"chat_id": chat_id}).sort("ts", -1).limit(limit_pairs * 2)
    items = [{"role": doc["role"], "content": doc["content"]} async for doc in cursor]
    items.reverse()
    return items


async def clear_history(chat_id: int) -> None:
    await history.delete_many({"chat_id": chat_id})


async def remember_bookmark(chat_id: int, content: str) -> None:
    if not content:
        return
    await bookmarks.insert_one(
        {
            "chat_id": chat_id,
            "content": content,
            "ts": _now_utc(),
        }
    )


async def forget_last_bookmark(chat_id: int) -> bool:
    doc = await bookmarks.find_one({"chat_id": chat_id}, sort=[("ts", -1)])
    if not doc:
        return False
    await bookmarks.delete_one({"_id": doc["_id"]})
    return True


async def get_last_bookmark(chat_id: int) -> Optional[str]:
    doc = await bookmarks.find_one(
        {"chat_id": chat_id}, sort=[("ts", -1)], projection={"content": 1}
    )
    return (doc or {}).get("content")


async def payment_create(
    pay_id: str,
    chat_id: int,
    plan: str,
    amount: float,
    currency: str = "RUB",
    provider: str = "payshark",
    raw_create: Optional[Dict[str, Any]] = None,
) -> bool:
    now = _now_utc()
    res = await payments.update_one(
        {"_id": str(pay_id)},
        {
            "$setOnInsert": {
                "_id": str(pay_id),
                "provider": str(provider),
                "chat_id": int(chat_id),
                "plan": str(plan),
                "amount": float(amount),
                "currency": str(currency),
                "status": "created",
                "created_at": now,
                "processed": False,
            },
            "$set": {
                "updated_at": now,
                "raw_create": raw_create,
            },
        },
        upsert=True,
    )
    return bool(getattr(res, "upserted_id", None))


async def payment_set_status(
    pay_id: str,
    status: str,
    raw_event: Optional[Dict[str, Any]] = None,
    external_id: Optional[str] = None,
) -> None:
    now = _now_utc()
    set_doc: Dict[str, Any] = {"status": str(status), "updated_at": now}
    if raw_event is not None:
        set_doc["raw_event"] = raw_event
    if external_id is not None:
        set_doc["external_id"] = str(external_id)
    await payments.update_one({"_id": str(pay_id)}, {"$set": set_doc}, upsert=True)


async def payment_mark_processed(pay_id: str) -> bool:
    now = _now_utc()
    res = await payments.update_one(
        {"_id": str(pay_id), "processed": {"$ne": True}},
        {"$set": {"processed": True, "processed_at": now, "updated_at": now}},
    )
    return getattr(res, "modified_count", 0) == 1


async def payment_get(pay_id: str) -> Optional[Dict[str, Any]]:
    return await payments.find_one({"_id": str(pay_id)})


async def payment_find_by_external_id(external_id: str) -> Optional[Dict[str, Any]]:
    return await payments.find_one({"external_id": str(external_id)})


REF_REWARD_BATCH = int(os.getenv("REF_BONUS_THRESHOLD", "6"))


async def extend_pro_months(chat_id: int, months: int = 1) -> dt.datetime:
    doc = await ensure_user(chat_id)
    now = _now_utc()
    active = await _is_subscription_active(doc) and (doc.get("plan") == "pro")
    start_from = _to_aware_utc(doc.get("sub_expires_at")) if active else now
    if start_from is None or start_from < now:
        start_from = now
    new_until = start_from + dt.timedelta(days=30 * max(1, int(months)))
    await users.update_one(
        {"chat_id": chat_id},
        {"$set": {"plan": "pro", "sub_expires_at": new_until}},
        upsert=True,
    )
    return new_until


async def get_or_create_ref_code(user_id: int) -> str:
    u = await users.find_one({"chat_id": user_id}, {"ref_code": 1})
    if u and u.get("ref_code"):
        return u["ref_code"]
    import secrets
    import string

    alphabet = string.ascii_lowercase + string.digits
    code = "".join(secrets.choice(alphabet) for _ in range(7))
    while await users.find_one({"ref_code": code}, {"_id": 1}):
        code = "".join(secrets.choice(alphabet) for _ in range(7))
    await users.update_one({"chat_id": user_id}, {"$set": {"ref_code": code}}, upsert=True)
    return code


async def find_user_by_ref_code(code: str) -> Optional[int]:
    u = await users.find_one({"ref_code": code}, {"chat_id": 1})
    return int(u["chat_id"]) if u else None


async def set_referrer_once(user_id: int, referrer_id: int) -> bool:
    if user_id == referrer_id:
        return False
    u = await users.find_one({"chat_id": user_id}, {"referred_by": 1})
    if u and u.get("referred_by"):
        return False
    await users.update_one(
        {"chat_id": user_id}, {"$set": {"referred_by": referrer_id}}, upsert=True
    )
    await users.update_one(
        {"chat_id": referrer_id}, {"$inc": {"referred_count": 1}}, upsert=True
    )
    return True


async def get_referral_stats(user_id: int) -> dict:
    u = await users.find_one(
        {"chat_id": user_id},
        {"ref_code": 1, "referred_by": 1, "referred_count": 1, "referred_paid_count": 1},
    )
    if not u:
        return {
            "ref_code": None,
            "referred_by": None,
            "referred_count": 0,
            "referred_paid_count": 0,
        }
    return {
        "ref_code": u.get("ref_code"),
        "referred_by": u.get("referred_by"),
        "referred_count": int(u.get("referred_count") or 0),
        "referred_paid_count": int(u.get("referred_paid_count") or 0),
    }


async def mark_referral_paid_if_first(buyer_id: int) -> tuple[bool, int, Optional[int]]:
    buyer = await users.find_one({"chat_id": buyer_id}, {"referred_by": 1})
    referrer_id = buyer.get("referred_by") if buyer else None
    if not referrer_id:
        return False, 0, None

    res = await users.update_one(
        {"chat_id": referrer_id},
        {"$addToSet": {"referred_paid_ids": buyer_id}},
    )
    if getattr(res, "modified_count", 0) != 1:
        doc = await users.find_one(
            {"chat_id": referrer_id}, {"referred_paid_ids": 1}
        )
        count = len(doc.get("referred_paid_ids") or [])
        return False, count, referrer_id

    await users.update_one(
        {"chat_id": referrer_id},
        {"$inc": {"referred_paid_count": 1}},
        upsert=True,
    )
    doc = await users.find_one(
        {"chat_id": referrer_id}, {"referred_paid_count": 1}
    )
    count = int(doc.get("referred_paid_count") or 0)
    return True, count, referrer_id


async def process_referral_reward_if_needed(
    buyer_id: int,
) -> tuple[bool, int, Optional[int]]:
    credited, paid_count, referrer_id = await mark_referral_paid_if_first(buyer_id)
    if not credited or not referrer_id:
        return False, paid_count, referrer_id
    if paid_count % REF_REWARD_BATCH == 0:
        await extend_pro_months(referrer_id, months=1)
        return True, paid_count, referrer_id
    return False, paid_count, referrer_id


# --- Compatibility layer for PayShark webhooks (older imports) ---

async def create_payment_intent(plan: str, chat_id: int, username: str | None = None) -> dict | None:
    # PayShark uses hosted payment links; intent is created on provider side.
    # We keep this for backward compatibility with older webhook code.
    return None


async def get_payment(order_id: str | None = None, payment_id: str | None = None) -> dict | None:
    key = str(order_id or payment_id or "").strip()
    if not key:
        return None
    doc = await payment_get(key)
    if doc:
        return doc
    # sometimes provider sends external_id separately
    return await payment_find_by_external_id(key)


async def mark_payment_status(payment_id: str, status: str, raw: dict | None = None) -> None:
    key = str(payment_id or "").strip()
    if not key:
        return
    await payment_set_status(key, status=str(status), raw_event=raw, external_id=key)


async def grant_paid_access(chat_id: int, plan: str, payment_id: str | None = None, order_id: str | None = None) -> bool:
    plan_s = str(plan or "").strip().lower()
    if plan_s not in {"lite", "pro"}:
        return False

    pay_key = str(order_id or payment_id or f"{chat_id}:{plan_s}").strip()
    doc = await payment_get(pay_key)
    if not doc:
        # create a minimal record so we can mark it processed idempotently
        try:
            amt = float(PAYSHARK_LITE_PRICE if plan_s == "lite" else PAYSHARK_PRO_PRICE)
        except Exception:
            amt = 0.0
        await payment_create(
            pay_id=pay_key,
            chat_id=int(chat_id),
            plan=plan_s,
            amount=amt,
            currency="RUB",
            provider="payshark",
            raw_create=None,
        )
        doc = await payment_get(pay_key)

    if doc and doc.get("processed") is True:
        return False

    await payment_set_status(
        pay_key,
        status="paid",
        raw_event=None,
        external_id=str(order_id or payment_id or pay_key),
    )
    await set_subscription(int(chat_id), plan_s)
    await payment_mark_processed(pay_key)
    return True
