# startbot.py — единый вход: поднимаем FastAPI (Telegram + Tribute webhooks)
import os
import logging
import uvicorn
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

WEBHOOK_HOST = "0.0.0.0"
WEBHOOK_PORT = int(os.getenv("PORT") or os.getenv("WEBHOOK_PORT", "8080"))

if __name__ == "__main__":
    from webhooks import app  # FastAPI-приложение с маршрутом /webhook/telegram и /webhook/tribute
    uvicorn.run(app, host=WEBHOOK_HOST, port=WEBHOOK_PORT, log_level="info")
