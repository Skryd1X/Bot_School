from __future__ import annotations

import os
import logging
import re
import shutil
from io import BytesIO
from typing import Optional, Tuple, Iterable

from openai import AsyncOpenAI

log = logging.getLogger("tts")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL") or None

OPENAI_TTS_MODEL = os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts")
OPENAI_TTS_FALLBACK = os.getenv("OPENAI_TTS_FALLBACK", "tts-1")

TTS_DEFAULT_VOICE = os.getenv("TTS_VOICE", "alloy")
TTS_DEFAULT_FORMAT = os.getenv("TTS_FORMAT", "ogg")

TTS_USE_SSML = os.getenv("TTS_USE_SSML", "true").lower() == "true"
TTS_SPEED_MIN = float(os.getenv("TTS_SPEED_MIN", "0.85"))
TTS_SPEED_MAX = float(os.getenv("TTS_SPEED_MAX", "1.25"))

if not OPENAI_API_KEY:
    log.warning("OPENAI_API_KEY is empty: TTS will fail without it")

_client: AsyncOpenAI | None = None

_ALLOWED_VOICES = {"nova", "shimmer", "echo", "onyx", "fable", "alloy", "ash", "sage", "coral"}
_VOICE_ALIASES = {"aria": "alloy", "verse": "alloy", "v2": "alloy", "default": "alloy"}


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


def _ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


_RE_CODEBLOCK = re.compile(r"```.+?```", re.DOTALL)
_RE_INLINE_CODE = re.compile(r"`([^`]+)`")
_RE_LATEX_WRAPS = re.compile(r"(\\\[|\\\]|\\\(|\\\))")
_RE_LATEX_FRAC = re.compile(r"\\frac\s*\{([^{}]+)\}\s*\{([^{}]+)\}", re.IGNORECASE)
_RE_LATEX_SQRT = re.compile(r"\\sqrt\{([^{}]+)\}", re.IGNORECASE)
_RE_SPACES = re.compile(r"\s{2,}")
_RE_TEN_POW = re.compile(r"(\b10)\s*\^\s*\(?\s*(-?\d+)\s*\)?")
_RE_LETTER_POW = re.compile(r"([a-zA-Zа-яА-Я])\s*\^\s*\(?\s*(\d+)\s*\)?", re.UNICODE)

_RE_MD_HEADER = re.compile(r"^\s{0,3}#{1,6}\s+", re.MULTILINE)
_RE_MD_BOLD_STAR = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)
_RE_MD_BOLD_UND = re.compile(r"__(.+?)__", re.DOTALL)
_RE_MD_ITALIC_STAR = re.compile(r"(?<!\w)\*(?!\s)(.+?)(?<!\s)\*(?!\w)", re.DOTALL)
_RE_MD_ITALIC_UND = re.compile(r"(?<!\w)_(?!\s)(.+?)(?<!\s)_(?!\w)", re.DOTALL)
_RE_MD_BULLET = re.compile(r"^\s*[-*•]\s+", re.MULTILINE)

_RE_MUL_STAR = re.compile(r"(?<=[0-9A-Za-zА-Яа-я\)\]])\s*\*\s*(?=[0-9A-Za-zА-Яа-я\(\[])")
_RE_DIV_SLASH = re.compile(r"(?<=[0-9A-Za-zА-Яа-я\)\]])\s*/\s*(?=[0-9A-Za-zА-Яа-я\(\[])")

_ARABIC_RE = re.compile(r"[\u0600-\u06FF]")
_DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")
_CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")


def _guess_lang(text: str) -> str:
    t = text or ""
    if _ARABIC_RE.search(t):
        return "ar"
    if _DEVANAGARI_RE.search(t):
        return "hi"
    if _CYRILLIC_RE.search(t):
        return "ru"
    tl = t.lower()
    if any(ch in tl for ch in "ğüşöçıİ".lower()):
        return "tr"
    if any(ch in tl for ch in "äöüß"):
        return "de"
    if any(ch in tl for ch in "éèêëàâîïôùûçœ"):
        return "fr"
    if any(ch in tl for ch in "ñ¡¿"):
        return "es"
    return "en"


def _strip_markdown(t: str) -> str:
    t = _RE_MD_HEADER.sub("", t)
    t = _RE_MD_BULLET.sub("", t)
    t = _RE_MD_BOLD_STAR.sub(r"\1", t)
    t = _RE_MD_BOLD_UND.sub(r"\1", t)
    t = _RE_MD_ITALIC_STAR.sub(r"\1", t)
    t = _RE_MD_ITALIC_UND.sub(r"\1", t)
    t = t.replace("**", " ").replace("__", " ")
    return t


