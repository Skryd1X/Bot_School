FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render прокидывает $PORT — просто используем его.
CMD ["sh","-c","uvicorn webhooks:app --host 0.0.0.0 --port ${PORT}"]
