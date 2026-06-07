"""
PDF RAPOR ÜRETİMİ — reportlab
=============================
Frontend'den gelen AKTİF görünüm verisini (filtreler + KPI kartları + grafik PNG'leri
+ tablolar) kurumsal bir A4 PDF rapora dönüştürür.

Tasarım kararı (kullanıcı onayladı): grafikler frontend'de recharts SVG'sinden 3x
yüksek çözünürlüklü PNG olarak üretilir ve buraya base64 olarak gelir; metin/yerleşim
burada VEKTÖREL olarak çizilir -> grafikler net, metin keskin, sayfa düzeni kurumsal.

Veri kuralı (#6): rapor yalnızca frontend'in ekranda gösterdiği GERÇEK veriyi yansıtır;
burada hiçbir değer uydurulmaz, yalnızca biçimlendirilir.
"""
from __future__ import annotations

import base64
import datetime as dt
import glob
import io
import os

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image, KeepTogether, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)
from reportlab.platypus.flowables import HRFlowable

# --- Kurumsal renk paleti (frontend ile uyumlu) ---------------------------
ACCENT = colors.HexColor("#2b6cf0")
INK = colors.HexColor("#1f2937")
MUTED = colors.HexColor("#6b7280")
CARD_BG = colors.HexColor("#f6f8fc")
HEAD_BG = colors.HexColor("#eef3fd")
BORDER = colors.HexColor("#e2e8f0")
GREEN = colors.HexColor("#1f9d57")


# --- Türkçe karakter destekli font kaydı ----------------------------------
def _register_fonts() -> tuple[str, str]:
    """Türkçe (ş/ğ/ı/İ) destekli bir TTF çiftini kaydeder. (regular, bold) döner.
    DejaVuSans (matplotlib ile gelir, taşınabilir) -> Arial (macOS) -> Helvetica."""
    candidates = []
    try:  # matplotlib bundle (anaconda'da hep var)
        import matplotlib
        mp = os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data/fonts/ttf")
        candidates.append((os.path.join(mp, "DejaVuSans.ttf"),
                           os.path.join(mp, "DejaVuSans-Bold.ttf"), "DejaVuSans"))
    except Exception:  # noqa: BLE001
        pass
    candidates.append(("/System/Library/Fonts/Supplemental/Arial.ttf",
                       "/System/Library/Fonts/Supplemental/Arial Bold.ttf", "ArialTR"))
    candidates.append(("/Library/Fonts/Arial Unicode.ttf",
                       "/Library/Fonts/Arial Unicode.ttf", "ArialUni"))
    for reg, bold, name in candidates:
        if os.path.exists(reg) and os.path.exists(bold):
            try:
                pdfmetrics.registerFont(TTFont(name, reg))
                pdfmetrics.registerFont(TTFont(name + "-Bold", bold))
                return name, name + "-Bold"
            except Exception:  # noqa: BLE001
                continue
    return "Helvetica", "Helvetica-Bold"  # son çare (Türkçe eksik olabilir)


FONT, FONT_B = _register_fonts()

# --- Paragraf stilleri ----------------------------------------------------
_title = ParagraphStyle("title", fontName=FONT_B, fontSize=18, textColor=INK, leading=22)
_brand = ParagraphStyle("brand", fontName=FONT_B, fontSize=11, textColor=ACCENT, leading=13)
_meta = ParagraphStyle("meta", fontName=FONT, fontSize=9, textColor=MUTED, leading=12)
_meta_r = ParagraphStyle("meta_r", parent=_meta, alignment=2)  # sağa hizalı
_section = ParagraphStyle("section", fontName=FONT_B, fontSize=12, textColor=INK, leading=16,
                          spaceBefore=6, spaceAfter=4)
_kpi_label = ParagraphStyle("kpi_label", fontName=FONT, fontSize=8, textColor=MUTED, leading=10)
_kpi_value = ParagraphStyle("kpi_value", fontName=FONT_B, fontSize=15, textColor=INK, leading=18)
_kpi_sub = ParagraphStyle("kpi_sub", fontName=FONT, fontSize=7, textColor=MUTED, leading=9)
_chart_title = ParagraphStyle("chart_title", fontName=FONT_B, fontSize=10, textColor=INK,
                              leading=13, spaceBefore=4, spaceAfter=3)
_cell = ParagraphStyle("cell", fontName=FONT, fontSize=8, textColor=INK, leading=10)
_cell_h = ParagraphStyle("cell_h", fontName=FONT_B, fontSize=8, textColor=colors.white, leading=10)


def _decode_png(data_url: str) -> bytes | None:
    """'data:image/png;base64,...' veya ham base64 -> bytes."""
    if not data_url:
        return None
    try:
        b64 = data_url.split(",", 1)[1] if "," in data_url else data_url
        return base64.b64decode(b64)
    except Exception:  # noqa: BLE001
        return None


def _kpi_grid(kpis: list[dict], avail_w: float, cols: int = 3) -> Table | None:
    """KPI kartlarını cols sütunlu bir ızgara tablosuna döker."""
    if not kpis:
        return None
    cells = []
    for k in kpis:
        stack = [Paragraph(str(k.get("label", "")), _kpi_label),
                 Spacer(1, 2),
                 Paragraph(str(k.get("value", "")), _kpi_value)]
        if k.get("sub"):
            stack += [Spacer(1, 1), Paragraph(str(k["sub"]), _kpi_sub)]
        cells.append(stack)
    # cols'a tamamla
    while len(cells) % cols != 0:
        cells.append("")
    rows = [cells[i:i + cols] for i in range(0, len(cells), cols)]
    cw = avail_w / cols
    t = Table(rows, colWidths=[cw] * cols)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CARD_BG),
        ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 4, colors.white),  # kartlar arası beyaz boşluk
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return t


