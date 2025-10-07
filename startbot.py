# startbot.py — единый вход: polling (по умолчанию) или webhook, + опционально вебхук Tribute
import os
import asyncio
import logging
import contextlib

from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("start")

# --------- ENV ---------
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

# Режим работы:
#   MODE=polling   — локально (дефолт)
#   MODE=webhook   — только веб-приложение (Render)
MODE = os.getenv("MODE", "polling").strip().lower()

# Tribute webhook (FastAPI) — поднимаем параллельно при polling, или единственным процессом при MODE=webhook
USE_TRIBUTE = os.getenv("USE_TRIBUTE", "false").lower() == "true"
RUN_TRIBUTE_WEBHOOK = os.getenv("RUN_TRIBUTE_WEBHOOK", "false").lower() == "true"

WEBHOOK_HOST = "0.0.0.0"
WEBHOOK_PORT = int(os.getenv("PORT") or os.getenv("WEBHOOK_PORT", "8080"))  # Render кладёт порт в PORT

# --------- POLLING (Aiogram) ---------
async def run_polling():
    from aiogram import Bot, Dispatcher
    from aiogram.fsm.storage.memory import MemoryStorage
    from aiogram.client.session.aiohttp import AiohttpSession
    from handlers import router

    # таймаут обычным числом (секунды)
    session = AiohttpSession(timeout=120)
    bot = Bot(token=BOT_TOKEN, session=session)

    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    # На всякий: если когда-то включался webhook — сняем его (иначе будет конфликт).
    with contextlib.suppress(Exception):
        await bot.delete_webhook(drop_pending_updates=True)

    me = await bot.get_me()
    log.info("Start polling for bot @%s (id=%s)", me.username, me.id)

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()

# --------- Tribute webhook (FastAPI via Uvicorn) ---------
async def run_tribute_server():
    # Запускаем uvicorn с приложением из webhooks.py
    import uvicorn
    from webhooks import app as tribute_app

    config = uvicorn.Config(
        app=tribute_app,
        host=WEBHOOK_HOST,
        port=WEBHOOK_PORT,
        log_level="info",
    )
    server = uvicorn.Server(config)
    log.info("Starting Tribute webhook on http://%s:%s", WEBHOOK_HOST, WEBHOOK_PORT)
    await server.serve()

# --------- orchestrator ---------
async def main():
    if MODE == "webhook":
        # Только веб-приложение (обычно для Render).
        # В этом режиме Aiogram polling не стартуем.
        if not (USE_TRIBUTE or RUN_TRIBUTE_WEBHOOK):
            log.warning("MODE=webhook, но USE_TRIBUTE/RUN_TRIBUTE_WEBHOOK выключены — нечего запускать.")
        await run_tribute_server()
        return

    # MODE=polling — локальная разработка по умолчанию
    tasks = [asyncio.create_task(run_polling())]

    # Параллельно можно поднять Tribute webhook (например, тестировать оплаты локально через туннель)
    if USE_TRIBUTE and RUN_TRIBUTE_WEBHOOK:
        tasks.append(asyncio.create_task(run_tribute_server()))

    # Ждём завершения любой задачи
    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
    # Если что-то упало — отменяем остальные
    for t in pending:
        t.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await t

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Bot stopped")
