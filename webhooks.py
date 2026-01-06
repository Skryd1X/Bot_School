import os
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

from aiogram import Bot, Dispatcher
from aiogram.types import Update
from aiogram.client.session.aiohttp import AiohttpSession

from db import db, set_subscription, process_referral_reward_if_needed, get_prefs


log = logging.getLogger("webhooks")

BOT_TOKEN = (os.getenv("BOT_TOKEN") or "").strip()
PUBLIC_BASE_URL = (os.getenv("PUBLIC_BASE_URL") or "").rstrip("/")
TELEGRAM_WEBHOOK_PATH = os.getenv("TELEGRAM_WEBHOOK_PATH", "/webhook/telegram")
TELEGRAM_SECRET_TOKEN = os.getenv("TELEGRAM_WEBHOOK_SECRET", "change-me-please")

TRIBUTE_API_KEY = (os.getenv("TRIBUTE_API_KEY") or "").strip()
TRIBUTE_LITE_STARTAPP = (os.getenv("TRIBUTE_LITE_STARTAPP") or "").strip()
TRIBUTE_PRO_STARTAPP = (os.getenv("TRIBUTE_PRO_STARTAPP") or "").strip()

SUBSCRIPTION_DAYS = int(os.getenv("SUBSCRIPTION_DAYS", "30"))
NOTIFY_ON_PAYMENT = (os.getenv("NOTIFY_ON_PAYMENT", "false").lower() == "true")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

payments = db["payments"]


def _ok(payload: Optional[dict] = None) -> JSONResponse:
    data = {"ok": True}
    if payload:
        data.update(payload)
    return JSONResponse(data)


def _fail(msg: str, code: int = 400) -> None:
    raise HTTPException(status_code=code, detail=msg)


def _get_api_key(req: Request) -> Optional[str]:
    return req.headers.get("X-Api-Key") or req.headers.get("x-tribute-api-key") or req.query_params.get("key")


