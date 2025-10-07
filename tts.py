# tts.py
# Асинхронная озвучка текста через OpenAI TTS.
# Готовит файлы для Telegram: voice (OGG/Opus) или audio (MP3/WAV).

from __future__ import annotations

import os
import logging
from io import BytesIO
from typing import Tuple

from openai import AsyncOpenAI

log = logging.getLogger("tts")

OPENAI_API_KEY     = os.getenv("OPENAI_API_KEY", "")
OPENAI_TTS_MODEL   = os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts")  # можно задать через .env
TTS_DEFAULT_VOICE  = os.getenv("TTS_VOICE", "alloy")
TTS_DEFAULT_FORMAT = os.getenv("TTS_FORMAT", "opus")  # "opus" (OGG/voice), "mp3", "wav"

if not OPENAI_API_KEY:
    log.warning("OPENAI_API_KEY is empty: TTS will fail without it")

_client: AsyncOpenAI | None = None


def _client_lazy() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    return _client


def _mime_ext(fmt: str) -> Tuple[str, str]:
    fmt = (fmt or "").lower()
    if fmt == "mp3":
        return "audio/mpeg", "mp3"
    if fmt in {"opus", "ogg"}:
        # Telegram voice ждёт OGG контейнер с Opus кодеком
        return "audio/ogg", "ogg"
    if fmt == "wav":
        return "audio/wav", "wav"
    return "application/octet-stream", "bin"


async def tts_bytes(
    text: str,
    voice: str | None = None,
    fmt: str | None = None,
    model: str | None = None,
) -> Tuple[bytes, str, str]:
    """
    Возвращает (audio_bytes, mime, ext).
    fmt: "opus" для voice (OGG/Opus) или "mp3"/"wav" для send_audio.
    """
    if not text or not text.strip():
        raise ValueError("tts: empty text")

    voice = voice or TTS_DEFAULT_VOICE
    fmt   = (fmt or TTS_DEFAULT_FORMAT).lower()
    model = model or OPENAI_TTS_MODEL

    client = _client_lazy()

    # Основной путь — современный TTS через streaming API (SDK >= 1.99.x)
    try:
        async with client.audio.speech.with_streaming_response.create(
            model=model,
            voice=voice,
            input=text,
            response_format=fmt,  # <-- ВАЖНО: именно response_format в этой версии SDK
        ) as resp:
            buf = BytesIO()
            async for chunk in resp.iter_bytes():
                buf.write(chunk)
            audio = buf.getvalue()

        mime, ext = _mime_ext(fmt)
        return audio, mime, ext

    except TypeError as e:
        # Случай несовпадения сигнатуры (редкие кастомные сборки SDK)
        log.warning("TTS primary failed (%s). Falling back without response_format…", e)
        async with client.audio.speech.with_streaming_response.create(
            model=model,
            voice=voice,
            input=text,
        ) as resp:
            buf = BytesIO()
            async for chunk in resp.iter_bytes():
                buf.write(chunk)
            audio = buf.getvalue()
        # чаще всего тут вернётся WAV
        return audio, "audio/wav", "wav"

    except Exception as e:
        log.warning("TTS primary error (%s). Trying tts-1 fallback…", e)
        # Фоллбек на tts-1 (широко доступна)
        async with client.audio.speech.with_streaming_response.create(
            model="tts-1",
            voice=voice,
            input=text,
            response_format="mp3",
        ) as resp:
            buf = BytesIO()
            async for chunk in resp.iter_bytes():
                buf.write(chunk)
            audio = buf.getvalue()
        return audio, "audio/mpeg", "mp3"


async def tts_voice_ogg(text: str, voice: str | None = None) -> BytesIO:
    """
    Готовит файл для Telegram voice: .ogg (Opus).
    """
    audio, _, ext = await tts_bytes(text, voice=voice, fmt="opus")
    if ext != "ogg":
        log.debug("tts_voice_ogg: got %s, expected ogg; sending as-is", ext)
    bio = BytesIO(audio)
    bio.name = f"voice.{ext}"
    bio.seek(0)
    return bio


async def tts_audio_file(text: str, voice: str | None = None, fmt: str = "mp3") -> Tuple[BytesIO, str]:
    """
    Готовит файл и MIME для send_audio (mp3/wav/ogg).
    Возврат: (BytesIO, mime)
    """
    audio, mime, ext = await tts_bytes(text, voice=voice, fmt=fmt)
    bio = BytesIO(audio)
    bio.name = f"audio.{ext}"
    bio.seek(0)
    return bio, mime


def split_for_tts(text: str, max_chars: int = 3000) -> list[str]:
    """
    Безопасно режем длинный текст на куски по предложениям,
    чтобы Telegram и TTS не упирались в лимиты.
    """
    text = " ".join((text or "").split())
    if len(text) <= max_chars:
        return [text]

    out: list[str] = []
    cur = []
    cur_len = 0
    for sent in _smart_sentences(text):
        if cur_len + len(sent) + 1 > max_chars and cur:
            out.append(" ".join(cur))
            cur = [sent]
            cur_len = len(sent)
        else:
            cur.append(sent)
            cur_len += len(sent) + 1
    if cur:
        out.append(" ".join(cur))
    return out


def _smart_sentences(text: str) -> list[str]:
    end = {".", "!", "?"}
    sents, cur = [], []
    for ch in text:
        cur.append(ch)
        if ch in end:
            sents.append("".join(cur).strip())
            cur = []
    if cur:
        sents.append("".join(cur).strip())
    return sents or [text.strip()]
