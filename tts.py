# tts.py
# Асинхронная озвучка через OpenAI TTS без спорных аргументов SDK.
# Берём WAV из API -> конвертируем локально в OGG/Opus 48k (качество для Telegram voice).

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

# ---------- Нормализация текста ----------
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

# ---------- Локальная конвертация ----------
def _ffmpeg_available() -> bool: return shutil.which("ffmpeg") is not None

def _to_ogg_opus(wav_bytes: bytes, bitrate: str = "32k") -> bytes:
    """WAV/PCM -> OGG/Opus 48k mono, VBR on (лучше для Telegram voice)."""
    if not _ffmpeg_available():
        raise RuntimeError("ffmpeg not found for opus conversion")
    try:
        from pydub import AudioSegment
    except Exception as e:
        raise RuntimeError(f"pydub not available: {e}")
    seg = AudioSegment.from_file(BytesIO(wav_bytes), format="wav").set_channels(1).set_frame_rate(48000)
    buf = BytesIO()
    seg.export(
        buf, format="ogg", codec="libopus",
        bitrate=bitrate,
        parameters=["-vbr","on","-compression_level","10"]
    )
    return buf.getvalue()

def _maybe_speed_postprocess(audio_wav: bytes, speed: Optional[float]) -> bytes:
    s = _clamp_speed(speed)
    if not s: return audio_wav
    if not _ffmpeg_available(): return audio_wav
    try:
        from pydub import AudioSegment
        from pydub.effects import speedup
    except Exception:
        return audio_wav
    src = AudioSegment.from_file(BytesIO(audio_wav), format="wav")
    if s >= 1.0:
        changed = speedup(src, playback_speed=s)
    else:
        new_rate = int(src.frame_rate * s)
        changed = src._spawn(src.raw_data, overrides={"frame_rate": new_rate}).set_frame_rate(src.frame_rate)
    buf = BytesIO(); changed.export(buf, format="wav")
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

    # 1) нормализуем
    text = _normalize_equations(text)
    sents = _chunk_sentences(text)

    voice = _pick_voice(voice or TTS_DEFAULT_VOICE)
    fmt   = (fmt or TTS_DEFAULT_FORMAT).lower()
    model = model or OPENAI_TTS_MODEL
    speed = _clamp_speed(speed)

    client = _client_lazy()

    # 2) строим вход (SSML или plain), НО НЕ передаём спорные поля (format/speed)
    input_payload = _wrap_ssml(sents, speed) if TTS_USE_SSML else "\n\n".join(sents)

    async def _synthesize(_model: str, payload: str) -> bytes:
        # Возвращаем «сырые» байты (обычно WAV/PCM) без параметров, которые ломают SDK.
        async with client.audio.speech.with_streaming_response.create(
            model=_model, voice=voice, input=payload
        ) as resp:
            buf = BytesIO()
            async for chunk in resp.iter_bytes():
                buf.write(chunk)
            return buf.getvalue()

    # основной + фолбэк
    try:
        wav = await _synthesize(model, input_payload)
    except Exception as e:
        log.warning("Основной TTS-преобразователь не удалось (метод AsyncSpeech.create()): %s. Переход на fallback…", e)
        # на фолбэке plain обычно стабильнее
        payload = "\n\n".join(sents)
        wav = await _synthesize(OPENAI_TTS_FALLBACK, payload)

    # 3) пост-процесс (темп) в WAV
    wav = _maybe_speed_postprocess(wav, speed)

    # 4) нужный формат наружу
    if fmt in {"opus","ogg"}:
        try:
            ogg = _to_ogg_opus(wav, bitrate="40k")  # чётче артикуляция
            return ogg, "audio/ogg", "ogg"
        except Exception as e:
            log.warning("Не удалось конвертировать в Opus: %s. Отдаю WAV.", e)
            return wav, "audio/wav", "wav"
    elif fmt == "mp3":
        # если очень надо mp3 — перекодируем через ogg->mp3 или прямо из wav
        try:
            from pydub import AudioSegment
            seg = AudioSegment.from_file(BytesIO(wav), format="wav")
            buf = BytesIO(); seg.export(buf, format="mp3", bitrate="128k")
            return buf.getvalue(), "audio/mpeg", "mp3"
        except Exception:
            return wav, "audio/wav", "wav"
    else:
        return wav, "audio/wav", "wav"

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
