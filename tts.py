# tts.py
# Асинхронная озвучка через OpenAI TTS.
# Авто-детект формата ответа (MP3/WAV/OGG/…) -> нормализация -> экспорт в OGG/Opus для Telegram.

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
TTS_USE_SSML         = os.getenv("TTS_USE_SSML", "true").lower() == "true"
TTS_SPEED_MIN        = float(os.getenv("TTS_SPEED_MIN", "0.85"))
TTS_SPEED_MAX        = float(os.getenv("TTS_SPEED_MAX", "1.25"))

if not OPENAI_API_KEY:
    log.warning("OPENAI_API_KEY is empty: TTS will fail without it")

_client: AsyncOpenAI | None = None

_ALLOWED_VOICES = {"nova","shimmer","echo","onyx","fable","alloy","ash","sage","coral"}
_VOICE_ALIASES  = {"aria":"alloy","verse":"alloy","v2":"alloy","default":"alloy"}


# ---------- Helpers (client, speed, mime) ----------
def _pick_voice(name: Optional[str]) -> str:
    if not name: return "alloy"
    n = str(name).strip().lower()
    if n in _ALLOWED_VOICES: return n
    if n in _VOICE_ALIASES:  return _VOICE_ALIASES[n]
    return "alloy"

def _client_lazy() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
    return _client

def _mime_ext(fmt: str) -> Tuple[str, str]:
    f = (fmt or "").lower()
    if f == "mp3": return "audio/mpeg","mp3"
    if f in {"opus","ogg"}: return "audio/ogg","ogg"
    if f == "wav": return "audio/wav","wav"
    return "application/octet-stream","bin"

def _clamp_speed(speed: Optional[float]) -> Optional[float]:
    if speed is None: return None
    try: s = float(speed)
    except Exception: return None
    if abs(s-1.0) < 0.02: return None
    return max(TTS_SPEED_MIN, min(TTS_SPEED_MAX, s))

def _ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


# ---------- Текст: нормализация формул и паузы ----------
_LATEX_PATTERNS = [
    (r"\\\[|\\\]", " "), (r"\\\(|\\\)", " "),
    (r"\\frac\s*\{([^{}]+)\}\s*\{([^{}]+)\}", r"(\1) делить на (\2)"),
    (r"\\times", " умножить на "), (r"\\cdot"," умножить на "),
    (r"\\leq", " меньше либо равно "), (r"\\geq", " больше либо равно "),
    (r"\\approx", " примерно равно "), (r"\\sqrt\{([^{}]+)\}", r"квадратный корень из \1"),
]
def _normalize_equations(text: str) -> str:
    text = re.sub(r"```.+?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    for pat, repl in _LATEX_PATTERNS:
        text = re.sub(pat, repl, text, flags=re.IGNORECASE)
    text = re.sub(r"(\b10)\s*\^\s*\(?\s*(-?\d+)\s*\)?", r"\1 в степени \2", text)
    text = re.sub(r"([a-zA-Zа-яА-Я])\s*\^\s*\(?\s*(\d+)\s*\)?", r"\1 в степени \2", text)
    text = (text.replace("·"," умножить на ").replace("*"," умножить на ")
                .replace("/"," делить на ").replace("="," равно ")
                .replace("≈"," примерно равно ").replace("≤"," меньше либо равно ")
                .replace("≥"," больше либо равно ").replace("≠"," не равно "))
    text = re.sub(r"\bкН\b", " килоНьютон ", text, flags=re.IGNORECASE)
    text = re.sub(r"\bН\b", " Ньютон ", text)
    text = re.sub(r"\bДж\b", " Джоуль ", text)
    text = re.sub(r"\bм/с\b", " метр в секунду ", text, flags=re.IGNORECASE)
    text = re.sub(r"\bсм\b", " сантиметр ", text, flags=re.IGNORECASE)
    text = text.replace("\\"," ")
    return re.sub(r"\s{2,}", " ", text).strip()

def _chunk_sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text)
    boundary = re.compile(r"(?<!\bт\.д)(?<!\bт\.п)(?<!\bи\.т\.д)(?<!\bсм)(?<!\bрис)\.(\s+|$)|[!?](\s+|$)", re.IGNORECASE)
    parts, start = [], 0
    for m in boundary.finditer(text):
        s = text[start:m.end()].strip()
        if s: parts.append(s)
        start = m.end()
    tail = text[start:].strip()
    if tail: parts.append(tail)
    return parts or [text]

