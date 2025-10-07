# tts.py
# Асинхронная озвучка текста через OpenAI TTS.
# Готовит файлы для Telegram: voice (OGG/Opus) или audio (MP3/WAV).

from __future__ import annotations

import os
import logging
import shutil
from io import BytesIO
from typing import Tuple, Optional

from openai import AsyncOpenAI

log = logging.getLogger("tts")

# -------- ENV / defaults --------
OPENAI_API_KEY       = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL      = os.getenv("OPENAI_BASE_URL") or None
OPENAI_TTS_MODEL     = os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts")  # основной
OPENAI_TTS_FALLBACK  = os.getenv("OPENAI_TTS_FALLBACK", "tts-1")         # фолбэк
TTS_DEFAULT_VOICE    = os.getenv("TTS_VOICE", "alloy")
# ВАЖНО: для совместимости с API формат по умолчанию делаем ogg (Opus в контейнере OGG)
TTS_DEFAULT_FORMAT   = os.getenv("TTS_FORMAT", "ogg")  # "ogg"(voice), "mp3", "wav"
TTS_USE_SSML         = os.getenv("TTS_USE_SSML", "false").lower() == "true"  # если модель понимает SSML
TTS_SPEED_MIN        = float(os.getenv("TTS_SPEED_MIN", "0.7"))
TTS_SPEED_MAX        = float(os.getenv("TTS_SPEED_MAX", "1.4"))

if not OPENAI_API_KEY:
    log.warning("OPENAI_API_KEY is empty: TTS will fail without it")

_client: AsyncOpenAI | None = None

# Допустимые голоса и алиасы (устаревшие/пользовательские имена → валидные)
_ALLOWED_VOICES = {
    "nova", "shimmer", "echo", "onyx", "fable", "alloy", "ash", "sage", "coral"
}
_VOICE_ALIASES = {
    "aria": "alloy",
    "verse": "alloy",
    "v2": "alloy",
    "default": "alloy",
}

def _pick_voice(name: Optional[str]) -> str:
    if not name:
        return "alloy"
    n = str(name).strip().lower()
    if n in _ALLOWED_VOICES:
        return n
    if n in _VOICE_ALIASES:
        return _VOICE_ALIASES[n]
    # неизвестные значения не валим в ошибку — подменяем на alloy
    return "alloy"


def _client_lazy() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
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


def _clamp_speed(speed: Optional[float]) -> Optional[float]:
    if speed is None:
        return None
    try:
        s = float(speed)
    except Exception:
        return None
    # минимальные «ступени», чтобы не гонять постпроцесс ради 1–2%
    if abs(s - 1.0) < 0.02:
        return None
    return max(TTS_SPEED_MIN, min(TTS_SPEED_MAX, s))


def _wrap_ssml(text: str, speed: Optional[float]) -> str:
    """
    Если включён SSML и задана скорость — оборачиваем текст в <prosody>.
    Иначе возвращаем как есть.
    """
    if not (TTS_USE_SSML and speed and abs(speed - 1.0) > 1e-3):
        return text
    # SSML rate в %: 1.0 -> 100%, 0.9 -> 90% и т.д.
    rate_pct = int(round(speed * 100))
    return f"<speak><prosody rate=\"{rate_pct}%\">{text}</prosody></speak>"


def _ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def _maybe_speed_postprocess(audio: bytes, fmt_ext: str, speed: Optional[float]) -> bytes:
    """
    Лёгкая коррекция скорости через pydub+ffmpeg (если доступны).
    Работает и для ogg/mp3/wav. Если что-то не так — возвращаем оригинал.
    """
    speed = _clamp_speed(speed)
    if not speed:
        return audio
    if not _ffmpeg_available():
        # На slim-образах ffmpeg может отсутствовать — это ок, просто пропускаем
        log.debug("TTS speed post-process skipped: ffmpeg not found")
        return audio

    try:
        from pydub import AudioSegment
        from pydub.effects import speedup
    except Exception as e:
        log.debug("TTS speed post-process skipped: pydub not available (%s)", e)
        return audio

    try:
        src = AudioSegment.from_file(BytesIO(audio), format=fmt_ext)
        # speedup даёт нормальный тайм-скейлинг с минимальными артефактами
        # Для замедления (<1) используем ресемплинг через изменение frame_rate.
        if speed >= 1.0:
            changed = speedup(src, playback_speed=speed)
        else:
            new_frame_rate = int(src.frame_rate * speed)
            changed = src._spawn(src.raw_data, overrides={"frame_rate": new_frame_rate}).set_frame_rate(src.frame_rate)

        buf = BytesIO()
        export_fmt = "ogg" if fmt_ext == "ogg" else fmt_ext
        params = {}
        if export_fmt == "ogg":
            params["codec"] = "libopus"
        changed.export(buf, format=export_fmt, **params)
        return buf.getvalue()
    except Exception as e:
        log.debug("TTS speed post-process failed (%s), returning original", e)
        return audio


