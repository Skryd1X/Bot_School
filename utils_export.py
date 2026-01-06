import io
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, List, Iterable

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.enums import TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem
from reportlab.lib.units import mm
from xml.sax.saxutils import escape as _xml_escape


FONT_REGULAR = "DejaVuSans.ttf"
FONT_BOLD = "DejaVuSans-Bold.ttf"

_DEFAULT_FONT_DIRS = (
    os.path.join(os.getcwd(), "fonts"),
    os.getcwd(),
    "/usr/share/fonts/truetype/dejavu",
    "/usr/local/share/fonts",
)


@dataclass(frozen=True)
class PdfConfig:
    pagesize: tuple = A4
    left_margin_mm: float = 18
    right_margin_mm: float = 18
    top_margin_mm: float = 16
    bottom_margin_mm: float = 16
    base_font_size: int = 11
    base_leading: int = 16
    title_font_size: int = 16
    title_leading: int = 20
    meta_font_size: int = 9
    meta_leading: int = 12


_fonts_ready = False


def _find_font(filename: str, extra_dirs: Optional[Iterable[str]] = None) -> Optional[str]:
    dirs = list(_DEFAULT_FONT_DIRS)
    if extra_dirs:
        for d in extra_dirs:
            if d and d not in dirs:
                dirs.insert(0, d)
    for d in dirs:
        path = os.path.join(d, filename)
        if os.path.isfile(path):
            return path
    return None


def _ensure_fonts(extra_dirs: Optional[Iterable[str]] = None) -> None:
    global _fonts_ready
    if _fonts_ready:
        return
    reg = _find_font(FONT_REGULAR, extra_dirs=extra_dirs)
    bold = _find_font(FONT_BOLD, extra_dirs=extra_dirs)
    if not reg or not bold:
        raise RuntimeError(
            f"Не найдены шрифты {FONT_REGULAR}/{FONT_BOLD}. "
            "Положите их в ./fonts или установите fonts-dejavu-core."
        )
    pdfmetrics.registerFont(TTFont("DejaVu", reg))
    pdfmetrics.registerFont(TTFont("DejaVu-Bold", bold))
    _fonts_ready = True


def _header_footer(canvas, doc, title: str) -> None:
    canvas.saveState()
    canvas.setFont("DejaVu", 8)
    w, _ = doc.pagesize
    canvas.drawString(15 * mm, 12 * mm, (title or "").strip()[:70])
    canvas.drawRightString(w - 15 * mm, 12 * mm, str(doc.page))
    canvas.restoreState()


def _styles(cfg: PdfConfig):
    styles = getSampleStyleSheet()

    if "BodyDejaVu" not in styles:
        styles.add(
            ParagraphStyle(
                name="BodyDejaVu",
                fontName="DejaVu",
                fontSize=cfg.base_font_size,
                leading=cfg.base_leading,
                alignment=TA_LEFT,
                wordWrap="CJK",
                spaceAfter=0,
            )
        )

    if "TitleDejaVu" not in styles:
        styles.add(
            ParagraphStyle(
                name="TitleDejaVu",
                fontName="DejaVu-Bold",
                fontSize=cfg.title_font_size,
                leading=cfg.title_leading,
                alignment=TA_LEFT,
                spaceAfter=6,
            )
        )

    if "MetaDejaVu" not in styles:
        styles.add(
            ParagraphStyle(
                name="MetaDejaVu",
                fontName="DejaVu",
                fontSize=cfg.meta_font_size,
                leading=cfg.meta_leading,
                textColor="#666666",
                alignment=TA_LEFT,
                spaceAfter=8,
            )
        )

    if "H2DejaVu" not in styles:
        styles.add(
            ParagraphStyle(
                name="H2DejaVu",
                fontName="DejaVu-Bold",
                fontSize=13,
                leading=17,
                spaceBefore=6,
                spaceAfter=4,
                alignment=TA_LEFT,
            )
        )

    return styles


_RE_MD_HEADER = re.compile(r"^\s{0,3}#{1,6}\s+", re.MULTILINE)
_RE_MD_BOLD_STAR = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)
_RE_MD_BOLD_UND = re.compile(r"__(.+?)__", re.DOTALL)
_RE_MD_ITALIC_STAR = re.compile(r"(?<!\w)\*(?!\s)(.+?)(?<!\s)\*(?!\w)", re.DOTALL)
_RE_MD_ITALIC_UND = re.compile(r"(?<!\w)_(?!\s)(.+?)(?<!\s)_(?!\w)", re.DOTALL)
_RE_MD_INLINE_CODE = re.compile(r"`([^`]+)`")
_RE_SPACES = re.compile(r"[ \t]{2,}")
_RE_EMPTY_LINES = re.compile(r"\n{3,}")