def _normalize_text(text: str, lang: Optional[str]) -> str:
    t = (text or "").strip()
    if not t:
        return ""
    lg = (lang or _guess_lang(t)).lower()

    t = _RE_CODEBLOCK.sub(" ", t)
    t = _RE_INLINE_CODE.sub(r"\1", t)
    t = _RE_LATEX_WRAPS.sub(" ", t)
    t = _strip_markdown(t)

    if lg == "ru":
        t = _RE_LATEX_FRAC.sub(r"(\1) делить на (\2)", t)
        t = _RE_LATEX_SQRT.sub(r"квадратный корень из \1", t)

        t = t.replace("·", " умножить на ")
        t = _RE_MUL_STAR.sub(" умножить на ", t)

        t = _RE_DIV_SLASH.sub(" делить на ", t)
        t = t.replace("=", " равно ")
        t = t.replace("≈", " примерно равно ").replace("≤", " меньше либо равно ")
        t = t.replace("≥", " больше либо равно ").replace("≠", " не равно ")

        t = re.sub(r"\bкН\b", " килоНьютон ", t, flags=re.IGNORECASE)
        t = re.sub(r"\bН\b", " Ньютон ", t)
        t = re.sub(r"\bДж\b", " Джоуль ", t)
        t = re.sub(r"\bм/с\b", " метр в секунду ", t, flags=re.IGNORECASE)
        t = re.sub(r"\bсм\b", " сантиметр ", t, flags=re.IGNORECASE)
    else:
        t = _RE_LATEX_FRAC.sub(r"(\1) / (\2)", t)
        t = _RE_LATEX_SQRT.sub(r"sqrt(\1)", t)

    t = _RE_TEN_POW.sub(r"\1^(\2)", t)
    t = _RE_LETTER_POW.sub(r"\1^(\2)", t)
    t = t.replace("\\", " ")

    return _RE_SPACES.sub(" ", t).strip()


def _chunk_sentences(text: str) -> list[str]:
    t = re.sub(r"\s+", " ", text or "").strip()
    if not t:
        return []

    boundary = re.compile(
        r"(?<!\bт\.д)(?<!\bт\.п)(?<!\bи\.т\.д)(?<!\bсм)(?<!\bрис)(?<!\be\.g)(?<!\bi\.e)\.(\s+|$)|[!?](\s+|$)",
        re.IGNORECASE,
    )
    out: list[str] = []
    start = 0
    for m in boundary.finditer(t):
        s = t[start:m.end()].strip()
        if s:
            out.append(s)
        start = m.end()
    tail = t[start:].strip()
    if tail:
        out.append(tail)
    return out or [t]


def _wrap_ssml(sentences: Iterable[str], speed: Optional[float]) -> str:
    rate = ""
    if speed and abs(speed - 1.0) > 1e-3:
        rate = f' rate="{int(round(speed * 100))}%"'
    body = "".join(f"<s>{s}</s><break time=\"420ms\"/>" for s in sentences)
    return f"<speak><prosody{rate}>{body}</prosody></speak>"


def _detect_audio_format(data: bytes) -> str:
    if not data:
        return "wav"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return "wav"
    if len(data) >= 4 and data[:4] == b"OggS":
        return "ogg"
    if len(data) >= 3 and data[:3] == b"ID3":
        return "mp3"
    if len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0:
        return "mp3"
    if len(data) >= 4 and data[:4] == b"fLaC":
        return "flac"
    if len(data) >= 4 and data[:4] == b"\x1a\x45\xdf\xa3":
        return "webm"
    return "wav"


def _mime_for_ext(ext: str) -> str:
    e = (ext or "").lower()
    if e == "mp3":
        return "audio/mpeg"
    if e in {"ogg", "opus"}:
        return "audio/ogg"
    if e == "wav":
        return "audio/wav"
    return "application/octet-stream"


def _load_segment(data: bytes, fmt_hint: Optional[str] = None):
    from pydub import AudioSegment
    fmt = (fmt_hint or _detect_audio_format(data)).lower()
    return AudioSegment.from_file(BytesIO(data), format=fmt)


def _maybe_speed_segment(seg, speed: Optional[float], already_applied: bool):
    s = _clamp_speed(speed)
    if not s or already_applied:
        return seg
    try:
        from pydub.effects import speedup
    except Exception:
        return seg
    if s >= 1.0:
        return speedup(seg, playback_speed=s)
    new_rate = int(seg.frame_rate * s)
    return seg._spawn(seg.raw_data, overrides={"frame_rate": new_rate}).set_frame_rate(seg.frame_rate)


def _export_ogg_opus(seg) -> bytes:
    if not _ffmpeg_available():
        raise RuntimeError("ffmpeg not found for opus conversion")
    buf = BytesIO()
    seg.set_channels(1).set_frame_rate(48000).export(
        buf,
        format="ogg",
        codec="libopus",
        bitrate="40k",
        parameters=["-vbr", "on", "-compression_level", "10"],
    )
    return buf.getvalue()


