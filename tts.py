# tts.py
# Асинхронная озвучка текста через OpenAI TTS.
# Делает голос понятнее: нормализует формулы/символы, расставляет паузы (SSML).

from __future__ import annotations

import os
import logging
import shutil
import re
from io import BytesIO
from typing import Tuple, Optional, Iterable

from openai import AsyncOpenAI

log = logging.getLogger("tts")

# -------- ENV / defaults --------
OPENAI_API_KEY       = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL      = os.getenv("OPENAI_BASE_URL") or None
OPENAI_TTS_MODEL     = os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts")  # основной
OPENAI_TTS_FALLBACK  = os.getenv("OPENAI_TTS_FALLBACK", "tts-1")         # фолбэк
TTS_DEFAULT_VOICE    = os.getenv("TTS_VOICE", "alloy")
TTS_DEFAULT_FORMAT   = os.getenv("TTS_FORMAT", "ogg")  # "ogg"(voice), "mp3", "wav"
TTS_USE_SSML         = os.getenv("TTS_USE_SSML", "true").lower() == "true"  # включил по умолчанию для пауз
TTS_SPEED_MIN        = float(os.getenv("TTS_SPEED_MIN", "0.8"))
TTS_SPEED_MAX        = float(os.getenv("TTS_SPEED_MAX", "1.3"))

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
    if abs(s - 1.0) < 0.02:
        return None
    return max(TTS_SPEED_MIN, min(TTS_SPEED_MAX, s))


# ---------- Нормализация текста под диктовку ----------

_LATEX_PATTERNS = [
    (r"\\\[|\\\]", " "), (r"\\\(|\\\)", " "),
    (r"\\frac\s*\{([^{}]+)\}\s*\{([^{}]+)\}", r"(\1) делить на (\2)"),
    (r"\\times", " умножить на "),
    (r"\\cdot",  " умножить на "),
    (r"\\leq", " меньше либо равно "),
    (r"\\geq", " больше либо равно "),
    (r"\\approx", " примерно равно "),
    (r"\\sqrt\{([^{}]+)\}", r"квадратный корень из \1"),
]