def _normalize_for_pdf(text: str) -> str:
    t = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    t = _RE_MD_HEADER.sub("", t)
    t = _RE_MD_BOLD_STAR.sub(r"\1", t)
    t = _RE_MD_BOLD_UND.sub(r"\1", t)
    t = _RE_MD_ITALIC_STAR.sub(r"\1", t)
    t = _RE_MD_ITALIC_UND.sub(r"\1", t)
    t = _RE_MD_INLINE_CODE.sub(r"\1", t)
    t = t.replace("\u00a0", " ")
    t = _RE_SPACES.sub(" ", t)
    t = _RE_EMPTY_LINES.sub("\n\n", t)
    return t.strip()


def _split_blocks(text: str) -> List[str]:
    if not text:
        return []
    return [b.strip() for b in text.split("\n\n") if b.strip()]


def _is_bullet_line(line: str) -> bool:
    s = (line or "").strip()
    return s.startswith(("- ", "• ", "— ", "* "))


def _strip_bullet_prefix(line: str) -> str:
    s = (line or "").strip()
    for pref in ("- ", "• ", "— ", "* "):
        if s.startswith(pref):
            return s[len(pref):].strip()
    return s


def _is_heading(block: str) -> bool:
    s = (block or "").strip()
    if not s:
        return False
    if len(s) > 90:
        return False
    if "\n" in s:
        return False
    if s.endswith(":"):
        return True
    words = s.split()
    if 1 <= len(words) <= 8 and sum(1 for ch in s if ch.isalpha() and ch.upper() == ch) >= max(3, len(s) // 6):
        return True
    return False


def _p(text: str) -> str:
    return _xml_escape(text or "").replace("\n", "<br/>")


def pdf_from_answer_text(
    answer: str,
    title: str = "Разбор задачи",
    author: str = "Учебный помощник",
    *,
    cfg: Optional[PdfConfig] = None,
    extra_font_dirs: Optional[Iterable[str]] = None,
) -> io.BytesIO:
    cleaned = _normalize_for_pdf(answer or "")
    if not cleaned:
        raise ValueError("Пустой текст для экспорта")

    cfg = cfg or PdfConfig()
    _ensure_fonts(extra_dirs=extra_font_dirs)
    styles = _styles(cfg)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=cfg.pagesize,
        leftMargin=cfg.left_margin_mm * mm,
        rightMargin=cfg.right_margin_mm * mm,
        topMargin=cfg.top_margin_mm * mm,
        bottomMargin=cfg.bottom_margin_mm * mm,
        title=title,
        author=author,
    )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    story: list = []
    story.append(Paragraph(_p(title), styles["TitleDejaVu"]))
    story.append(Paragraph(_p(f"{author} • {now}"), styles["MetaDejaVu"]))
    story.append(Spacer(1, 4 * mm))

    for block in _split_blocks(cleaned):
        lines = [ln.rstrip() for ln in block.split("\n") if ln.strip()]

        if lines and all(_is_bullet_line(ln) for ln in lines) and len(lines) >= 2:
            items = []
            for ln in lines:
                txt = _strip_bullet_prefix(ln)
                if txt:
                    items.append(ListItem(Paragraph(_p(txt), styles["BodyDejaVu"])))
            if items:
                story.append(
                    ListFlowable(
                        items,
                        bulletType="bullet",
                        leftIndent=10 * mm,
                        bulletFontName="DejaVu",
                        bulletFontSize=10,
                        bulletDedent=3 * mm,
                    )
                )
                story.append(Spacer(1, 3 * mm))
                continue

        text_block = "\n".join(lines) if lines else block
        if _is_heading(text_block):
            story.append(Paragraph(_p(text_block.rstrip(":")), styles["H2DejaVu"]))
        else:
            story.append(Paragraph(_p(text_block), styles["BodyDejaVu"]))
        story.append(Spacer(1, 3 * mm))

    def _on_page(canvas, d):
        _header_footer(canvas, d, title=title)

    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    buf.seek(0)
    return buf
