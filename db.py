# db.py
import os
import datetime as dt
from typing import Optional, Literal, Tuple, List  # --- added/updated ---

from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DB  = os.getenv("MONGODB_DB", "schoolbot")

if not MONGODB_URI:
    raise RuntimeError("MONGODB_URI is not set in .env")

# ВАЖНО: включаем tz_aware, чтобы Mongo возвращал tz-aware даты (UTC)
client = AsyncIOMotorClient(MONGODB_URI, tz_aware=True, tzinfo=dt.timezone.utc)
db = client[MONGODB_DB]
users = db["users"]

Plan = Literal["free", "lite", "pro"]

# --- лимиты ---
FREE_TEXT_LIMIT  = 3
FREE_PHOTO_LIMIT = 2

# LITE (меняются в .env)
LITE_TEXT_LIMIT  = int(os.getenv("LITE_TEXT_LIMIT",  "300"))
LITE_PHOTO_LIMIT = int(os.getenv("LITE_PHOTO_LIMIT", "120"))

UNLIMITED = 10**12  # «бесконечность» для PRO

def _now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)

def _month_key(d: dt.datetime) -> str:
    return d.strftime("%Y-%m")  # например "2025-09"

def _to_aware_utc(value) -> Optional[dt.datetime]:
    """Приводим любые варианты даты к tz-aware UTC (или None)."""
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

async def ensure_user(chat_id: int) -> dict:
    """Возвращает (и создаёт при необходимости) документ пользователя; обнуляет счётчики при новом месяце.
       Попутно нормализует sub_expires_at к tz-aware UTC, если раньше сохранилось naive.
       Также добавляет/мигрирует поле optin для рассылок."""
    now = _now_utc()
    doc = await users.find_one({"chat_id": chat_id})
    if doc:
        # --- миграция optin: если поля нет, включаем подписку по умолчанию
        if "optin" not in doc:
            await users.update_one({"chat_id": chat_id}, {"$set": {"optin": True}})
            doc["optin"] = True
        # Миграция: нормализуем дату подписки к aware UTC
        raw_exp = doc.get("sub_expires_at")
        norm_exp = _to_aware_utc(raw_exp)
        if norm_exp != raw_exp:
            await users.update_one({"chat_id": chat_id}, {"$set": {"sub_expires_at": norm_exp}})
            doc["sub_expires_at"] = norm_exp

        month = _month_key(now)
        if doc.get("period_month") != month:
            await users.update_one(
                {"chat_id": chat_id},
                {"$set": {"period_month": month, "text_used": 0, "photo_used": 0}}
            )
            doc["period_month"] = month
            doc["text_used"] = 0
            doc["photo_used"] = 0
        return doc

    doc = {
        "chat_id": chat_id,
        "created_at": now,
        "plan": "free",           # free / lite / pro
        "sub_expires_at": None,   # дата окончания подписки (для lite/pro)
        "period_month": _month_key(now),
        "text_used": 0,
        "photo_used": 0,
        "optin": True,            # подписка на рассылки по умолчанию
    }
    await users.insert_one(doc)
    return doc

async def _is_subscription_active(doc: dict) -> bool:
    if doc.get("plan") in ("lite", "pro"):
        exp = _to_aware_utc(doc.get("sub_expires_at"))
        return bool(exp and exp > _now_utc())
    return False

async def get_limits(doc: dict) -> Tuple[int, int]:
    """
    Возвращает (text_limit, photo_limit) для текущего статуса.
    FREE: 3 / 2
    LITE (активна): берёт из .env (по умолчанию 300 / 120)
    PRO (активна): безлимит
    """
    plan = doc.get("plan", "free")
    active = await _is_subscription_active(doc)

    if plan == "pro" and active:
        return (UNLIMITED, UNLIMITED)
    if plan == "lite" and active:
        return (LITE_TEXT_LIMIT, LITE_PHOTO_LIMIT)
    # free или просроченная подписка
    return (FREE_TEXT_LIMIT, FREE_PHOTO_LIMIT)