def _normalize_equations(text: str) -> str:
    # убираем код-блоки/инлайн-код, чтобы не диктовать бэктики
    text = re.sub(r"```.+?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"`([^`]+)`", r"\1", text)

    # латех-подобные штуки
    for pat, repl in _LATEX_PATTERNS:
        text = re.sub(pat, repl, text, flags=re.IGNORECASE)

    # степени вида 10^(-7) или a^(2) → читаемо
    text = re.sub(r"(\b10)\s*\^\s*\(?\s*(-?\d+)\s*\)?", r"\1 в степени \2", text)
    text = re.sub(r"([a-zA-Zа-яА-Я])\s*\^\s*\(?\s*(\d+)\s*\)?", r"\1 в степени \2", text)

    # символы операций
    text = text.replace("·", " умножить на ")
    text = text.replace("*", " умножить на ")
    text = text.replace("/", " делить на ")
    text = text.replace("=", " равно ")
    text = text.replace("≈", " примерно равно ")
    text = text.replace("≤", " меньше либо равно ")
    text = text.replace("≥", " больше либо равно ")
    text = text.replace("≠", " не равно ")

    # единицы/сокращения, немного озвучивания
    text = re.sub(r"\bкН\b", " килоНьютон ", text, flags=re.IGNORECASE)
    text = re.sub(r"\bН\b", " Ньютон ", text)
    text = re.sub(r"\bДж\b", " Джоуль ", text)
    text = re.sub(r"\bм/с\b", " метр в секунду ", text, flags=re.IGNORECASE)
    text = re.sub(r"\bсм\b", " сантиметр ", text, flags=re.IGNORECASE)

    # подчистим лишние обратные слэши/дубли пробелов
    text = text.replace("\\", " ")
    text = re.sub(r"\s{2,}", " ", text).strip()
    return text


def _chunk_sentences(text: str) -> list[str]:
    """
    Разбиваем на предложения аккуратнее: учитываем сокращения и числа.
    """
    text = re.sub(r"\s+", " ", text)
    # не рвём после сокращений типа "т.д.", "и т.п.", "см.", "рис."
    boundary = re.compile(r"(?<!\bт\.д)(?<!\bт\.п)(?<!\bи\.т\.д)(?<!\bсм)(?<!\bрис)\.(\s+|$)|[!?](\s+|$)", re.IGNORECASE)
    parts: list[str] = []
    start = 0
    for m in boundary.finditer(text):
        end = m.end()
        sent = text[start:end].strip()
        if sent:
            parts.append(sent)
        start = end
    tail = text[start:].strip()
    if tail:
        parts.append(tail)
    return parts if parts else [text]


def _wrap_ssml(sentences: Iterable[str], speed: Optional[float]) -> str:
    """
    Строим SSML с паузами между предложениями.
    """
    rate_attr = ""
    if speed and abs(speed - 1.0) > 1e-3:
        rate_attr = f' rate="{int(round(speed*100))}%"'
    body = []
    for s in sentences:
        # небольшие паузы внутри длинных формул через запятые/двоеточия
        s = s.replace(":", ",")
        body.append(f"<s>{s}</s><break time=\"450ms\"/>")
    inner = "".join(body)
    return f"<speak><prosody{rate_attr}>{inner}</prosody></speak>"


# ---------- FFmpeg / постобработка ----------

def _ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def _maybe_speed_postprocess(audio: bytes, fmt_ext: str, speed: Optional[float]) -> bytes:
    speed = _clamp_speed(speed)
    if not speed:
        return audio
    if not _ffmpeg_available():
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


# ---------- Основные API-функции ----------

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
    speed: 0.8..1.3 (мягкая коррекция; если недоступно — игнорируется).
    """
    if not text or not text.strip():
        raise ValueError("tts: empty text")

    # 1) нормализуем под диктовку
    text = _normalize_equations(text)
    sentences = _chunk_sentences(text)

    voice = _pick_voice(voice or TTS_DEFAULT_VOICE)
    fmt   = (fmt or TTS_DEFAULT_FORMAT).lower()
    model = model or OPENAI_TTS_MODEL
    speed = _clamp_speed(speed)

    # API понимает "ogg", не "opus"
    api_fmt = "ogg" if fmt in {"opus", "ogg"} else fmt

    client = _client_lazy()

    # 2) строим вход: SSML (по умолчанию включён) или plain
    if TTS_USE_SSML:
        input_payload = _wrap_ssml(sentences, speed)
        wants_ssml = True
    else:
        # даже без SSML добавим перевод строк для пауз
        input_payload = "\n\n".join(sentences)
        wants_ssml = False

    try:
        kwargs = dict(model=model, voice=voice, input=input_payload, format=api_fmt)
        if (speed and not wants_ssml):
            kwargs["speed"] = speed  # если не поддерживается — поймаем TypeError и повторим
        async with client.audio.speech.with_streaming_response.create(**kwargs) as resp:
            buf = BytesIO()
            async for chunk in resp.iter_bytes():
                buf.write(chunk)
            audio = buf.getvalue()

        # Пост-процесс скорости только если не SSML
        _, ext_for_post = _mime_ext(api_fmt)
        if speed and not wants_ssml:
            audio = _maybe_speed_postprocess(audio, ext_for_post, speed)

        mime, ext = _mime_ext(api_fmt)
        return audio, mime, ext

    except TypeError as e:
        log.warning("TTS primary failed (%s). Retrying w/o speed/format extras…", e)
        async with client.audio.speech.with_streaming_response.create(
            model=model, voice=voice, input=input_payload
        ) as resp:
            buf = BytesIO()
            async for chunk in resp.iter_bytes():
                buf.write(chunk)
            audio = buf.getvalue()
        if speed and not TTS_USE_SSML:
            audio = _maybe_speed_postprocess(audio, "wav", speed)
        return audio, "audio/wav", "wav"

    except Exception as e:
        log.warning("TTS error (%s). Trying fallback model %s…", e, OPENAI_TTS_FALLBACK)
        async with client.audio.speech.with_streaming_response.create(
            model=OPENAI_TTS_FALLBACK,
            voice=voice,
            input="\n\n".join(sentences),   # на фолбэке plain надёжнее
            format="mp3",
        ) as resp:
            buf = BytesIO()
            async for chunk in resp.iter_bytes():
                buf.write(chunk)
            audio = buf.getvalue()
        audio = _maybe_speed_postprocess(audio, "mp3", speed)
        return audio, "audio/mpeg", "mp3"


async def tts_voice_ogg(text: str, voice: str | None = None, speed: Optional[float] = None) -> BytesIO:
    """
    Готовит файл для Telegram voice: .ogg (Opus).
    """
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


# ---------- Разбиение на куски для длинных ответов ----------

def split_for_tts(text: str, max_chars: int = 2800) -> list[str]:
    """
    Режем по абзацам и предложениям, чтобы куски заканчивались на паузах.
    """
    text = " ".join((text or "").split())
    if len(text) <= max_chars:
        return [text]

    # Сперва абзацы
    paras = re.split(r"(?:\n\s*){2,}", text)
    out: list[str] = []
    cur = ""
    for para in paras:
        sents = _chunk_sentences(para)
        for s in sents:
            if len(cur) + len(s) + 1 > max_chars:
                if cur:
                    out.append(cur.strip())
                    cur = s
                else:
                    out.append(s[:max_chars])
                    cur = s[max_chars:]
            else:
                cur = (cur + " " + s).strip()
        if cur:
            cur += "\n\n"
    if cur.strip():
        out.append(cur.strip())
    return out