def _chart_flow(chart: dict, avail_w: float, max_h: float = 95 * mm):
    """Bir grafiği başlık + ölçeklenmiş görsel olarak (sayfada kırılmadan) döndürür."""
    raw = _decode_png(chart.get("image", ""))
    if not raw:
        return None
    try:
        from reportlab.lib.utils import ImageReader
        iw, ih = ImageReader(io.BytesIO(raw)).getSize()
    except Exception:  # noqa: BLE001
        return None
    w = avail_w
    h = w * ih / iw
    if h > max_h:  # çok uzunsa yüksekliğe göre küçült (en-boy korunur -> kırılmaz)
        h = max_h
        w = h * iw / ih
    img = Image(io.BytesIO(raw), width=w, height=h)
    img.hAlign = "CENTER"
    flow = [Paragraph(chart.get("title", "Grafik"), _chart_title), img, Spacer(1, 8)]
    return KeepTogether(flow)


def _table_flow(tbl: dict, avail_w: float):
    """Frontend tablosunu (columns + rows) kurumsal bir reportlab tablosuna çevirir."""
    columns = tbl.get("columns") or []
    rows = tbl.get("rows") or []
    if not columns:
        return None
    head = [Paragraph(str(c), _cell_h) for c in columns]
    body = [[Paragraph(str(c), _cell) for c in r] for r in rows] or [[Paragraph("Kayıt yok", _cell)] +
                                                                     [""] * (len(columns) - 1)]
    n = len(columns)
    cw = [avail_w / n] * n
    data = [head] + body
    t = Table(data, colWidths=cw, repeatRows=1)  # başlık her sayfada tekrar
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), FONT_B),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, BORDER),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, CARD_BG]),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    t.setStyle(TableStyle(style))
    return [Paragraph(tbl.get("title", "Tablo"), _section), t, Spacer(1, 10)]


def build_report_pdf(payload: dict) -> bytes:
    """Aktif görünüm payload'ını kurumsal PDF rapora çevirir; PDF byte'larını döner."""
    page_title = str(payload.get("page_title") or "Analitik Rapor")
    machine = str(payload.get("machine") or "—")
    date_label = str(payload.get("date_label") or "—")
    kpis = payload.get("kpis") or []
    charts = payload.get("charts") or []
    tables = payload.get("tables") or []
    generated_at = dt.datetime.now().strftime("%d.%m.%Y %H:%M")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=16 * mm, rightMargin=16 * mm,
        topMargin=26 * mm, bottomMargin=16 * mm,
        title=f"{page_title} — OEE Panosu", author="OEE Panosu",
    )
    avail_w = doc.width

    story = []
    # Başlık + filtre bandı
    story.append(Paragraph(page_title, _title))
    story.append(Spacer(1, 3))
    filt = Table([[
        Paragraph(f"<b>Makine:</b> {machine}", _meta),
        Paragraph(f"<b>Tarih Aralığı:</b> {date_label}", _meta_r),
    ]], colWidths=[avail_w * 0.5, avail_w * 0.5])
    filt.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(filt)
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width="100%", thickness=1, color=BORDER, spaceAfter=10))

    # KPI ızgarası
    grid = _kpi_grid(kpis, avail_w)
    if grid is not None:
        story.append(Paragraph("Özet Göstergeler", _section))
        story.append(grid)
        story.append(Spacer(1, 12))

    # Grafikler
    chart_flows = [f for f in (_chart_flow(c, avail_w) for c in charts) if f is not None]
    if chart_flows:
        story.append(Paragraph("Grafikler", _section))
        story.extend(chart_flows)

    # Tablolar
    for tbl in tables:
        flow = _table_flow(tbl, avail_w)
        if flow:
            story.extend(flow)

    if grid is None and not chart_flows and not tables:
        story.append(Paragraph("Bu görünümde dışa aktarılacak içerik bulunamadı.", _meta))

    def _decorate(canvas, _doc):
        """Her sayfaya üst marka bandı + alt bilgi (sayfa no) çizer."""
        canvas.saveState()
        w, h = A4
        # Üst bant
        canvas.setFillColor(ACCENT)
        canvas.rect(0, h - 12 * mm, w, 12 * mm, fill=1, stroke=0)
        canvas.setFillColor(colors.white)
        canvas.setFont(FONT_B, 12)
        canvas.drawString(16 * mm, h - 8 * mm, "OEE Panosu")
        canvas.setFont(FONT, 8)
        canvas.drawRightString(w - 16 * mm, h - 8 * mm, f"Oluşturulma: {generated_at}")
        # Alt bilgi
        canvas.setStrokeColor(BORDER)
        canvas.line(16 * mm, 12 * mm, w - 16 * mm, 12 * mm)
        canvas.setFillColor(MUTED)
        canvas.setFont(FONT, 8)
        canvas.drawString(16 * mm, 8 * mm, "OEE What-If & Kök Neden Analizi")
        canvas.drawRightString(w - 16 * mm, 8 * mm, f"Sayfa {_doc.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=_decorate, onLaterPages=_decorate)
    return buf.getvalue()