async def tts_bytes(
    text: str,
    voice: str | None = None,
    fmt: str | None = None,
    model: str | None = None,
    speed: Optional[float] = None,
) -> Tuple[bytes, str, str]:
    """
    Возвращает (audio_bytes, mime, ext).
    fmt: "ogg" для voice (OGG/Opus) или "mp3"/"wav" для send_audio.
    speed: 0.7..1.4 (мягкая коррекция; если недоступно — игнорируется).
    """
    if not text or not text.strip():
        raise ValueError("tts: empty text")

    voice = _pick_voice(voice or TTS_DEFAULT_VOICE)
    fmt   = (fmt or TTS_DEFAULT_FORMAT).lower()
    model = model or OPENAI_TTS_MODEL
    speed = _clamp_speed(speed)

    # ВАЖНО: если прилетело "opus", для API это должен быть "ogg"
    api_fmt = "ogg" if fmt in {"opus", "ogg"} else fmt

    client = _client_lazy()
    text_or_ssml = _wrap_ssml(text, speed)
    wants_ssml = text_or_ssml != text

    # Основной путь — современный TTS (SDK >= 1.99.x)
    try:
        kwargs = dict(model=model, voice=voice, input=text_or_ssml, format=api_fmt)
        # Если мы не использовали SSML, но скорость задана, попробуем (молчаливо) передать как vendor-hint.
        if (speed and not wants_ssml):
            kwargs["speed"] = speed  # если эндпоинт не знает — свалимся в TypeError

        async with client.audio.speech.with_streaming_response.create(**kwargs) as resp:
            buf = BytesIO()
            async for chunk in resp.iter_bytes():
                buf.write(chunk)
            audio = buf.getvalue()

        # Пост-процесс скорости (если задана и нет SSML)
        _, ext_for_post = _mime_ext(api_fmt)
        if speed and not wants_ssml:
            audio = _maybe_speed_postprocess(audio, ext_for_post, speed)

        mime, ext = _mime_ext(api_fmt)
        return audio, mime, ext

    except TypeError as e:
        # Случай несовпадения сигнатуры — повтор без «экзотики»
        log.warning("TTS primary failed (%s). Retrying w/o speed/format extras…", e)
        async with client.audio.speech.with_streaming_response.create(
            model=model,
            voice=voice,
            input=text_or_ssml,
        ) as resp:
            buf = BytesIO()
            async for chunk in resp.iter_bytes():
                buf.write(chunk)
            audio = buf.getvalue()
        # чаще всего тут придёт WAV
        if speed and not wants_ssml:
            audio = _maybe_speed_postprocess(audio, "wav", speed)
        return audio, "audio/wav", "wav"

    except Exception as e:
        log.warning("TTS error (%s). Trying fallback model %s…", e, OPENAI_TTS_FALLBACK)
        # Фоллбек на tts-1 (широко доступна)
        async with client.audio.speech.with_streaming_response.create(
            model=OPENAI_TTS_FALLBACK,
            voice=voice,
            input=text,         # на фоллбэке без SSML надёжнее
            format="mp3",
        ) as resp:
            buf = BytesIO()
            async for chunk in resp.iter_bytes():
                buf.write(chunk)
            audio = buf.getvalue()
        # При желании подправим скорость через ffmpeg/pydub
        audio = _maybe_speed_postprocess(audio, "mp3", speed)
        return audio, "audio/mpeg", "mp3"


async def tts_voice_ogg(text: str, voice: str | None = None, speed: Optional[float] = None) -> BytesIO:
    """
    Готовит файл для Telegram voice: .ogg (Opus).
    """
    # просим ogg (совместимо с API), а не «opus»
    audio, _, ext = await tts_bytes(text, voice=voice, fmt="ogg", speed=speed)
    bio = BytesIO(audio)
    bio.name = f"voice.{ext}"
    bio.seek(0)
    return bio


async def tts_audio_file(
    text: str,
    voice: str | None = None,
    fmt: str = "mp3",
    speed: Optional[float] = None
) -> Tuple[BytesIO, str]:
    """
    Готовит файл и MIME для send_audio (mp3/wav/ogg).
    Возврат: (BytesIO, mime)
    """
    audio, mime, ext = await tts_bytes(text, voice=voice, fmt=fmt, speed=speed)
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