async def can_use(doc: dict, kind: Literal["text", "photo"]) -> Tuple[bool, str]:
    """Проверяет лимит; (allowed, msg_if_blocked). Сообщение учитывает план."""
    text_limit, photo_limit = await get_limits(doc)
    tu, pu = doc.get("text_used", 0), doc.get("photo_used", 0)
    plan = doc.get("plan", "free")
    active = await _is_subscription_active(doc)

    def _msg_free() -> str:
        return (
            "🚫 Бесплатные лимиты закончились.\n\n"
            "Оформите подписку, чтобы продолжить:\n"
            f"• Lite — 199.99 ₽ / 30 дней (до {LITE_TEXT_LIMIT} текстовых и до {LITE_PHOTO_LIMIT} фото-решений в месяц)\n"
            "• Pro  — 299.99 ₽ / 30 дней (безлимит + приоритет)\n"
            "Команды: /buy199 или /buy299"
        )

    def _msg_lite() -> str:
        if kind == "text":
            return (f"🚫 Достигнут лимит LITE по текстовым запросам: {tu}/{text_limit} за месяц.\n\n"
                    "Продлите LITE на следующий месяц или перейдите на PRO (безлимит).\n"
                    "Команды: /buy199 или /buy299")
        else:
            return (f"🚫 Достигнут лимит LITE по решениям с фото: {pu}/{photo_limit} за месяц.\n\n"
                    "Продлите LITE на следующий месяц или перейдите на PRO (безлимит).\n"
                    "Команды: /buy199 или /buy299")

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

# --- управление подпиской ---
async def set_subscription(chat_id: int, plan: Plan, days: int = 30) -> dict:
    now = _now_utc()
    exp = now + dt.timedelta(days=days)
    await users.update_one(
        {"chat_id": chat_id},
        {"$set": {"plan": plan, "sub_expires_at": exp}},
        upsert=True,
    )
    return await users.find_one({"chat_id": chat_id})

async def get_status_text(chat_id: int) -> str:
    doc = await ensure_user(chat_id)
    text_limit, photo_limit = await get_limits(doc)
    active = await _is_subscription_active(doc)
    tu, pu = doc.get("text_used", 0), doc.get("photo_used", 0)
    plan = doc.get("plan", "free")
    exp  = _to_aware_utc(doc.get("sub_expires_at"))

    if active and plan == "pro":
        exp_s = exp.strftime("%Y-%m-%d %H:%M UTC")
        return (f"📦 План: PRO (активен до {exp_s})\n"
                f"Текстовые запросы: безлимит (использовано {tu})\n"
                f"Решения по фото: безлимит (использовано {pu})")

    if active and plan == "lite":
        exp_s = exp.strftime("%Y-%m-%d %H:%М UTC")
        return (f"📦 План: LITE (активен до {exp_s})\n"
                f"Текстовые запросы: {tu}/{text_limit}\n"
                f"Решения по фото: {pu}/{photo_limit}")

    # free
    return (f"📦 План: FREE\n"
            f"Текстовые запросы: {tu}/{text_limit}\n"
            f"Решения по фото: {pu}/{photo_limit}\n\n"
            f"Обновите план: /plan")

# -------------------------------
# Рассылки / подписки (optin)
# -------------------------------

async def set_optin(chat_id: int, optin: bool = True) -> None:
    """Включить/выключить подписку на рассылки для пользователя."""
    await users.update_one({"chat_id": chat_id}, {"$set": {"optin": optin}}, upsert=True)

async def set_optin_for_all(value: bool = True) -> int:
    """Массово проставить optin всем пользователям. Возвращает число изменённых документов."""
    res = await users.update_many({}, {"$set": {"optin": value}})
    return getattr(res, "modified_count", 0)

async def get_all_chat_ids(optin_only: bool = True) -> List[int]:
    """
    Получить список chat_id для рассылки.
    Если optin_only=True — берём тех, у кого optin=True ИЛИ поле optin отсутствует (по умолчанию считаем True).
    """
    if optin_only:
        query = {"$or": [{"optin": True}, {"optin": {"$exists": False}}]}
    else:
        query = {}
    cursor = users.find(query, {"chat_id": 1, "_id": 0})
    return [doc["chat_id"] async for doc in cursor]

async def drop_chat(chat_id: int) -> None:
    """Удалить (или пометить) мёртвый чат из базы — например, если пользователь заблокировал бота."""
    await users.delete_one({"chat_id": chat_id})