def _to_bool(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    return s in {"1", "true", "yes", "y", "on"}


def _as_float(v: Any) -> float:
    try:
        return float(v)
    except Exception:
        return 0.0


def _as_int(v: Any) -> Optional[int]:
    if v is None:
        return None
    try:
        s = str(v).strip()
        if not s:
            return None
        return int(s)
    except Exception:
        return None


@dataclass(frozen=True)
class TributeEvent:
    event_id: Optional[str]
    is_test: bool
    status: str
    paid: bool
    amount: float
    currency: str
    startapp: str
    telegram_user_id: Optional[int]


def _deep_get(obj: Any, path: list[str], default: Any = None) -> Any:
    cur = obj
    for key in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
    return cur if cur is not None else default


def _extract_event(data: dict) -> TributeEvent:
    is_test = _to_bool(data.get("test")) or str(data.get("mode") or "").lower() in {"test", "sandbox"}

    event_id = (
        data.get("id")
        or data.get("event_id")
        or _deep_get(data, ["payment", "id"])
        or _deep_get(data, ["invoice", "id"])
    )
    event_id = str(event_id).strip() if event_id is not None else None
    if event_id == "":
        event_id = None

    status = (
        str(data.get("status") or _deep_get(data, ["payment", "status"]) or _deep_get(data, ["invoice", "status"]) or "")
        .strip()
        .lower()
    )

    paid = (
        _to_bool(data.get("paid"))
        or _to_bool(_deep_get(data, ["payment", "paid"]))
        or status in {"succeeded", "success", "paid", "completed"}
    )

    amount = _as_float(data.get("amount") or _deep_get(data, ["payment", "amount"]) or _deep_get(data, ["invoice", "amount"]) or 0)
    currency = str(data.get("currency") or _deep_get(data, ["payment", "currency"]) or _deep_get(data, ["invoice", "currency"]) or "").upper().strip()

    startapp = str(
        data.get("startapp")
        or _deep_get(data, ["product", "startapp"])
        or _deep_get(data, ["product", "code"])
        or ""
    ).strip()

    telegram_user_id = (
        data.get("telegram_user_id")
        or data.get("from_id")
        or _deep_get(data, ["buyer", "telegram_id"])
        or _deep_get(data, ["user", "id"])
        or _deep_get(data, ["payment", "telegram_user_id"])
    )
    telegram_user_id_int = _as_int(telegram_user_id)

    return TributeEvent(
        event_id=event_id,
        is_test=is_test,
        status=status,
        paid=paid,
        amount=amount,
        currency=currency,
        startapp=startapp,
        telegram_user_id=telegram_user_id_int,
    )


async def _resolve_lang(chat_id: int) -> str:
    try:
        prefs = await get_prefs(chat_id)
    except Exception:
        prefs = {}
    lang = (prefs or {}).get("lang")
    return lang if isinstance(lang, str) and lang else "ru"


def _pay_text(lang: str, plan: str, days: int) -> str:
    l = (lang or "ru").lower()

    if plan == "lite":
        texts = {
            "ru": f"✅ LITE активирован на {days} дней. Приятной учёбы!",
            "en": f"✅ LITE activated for {days} days. Happy studying!",
            "uz": f"✅ LITE {days} kunga faollashtirildi. Yoqimli o‘qish!",
            "kk": f"✅ LITE {days} күнге қосылды. Сәтті оқу!",
            "de": f"✅ LITE für {days} Tage aktiviert. Viel Erfolg beim Lernen!",
            "fr": f"✅ LITE activé pour {days} jours. Bonne étude !",
            "es": f"✅ LITE activado por {days} días. ¡Buen estudio!",
            "tr": f"✅ LITE {days} gün etkinleştirildi. İyi çalışmalar!",
            "ar": f"✅ تم تفعيل LITE لمدة {days} يومًا. دراسة ممتعة!",
            "hi": f"✅ LITE {days} दिनों के लिए सक्रिय हो गया। शुभ अध्ययन!",
        }
        return texts.get(l, texts["en"] if l != "ru" else texts["ru"])

    texts = {
        "ru": f"⭐ Спасибо за покупку PRO на {days} дней! Безлимит и приоритет включены.",
        "en": f"⭐ Thanks for getting PRO for {days} days! Unlimited access and priority are on.",
        "uz": f"⭐ PRO {days} kunga olganingiz uchun rahmat! Cheksiz va prioritet yoqildi.",
        "kk": f"⭐ PRO {days} күнге сатып алғаныңызға рахмет! Шексіз және приоритет қосылды.",
        "de": f"⭐ Danke für PRO für {days} Tage! Unbegrenzt und Priorität sind aktiv.",
        "fr": f"⭐ Merci pour PRO {days} jours ! Accès illimité et priorité activés.",
        "es": f"⭐ ¡Gracias por PRO {days} días! Acceso ilimitado y prioridad activados.",
        "tr": f"⭐ PRO {days} gün için teşekkürler! Sınırsız erişim ve öncelik aktif.",
        "ar": f"⭐ شكرًا لشراء PRO لمدة {days} يومًا! تم تفعيل اللامحدود والأولوية.",
        "hi": f"⭐ PRO {days} दिनों के लिए लेने के लिए धन्यवाद! अनलिमिटेड और प्रायोरिटी चालू है।",
    }
    return texts.get(l, texts["en"] if l != "ru" else texts["ru"])


def _ref_text(lang: str, paid_count: int, rewarded: bool) -> str:
    l = (lang or "ru").lower()
    if rewarded:
        texts = {
            "ru": f"🎉 Ваш {paid_count}-й платящий друг оформил подписку — месяц PRO начислен автоматически!",
            "en": f"🎉 Your {paid_count}th paying friend subscribed — 1 month of PRO has been added automatically!",
            "uz": f"🎉 Sizning {paid_count}-to‘lovchi do‘stingiz obuna oldi — 1 oy PRO avtomatik qo‘shildi!",
            "kk": f"🎉 Сіздің {paid_count}-төлем жасаған досыңыз жазылды — 1 ай PRO автоматты түрде қосылды!",
            "de": f"🎉 Dein {paid_count}. zahlender Freund hat abonniert — 1 Monat PRO wurde automatisch gutgeschrieben!",
            "fr": f"🎉 Votre {paid_count}e ami payant s’est abonné — 1 mois de PRO a été ajouté automatiquement !",
            "es": f"🎉 Tu {paid_count}º amigo de pago se suscribió — ¡se añadió 1 mes de PRO automáticamente!",
            "tr": f"🎉 {paid_count}. ücretli arkadaşın abone oldu — 1 ay PRO otomatik eklendi!",
            "ar": f"🎉 صديقك الدافع رقم {paid_count} اشترك — تمت إضافة شهر PRO تلقائيًا!",
            "hi": f"🎉 आपका {paid_count}वाँ भुगतान करने वाला दोस्त सब्सक्राइब हुआ — 1 माह PRO अपने-आप जुड़ गया!",
        }
        return texts.get(l, texts["en"] if l != "ru" else texts["ru"])

    texts = {
        "ru": f"🙌 По вашей ссылке очередная покупка! Зачтено платящих: {paid_count}.",
        "en": f"🙌 Another purchase via your link! Paying users counted: {paid_count}.",
        "uz": f"🙌 Sizning havolangiz orqali yana bir xarid! To‘lovchilar soni: {paid_count}.",
        "kk": f"🙌 Сіздің сілтемеңіз арқылы тағы бір сатып алу! Төлем жасағандар: {paid_count}.",
        "de": f"🙌 Noch ein Kauf über deinen Link! Zahlende Nutzer: {paid_count}.",
        "fr": f"🙌 Un nouvel achat via votre lien ! Payants comptabilisés : {paid_count}.",
        "es": f"🙌 ¡Otra compra con tu enlace! Pagos contabilizados: {paid_count}.",
        "tr": f"🙌 Bağlantın üzerinden bir satın alma daha! Ödeyen sayısı: {paid_count}.",
        "ar": f"🙌 عملية شراء جديدة عبر رابطك! عدد الدافعين: {paid_count}.",
        "hi": f"🙌 आपके लिंक से एक और खरीद! भुगतान करने वालों की गिनती: {paid_count}.",
    }
    return texts.get(l, texts["en"] if l != "ru" else texts["ru"])


async def _notify(bot: Optional[Bot], chat_id: int, text: str) -> None:
    if not NOTIFY_ON_PAYMENT:
        return
    t = (text or "").strip()
    if not t:
        return

    if bot is not None:
        try:
            await bot.send_message(chat_id=chat_id, text=t, disable_web_page_preview=True)
            return
        except Exception as e:
            log.warning("notify via bot failed: %s", e)

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": t, "disable_web_page_preview": True}
    timeout = httpx.Timeout(10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            await client.post(url, data=payload)
        except Exception as e:
            log.warning("notify via http failed: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from handlers import router as handlers_router

    session = AiohttpSession(timeout=120)
    bot = Bot(token=BOT_TOKEN, session=session)
    dp = Dispatcher()
    dp.include_router(handlers_router)

    app.state.bot = bot
    app.state.dp = dp

    if PUBLIC_BASE_URL:
        url = f"{PUBLIC_BASE_URL}{TELEGRAM_WEBHOOK_PATH}"
        try:
            await bot.delete_webhook(drop_pending_updates=True)
            await bot.set_webhook(url=url, secret_token=TELEGRAM_SECRET_TOKEN, drop_pending_updates=True)
            me = await bot.get_me()
            log.info("Telegram webhook set: %s (@%s)", url, me.username)
        except Exception as e:
            log.error("Telegram webhook set failed: %s", e)
            raise
    else:
        log.warning("PUBLIC_BASE_URL is not set")

    try:
        yield
    finally:
        try:
            await bot.delete_webhook(drop_pending_updates=False)
        except Exception:
            pass
        try:
            await bot.session.close()
        except Exception:
            pass


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health():
    return _ok({"health": "ok"})


@app.post(TELEGRAM_WEBHOOK_PATH)
async def telegram_handler(request: Request):
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if TELEGRAM_SECRET_TOKEN and secret != TELEGRAM_SECRET_TOKEN:
        raise HTTPException(status_code=401, detail="bad telegram secret")

    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid telegram json")

    try:
        update = Update.model_validate(data)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid telegram update")

    bot: Bot = request.app.state.bot
    dp: Dispatcher = request.app.state.dp

    try:
        await dp.feed_update(bot, update)
    except Exception as e:
        log.warning("dp.feed_update failed: %s", e)

    return _ok()


@app.get("/webhook/tribute")
async def tribute_ping():
    return _ok({"ping": True})


async def _dedupe_event(event_id: str, raw: dict) -> bool:
    now = datetime.now(timezone.utc)
    res = await payments.update_one(
        {"_id": event_id},
        {
            "$setOnInsert": {
                "raw": raw,
                "created_at": now,
                "processed_at": None,
            }
        },
        upsert=True,
    )
    return bool(res.upserted_id)


async def _mark_processed(event_id: str, plan: str, days: int, amount: float, currency: str, startapp: str) -> None:
    await payments.update_one(
        {"_id": event_id},
        {
            "$set": {
                "processed_at": datetime.now(timezone.utc),
                "plan": plan,
                "days": days,
                "amount": amount,
                "currency": currency,
                "startapp": startapp,
            }
        },
    )


@app.post("/webhook/tribute")
async def tribute_webhook(request: Request):
    key = _get_api_key(request)
    if TRIBUTE_API_KEY and key != TRIBUTE_API_KEY:
        _fail("bad api key", 401)

    try:
        data = await request.json()
    except Exception:
        _fail("invalid json")

    evt = _extract_event(data)

    if evt.is_test or str(data.get("event") or "").lower() in {"test", "ping"}:
        return _ok({"ignored": "test"})

    if not evt.paid:
        return _ok({"ignored": "not_paid"})

    if evt.amount <= 0:
        return _ok({"ignored": "zero_amount"})

    if not evt.telegram_user_id:
        _fail("telegram_user_id missing")

    bot: Optional[Bot] = getattr(request.app.state, "bot", None)

    if evt.event_id:
        inserted = await _dedupe_event(evt.event_id, data)
        if not inserted:
            return _ok({"dup": True})

    chat_id = evt.telegram_user_id
    if evt.startapp == TRIBUTE_LITE_STARTAPP:
        plan = "lite"
    elif evt.startapp == TRIBUTE_PRO_STARTAPP:
        plan = "pro"
    else:
        return _ok({"ignored": "unknown_startapp", "startapp": evt.startapp})

    await set_subscription(chat_id, plan, days=SUBSCRIPTION_DAYS)

    lang = await _resolve_lang(chat_id)
    await _notify(bot, chat_id, _pay_text(lang, plan, SUBSCRIPTION_DAYS))

    if evt.event_id:
        await _mark_processed(evt.event_id, plan, SUBSCRIPTION_DAYS, evt.amount, evt.currency, evt.startapp)

    try:
        rewarded, paid_count, referrer_id = await process_referral_reward_if_needed(chat_id)
        if referrer_id:
            ref_lang = await _resolve_lang(referrer_id)
            await _notify(bot, referrer_id, _ref_text(ref_lang, int(paid_count or 0), bool(rewarded)))
    except Exception as e:
        log.warning("referral reward processing failed for buyer %s: %s", chat_id, e)

    log.info(
        "Tribute processed: user=%s plan=%s amount=%s %s startapp=%s event_id=%s",
        chat_id,
        plan,
        evt.amount,
        evt.currency,
        evt.startapp,
        evt.event_id,
    )

    return _ok({"plan": plan, "days": SUBSCRIPTION_DAYS, "chat_id": chat_id})