def _wrap_ssml(sentences: Iterable[str], speed: Optional[float]) -> str:
    rate = f' rate="{int(round(speed*100))}%\"' if speed and abs(speed-1.0)>1e-3 else ""
    body = "".join(f"<s>{s}</s><break time=\"420ms\"/>" for s in sentences)
    return f"<speak><prosody{rate}>{body}</prosody></speak>"


# ---------- Декодирование входа: авто-детект формата ----------
def _detect_audio_format(data: bytes) -> str:
    """Возвращает hint формата для pydub/ffmpeg: 'wav'|'mp3'|'ogg'|'flac'|'webm'…"""
    if len(data) < 8:
        return "wav"
    h4 = data[:4]
    h8 = data[:8]
    if h4 == b"RIFF" and data[8:12] == b"WAVE":
        return "wav"
    if h3 := data[:3]:
        if h3 == b"ID3":   # ID3 тег
            return "mp3"
    # MP3 frame sync: FF FB / F3 / F2 …
    if h2 := data[:2]:
        if h2[0] == 0xFF and (h2[1] & 0xE0) == 0xE0:
            return "mp3"
    if h4 == b"OggS":
        return "ogg"
    if h4 == b"fLaC":
        return "flac"
    if h8.startswith(b"\x1a\x45\xdf\xa3"):
        return "webm"
    return "wav"  # по умолчанию попробуем WAV

def _load_segment(data: bytes, fmt_hint: Optional[str] = None):
    """Создаёт AudioSegment из байт с авто-детектом формата."""
    try:
        from pydub import AudioSegment
    except Exception as e:
        raise RuntimeError(f"pydub not available: {e}")
    fmt = fmt_hint or _detect_audio_format(data)
    return AudioSegment.from_file(BytesIO(data), format=fmt)

def _maybe_speed_segment(seg, speed: Optional[float]):
    s = _clamp_speed(speed)
    if not s:
        return seg
    try:
        from pydub.effects import speedup
    except Exception:
        return seg
    if s >= 1.0:
        return speedup(seg, playback_speed=s)
    # замедление — ресемплинг
    new_rate = int(seg.frame_rate * s)
    return seg._spawn(seg.raw_data, overrides={"frame_rate": new_rate}).set_frame_rate(seg.frame_rate)


# ---------- Экспорт ----------
def _export_ogg_opus(seg) -> bytes:
    """Выгружает в OGG/Opus 48k mono, libopus VBR."""
    if not _ffmpeg_available():
        raise RuntimeError("ffmpeg not found for opus conversion")
    buf = BytesIO()
    seg.set_channels(1).set_frame_rate(48000).export(
        buf, format="ogg", codec="libopus",
        bitrate="40k", parameters=["-vbr","on","-compression_level","10"]
    )
    return buf.getvalue()


