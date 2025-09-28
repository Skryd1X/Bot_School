# startbot.py
import os
import asyncio
import logging
import contextlib

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.session.aiohttp import AiohttpSession
from dotenv import load_dotenv

from handlers import router

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set in .env")

USE_TRIBUTE = os.getenv("USE_TRIBUTE", "false").lower() == "true"
RUN_TRIBUTE_WEBHOOK = os.getenv("RUN_TRIBUTE_WEBHOOK", "true").lower() == "true"

# Render пробрасывает порт в переменную PORT. Локально можно оставить WEBHOOK_PORT=8080
WEBHOOK_HOST = "0.0.0.0"
WEBHOOK_PORT = int(os.getenv("PORT") or os.getenv("WEBHOOK_PORT", "8080"))

async def _run_tribute_webhook():
    """
    Поднимает uvicorn-сервер с FastAPI-приложением (webhooks.py) для Tribute.
    Отключается, если USE_TRIBUTE или RUN_TRIBUTE_WEBHOOK = false.
    """
    if not (USE_TRIBUTE and RUN_TRIBUTE_WEBHOOK):
        return

    try:
        import uvicorn
        from webhooks import app as tribute_app
    except Exception as e:
        logging.error("Не удалось запустить вебхук Tribute: %s", e)
        return

    config = uvicorn.Config(
        app=tribute_app,
        host=WEBHOOK_HOST,
        port=WEBHOOK_PORT,
        log_level="info",
    )
    server = uvicorn.Server(config)
    logging.info("Запускаю вебхук Tribute на http://%s:%s/webhook/tribute", WEBHOOK_HOST, WEBHOOK_PORT)
    await server.serve()

async def main():
    # ВАЖНО: aiogram ждёт ЧИСЛО секунд, а не aiohttp.ClientTimeout
    session = AiohttpSession(timeout=120)
    bot = Bot(token=BOT_TOKEN, session=session)

    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    # На случай, если раньше стоял webhook-режим
    with contextlib.suppress(Exception):
        await bot.delete_webhook(drop_pending_updates=True)

    # Параллельно поднимаем FastAPI (Tribute webhook), если включено
    webhook_task = None
    if USE_TRIBUTE and RUN_TRIBUTE_WEBHOOK:
        webhook_task = asyncio.create_task(_run_tribute_webhook())

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        if webhook_task and not webhook_task.done():
            webhook_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await webhook_task
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Bot stopped")
