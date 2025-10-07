FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    # опционально: ускоряет uvloop/HTTP по умолчанию в uvicorn
    UVICORN_WORKERS=1

WORKDIR /app

# 1) Системные зависимости:
#    - fonts-dejavu-core: кириллица в PDF (ReportLab)
#    - ffmpeg: постобработка скорости в TTS (pydub использует его)
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-dejavu-core \
    ffmpeg \
 && rm -rf /var/lib/apt/lists/*

# 2) Python-зависимости (кэшируем слой с requirements отдельно)
COPY requirements.txt .
RUN python -m pip install --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# 3) Копируем приложение (вкл. ./fonts при необходимости своих ttf)
COPY . .

# --- Запуск ---
# Render/Heroku/другие PaaS прокидывают $PORT — используем его.
# Параметры:
#  --proxy-headers        : доверяем заголовкам прокси (X-Forwarded-Proto/For)
#  --forwarded-allow-ips  : разрешаем все IP прокси (или зажми по необходимости)
CMD ["sh","-c","uvicorn webhooks:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