def _response_format_from_fmt(fmt: str) -> str:
    f = (fmt or "").lower()
    if f in {"ogg", "opus"}:
        return "opus"
    if f == "mp3":
        return "mp3"
    if f == "wav":
        return "wav"
    return "opus"


async def tts_bytes(
    text: str,
    voice: str | None = None,
    fmt: str | None = None,
    model: str | None = None,
    speed: Optional[float] = None,
    lang: Optional[str] = None,
) -> Tuple[bytes, str, str]:
    t = _normalize_text(text, lang)
    if not t:
        raise ValueError("tts: empty text")

    sents = _chunk_sentences(t)
    voice_final = _pick_voice(voice or TTS_DEFAULT_VOICE)
    fmt_final = (fmt or TTS_DEFAULT_FORMAT).lower()
    model_final = model or OPENAI_TTS_MODEL
    speed_final = _clamp_speed(speed)

    response_format = _response_format_from_fmt(fmt_final)
    client = _client_lazy()

    ssml_used = False
    payload: str
    if TTS_USE_SSML and speed_final:
        payload = _wrap_ssml(sents, speed_final)
        ssml_used = True
    else:
        payload = "\n\n".join(sents)

    async def synthesize(m: str, p: str) -> bytes:
        async with client.audio.speech.with_streaming_response.create(
            model=m,
            voice=voice_final,
            input=p,
            response_format=response_format,
        ) as resp:
            buf = BytesIO()
            async for chunk in resp.iter_bytes():
                buf.write(chunk)
            return buf.getvalue()

    raw: bytes
    try:
        raw = await synthesize(model_final, payload)
    except Exception as e1:
        try:
            raw = await synthesize(model_final, "\n\n".join(sents))
            ssml_used = False
        except Exception as e2:
            log.warning("TTS primary failed: %s | retry failed: %s | fallback: %s", e1, e2, OPENAI_TTS_FALLBACK)
            raw = await synthesize(OPENAI_TTS_FALLBACK, "\n\n".join(sents))
            ssml_used = False

    ext = "ogg" if response_format == "opus" else response_format
    mime = _mime_for_ext(ext)

    need_postprocess = (fmt_final in {"ogg", "opus", "mp3", "wav"} and (fmt_final != ext or (speed_final and not ssml_used)))
    if not need_postprocess:
        return raw, mime, ext

    try:
        seg = _load_segment(raw, fmt_hint=ext)
    except Exception:
        return raw, mime, ext

    seg = _maybe_speed_segment(seg, speed_final, already_applied=ssml_used)

    if fmt_final in {"ogg", "opus"}:
        if ext == "ogg" and not (speed_final and not ssml_used):
            return raw, "audio/ogg", "ogg"
        try:
            ogg = _export_ogg_opus(seg)
            return ogg, "audio/ogg", "ogg"
        except Exception:
            buf = BytesIO()
            seg.export(buf, format="wav")
            return buf.getvalue(), "audio/wav", "wav"

    if fmt_final == "mp3":
        buf = BytesIO()
        seg.export(buf, format="mp3", bitrate="128k")
        return buf.getvalue(), "audio/mpeg", "mp3"

    buf = BytesIO()
    seg.export(buf, format="wav")
    return buf.getvalue(), "audio/wav", "wav"


async def tts_voice_ogg(
    text: str,
    voice: str | None = None,
    speed: Optional[float] = None,
    lang: Optional[str] = None,
) -> BytesIO:
    audio, _, ext = await tts_bytes(text, voice=voice, fmt="ogg", speed=speed, lang=lang)
    bio = BytesIO(audio)
    bio.name = f"voice.{ext}"
    bio.seek(0)
    return bio


async def tts_audio_file(
    text: str,
    voice: str | None = None,
    fmt: str = "mp3",
    speed: Optional[float] = None,
    lang: Optional[str] = None,
) -> Tuple[BytesIO, str]:
    audio, mime, ext = await tts_bytes(text, voice=voice, fmt=fmt, speed=speed, lang=lang)
    bio = BytesIO(audio)
    bio.name = f"audio.{ext}"
    bio.seek(0)
    return bio, mime


def split_for_tts(text: str, max_chars: int = 2800) -> list[str]:
    t = " ".join((text or "").split()).strip()
    if not t:
        return []
    if len(t) <= max_chars:
        return [t]

    parts = re.split(r"(?:\n\s*){2,}", t)
    out: list[str] = []
    cur = ""

    for para in parts:
        para = para.strip()
        if not para:
            continue
        for s in _chunk_sentences(para):
            if not s:
                continue
            if len(cur) + len(s) + 1 > max_chars:
                if cur.strip():
                    out.append(cur.strip())
                    cur = s
                else:
                    out.append(s[:max_chars])
                    cur = s[max_chars:]
            else:
                cur = (cur + " " + s).strip()
        if cur and len(cur) < max_chars - 10:
            cur += "\n\n"

    if cur.strip():
        out.append(cur.strip())

    return out