# ---------- Основные функции ----------
async def tts_bytes(
    text: str,
    voice: str | None = None,
    fmt: str | None = None,
    model: str | None = None,
    speed: Optional[float] = None,
) -> Tuple[bytes, str, str]:
    """
    Возвращает (audio_bytes, mime, ext).
    Требуемый fmt: "ogg" (voice), "mp3", "wav".
    """
    if not text or not text.strip():
        raise ValueError("tts: empty text")

    # нормализуем формулы/обозначения
    text = _normalize_equations(text)
    sents = _chunk_sentences(text)

    voice = _pick_voice(voice or TTS_DEFAULT_VOICE)
    fmt   = (fmt or TTS_DEFAULT_FORMAT).lower()
    model = model or OPENAI_TTS_MODEL
    speed = _clamp_speed(speed)

    client = _client_lazy()
    input_payload = _wrap_ssml(sents, speed) if TTS_USE_SSML else "\n\n".join(sents)

    async def _synthesize(_model: str, payload: str) -> bytes:
        # ВАЖНО: без параметров format/speed — разные SDK их трактуют по-разному
        async with client.audio.speech.with_streaming_response.create(
            model=_model, voice=voice, input=payload
        ) as resp:
            buf = BytesIO()
            async for chunk in resp.iter_bytes():
                buf.write(chunk)
            return buf.getvalue()

    # 1) пробуем основной TTS; 2) фолбэк plain-текстом
    try:
        raw = await _synthesize(model, input_payload)
    except Exception as e:
        log.warning("TTS primary failed: %s. Fallback to %s…", e, OPENAI_TTS_FALLBACK)
        raw = await _synthesize(OPENAI_TTS_FALLBACK, "\n\n".join(sents))

    # 2) декодируем независимо от формата (mp3/wav/…)
    try:
        seg = _load_segment(raw)
    except Exception as e:
        # иногда API отдаёт mp3 без заголовка ID3 → подскажем явно
        try:
            seg = _load_segment(raw, "mp3")
        except Exception:
            log.error("Cannot decode audio from TTS: %s", e)
            # отдаём как есть (редкий случай)
            return raw, "audio/wav", "wav"

    # 3) темп/нормализация
    seg = _maybe_speed_segment(seg, speed)

    # 4) экспорт в нужный формат
    if fmt in {"opus","ogg"}:
        try:
            ogg = _export_ogg_opus(seg)
            return ogg, "audio/ogg", "ogg"
        except Exception as e:
            log.warning("Opus export failed (%s). Returning WAV.", e)
            buf = BytesIO(); seg.export(buf, format="wav"); return buf.getvalue(), "audio/wav", "wav"
    elif fmt == "mp3":
        buf = BytesIO(); seg.export(buf, format="mp3", bitrate="128k"); return buf.getvalue(), "audio/mpeg", "mp3"
    else:
        buf = BytesIO(); seg.export(buf, format="wav"); return buf.getvalue(), "audio/wav", "wav"


async def tts_voice_ogg(text: str, voice: str | None = None, speed: Optional[float] = None) -> BytesIO:
    audio, _, ext = await tts_bytes(text, voice=voice, fmt="ogg", speed=speed)
    bio = BytesIO(audio); bio.name = f"voice.{ext}"; bio.seek(0)
    return bio

async def tts_audio_file(text: str, voice: str | None = None, fmt: str = "mp3", speed: Optional[float] = None) -> Tuple[BytesIO, str]:
    audio, mime, ext = await tts_bytes(text, voice=voice, fmt=fmt, speed=speed)
    bio = BytesIO(audio); bio.name = f"audio.{ext}"; bio.seek(0)
    return bio, mime


# ---------- Разбиение длинных ответов ----------
def split_for_tts(text: str, max_chars: int = 2800) -> list[str]:
    text = " ".join((text or "").split())
    if len(text) <= max_chars: return [text]
    paras = re.split(r"(?:\n\s*){2,}", text)
    out, cur = [], ""
    for para in paras:
        for s in _chunk_sentences(para):
            if len(cur) + len(s) + 1 > max_chars:
                if cur: out.append(cur.strip()); cur = s
                else:   out.append(s[:max_chars]); cur = s[max_chars:]
            else:
                cur = (cur + " " + s).strip()
        if cur: cur += "\n\n"
    if cur.strip(): out.append(cur.strip())
    return out
