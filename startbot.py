import os
import asyncio
import logging
import contextlib

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("start")

BOT_TOKEN = (os.getenv("BOT_TOKEN") or "").strip()
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

MODE = (os.getenv("MODE") or "polling").strip().lower()

USE_TRIBUTE = (os.getenv("USE_TRIBUTE") or "false").lower() == "true"
RUN_TRIBUTE_WEBHOOK = (os.getenv("RUN_TRIBUTE_WEBHOOK") or "false").lower() == "true"

WEBHOOK_HOST = (os.getenv("WEBHOOK_HOST") or "0.0.0.0").strip()
WEBHOOK_PORT = int(os.getenv("PORT") or os.getenv("WEBHOOK_PORT") or "8080")


def _want_webhook_server() -> bool:
    if MODE == "webhook":
        return True
    if MODE in {"both", "hybrid"}:
        return True
    return bool(USE_TRIBUTE and RUN_TRIBUTE_WEBHOOK)


def _want_polling() -> bool:
    if MODE == "webhook":
        return False
    if MODE in {"polling", "both", "hybrid"}:
        return True
    return True


async def run_polling():
    from aiogram import Bot, Dispatcher
    from aiogram.fsm.storage.memory import MemoryStorage
    from aiogram.client.session.aiohttp import AiohttpSession
    from handlers import router

    session = AiohttpSession(timeout=120)
    bot = Bot(token=BOT_TOKEN, session=session)

    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    with contextlib.suppress(Exception):
        await bot.delete_webhook(drop_pending_updates=True)

    me = await bot.get_me()
    log.info("Polling started: @%s (id=%s)", me.username, me.id)

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        with contextlib.suppress(Exception):
            await bot.session.close()


async def run_webhook_server():
    import uvicorn
    from webhooks import app

    config = uvicorn.Config(
        app=app,
        host=WEBHOOK_HOST,
        port=WEBHOOK_PORT,
        log_level="info",
        access_log=False,
    )
    server = uvicorn.Server(config)

    log.info("Webhook server starting on http://%s:%s", WEBHOOK_HOST, WEBHOOK_PORT)
    try:
        await server.serve()
    except asyncio.CancelledError:
        with contextlib.suppress(Exception):
            server.should_exit = True
        raise


async def _run_until_first_exception(tasks: list[asyncio.Task]):
    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)

    exc: BaseException | None = None
    for t in done:
        with contextlib.suppress(asyncio.CancelledError):
            e = t.exception()
            if e:
                exc = e
                break

    for t in pending:
        t.cancel()
    for t in pending:
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await t

    if exc:
        raise exc


async def main():
    log.info(
        "Mode=%s | polling=%s | webhook_server=%s | tribute=%s",
        MODE,
        _want_polling(),
        _want_webhook_server(),
        "on" if USE_TRIBUTE else "off",
    )

    if MODE == "webhook" and not (USE_TRIBUTE or RUN_TRIBUTE_WEBHOOK):
        log.warning("MODE=webhook, but USE_TRIBUTE/RUN_TRIBUTE_WEBHOOK are disabled")

    tasks: list[asyncio.Task] = []

    if _want_polling():
        tasks.append(asyncio.create_task(run_polling(), name="polling"))

    if _want_webhook_server():
        tasks.append(asyncio.create_task(run_webhook_server(), name="webhook_server"))

    if not tasks:
        raise RuntimeError("Nothing to run: check MODE/USE_TRIBUTE/RUN_TRIBUTE_WEBHOOK")

    await _run_until_first_exception(tasks)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Bot stopped")
