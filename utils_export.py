# utils_export.py
import io
import os
from datetime import datetime
from typing import Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.enums import TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.units import mm

# ---- где искать шрифты ----
FONT_DIRS = [
    os.path.join(os.getcwd(), "fonts"),                                  # ./fonts (проект)
    os.getcwd(),                                                         # корень проекта (на всякий)
    "/usr/share/fonts/truetype/dejavu",                                  # Debian/Ubuntu
    "/usr/local/share/fonts",                                            # иногда сюда кладут
]
FONT_REGULAR = "DejaVuSans.ttf"
FONT_BOLD    = "DejaVuSans-Bold.ttf"

def _find_font(name: str) -> Optional[str]:
    for d in FONT_DIRS:
        path = os.path.join(d, name)
        if os.path.isfile(path):
            return path
    return None

_fonts_ready = False
def _ensure_fonts():
    global _fonts_ready
    if _fonts_ready:
        return
    reg = _find_font(FONT_REGULAR)
    bold = _find_font(FONT_BOLD)
    if not reg or not bold:
        raise RuntimeError(
            f"{FONT_REGULAR} not found — положите шрифт в ./fonts/ "
            "или установите системный пакет fonts-dejavu-core"
        )
    pdfmetrics.registerFont(TTFont("DejaVu", reg))
    pdfmetrics.registerFont(TTFont("DejaVu-Bold", bold))
    _fonts_ready = True

def _header_footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("DejaVu", 8)
    page = f"{doc.page}"
    canvas.drawRightString(doc.pagesize[0] - 15*mm, 12*mm, page)
    canvas.restoreState()

def _build_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="BodyDejaVu",
        fontName="DejaVu",
        fontSize=11,
        leading=16,
        alignment=TA_LEFT,
    ))
    styles.add(ParagraphStyle(
        name="TitleDejaVu",
        fontName="DejaVu-Bold",
        fontSize=16,
        leading=20,
        spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        name="MetaDejaVu",
        fontName="DejaVu",
        fontSize=9,
        leading=12,
        textColor="#666666",
        spaceAfter=6,
    ))
    return styles

def _escape(text: str) -> str:
    # reportlab поддерживает простой XHTML, экранируем спецсимволы
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def pdf_from_answer_text(answer: str, title: str = "Разбор задачи", author: str = "Учебный помощник") -> io.BytesIO:
    """
    Возвращает BytesIO с готовым PDF. Требует DejaVuSans(.ttf) для кириллицы.
    """
    if not answer or not answer.strip():
        raise ValueError("Пустой текст для экспорта")

    _ensure_fonts()
    styles = _build_styles()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=18*mm, rightMargin=18*mm,
        topMargin=16*mm, bottomMargin=16*mm,
        title=title, author=author
    )

    story = []
    story.append(Paragraph(_escape(title), styles["TitleDejaVu"]))
    story.append(Paragraph(_escape(f"{author} • {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"), styles["MetaDejaVu"]))
    story.append(Spacer(1, 6*mm))

    # простое разбиение по абзацам
    paragraphs = [p.strip() for p in (answer or "").split("\n\n") if p.strip()]
    for i, p in enumerate(paragraphs):
        story.append(Paragraph(_escape(p).replace("\n", "<br/>"), styles["BodyDejaVu"]))
        story.append(Spacer(1, 3*mm))
        # необязательный перенос страниц, если абзацов много
        if (i+1) % 25 == 0:
            story.append(PageBreak())

    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    buf.seek(0)
    return buf
