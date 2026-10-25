# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Sudem Kırmız
"""Two-page A4 PDF report built with ReportLab (pure Python, embeds Poppins for Turkish text).

Page 1: who/when, photos, Skin Score with sub-scores, regional distribution, notes.
Page 2: AI comment, personal routine with weekly plan, change since the previous record.
Every dynamic string goes through `_text()` (XML-escaped, unsupported glyphs replaced),
so nothing from the model or the user can break the layout or render as empty boxes.
"""
from __future__ import annotations

import base64
import html
from datetime import datetime
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Any

from reportlab.graphics.shapes import Circle, Drawing, Rect
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from recommendation.profile import CONCERNS, SENSITIVITY, SKIN_TYPES

FONT_DIR = Path(__file__).resolve().parents[2] / "assets" / "fonts"
LOGO = Path(__file__).resolve().parents[2] / "assets" / "brand" / "logo.png"
INK = colors.HexColor("#24342B")
MUTED = colors.HexColor("#68766D")
LINE = colors.HexColor("#DDEBDE")
BRAND = colors.HexColor("#3E7655")
SOFT = colors.HexColor("#F1F8F2")
WARN_BG = colors.HexColor("#FFF9E8")
# Status palette (dataviz reference) - always paired with a text label.
STATUS = [(75, "İyi", "#0ca30c"), (55, "Orta", "#fab219"), (35, "Dikkat", "#ec835a"), (0, "Öncelikli", "#d03b3b")]
GLYPH_REPLACEMENTS = {"→": "»", "←": "«", "✓": "", "▲": "+", "▼": "-", "●": "", "◆": "", "⚠": "!", "💡": "", "👋": "", "↗": ""}
PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN = 16 * mm
CONTENT_WIDTH = PAGE_WIDTH - 2 * MARGIN


@lru_cache(maxsize=1)
def _register_fonts() -> frozenset[int]:
    """Registers Poppins once and returns the set of supported code points."""
    for weight in ("Regular", "SemiBold", "Bold"):
        if f"Poppins-{weight}" not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(f"Poppins-{weight}", str(FONT_DIR / f"Poppins-{weight}.ttf")))
    pdfmetrics.registerFontFamily("Poppins", normal="Poppins-Regular", bold="Poppins-Bold", italic="Poppins-Regular", boldItalic="Poppins-Bold")
    return frozenset(TTFont("probe", str(FONT_DIR / "Poppins-Regular.ttf")).face.charToGlyph)


def _text(value: Any) -> str:
    supported = _register_fonts()
    raw = str(value if value is not None else "–")
    for source, target in GLYPH_REPLACEMENTS.items():
        raw = raw.replace(source, target)
    raw = "".join(ch for ch in raw if ord(ch) in supported or ch in "\n\t ")
    return html.escape(raw.strip(), quote=False)


def _styles() -> dict[str, ParagraphStyle]:
    _register_fonts()
    base = ParagraphStyle("base", fontName="Poppins-Regular", fontSize=9, leading=13, textColor=INK, alignment=TA_LEFT)
    return {
        "base": base,
        "muted": ParagraphStyle("muted", parent=base, textColor=MUTED, fontSize=8, leading=11),
        "title": ParagraphStyle("title", parent=base, fontName="Poppins-Bold", fontSize=18, leading=22, spaceAfter=3),
        "h2": ParagraphStyle("h2", parent=base, fontName="Poppins-SemiBold", fontSize=12, leading=16, spaceBefore=8, spaceAfter=4, textColor=BRAND),
        "h3": ParagraphStyle("h3", parent=base, fontName="Poppins-SemiBold", fontSize=9.5, leading=13),
        "hero": ParagraphStyle("hero", parent=base, fontName="Poppins-Bold", fontSize=34, leading=38),
        "small": ParagraphStyle("small", parent=base, fontSize=7.5, leading=10),
        "bullet": ParagraphStyle("bullet", parent=base, leftIndent=9, bulletIndent=0, spaceAfter=2),
    }


def _status(score: int) -> tuple[str, colors.Color]:
    label, color = next((label, color) for threshold, label, color in STATUS if score >= threshold)
    return label, colors.HexColor(color)


def _dot(color: colors.Color, size: float = 7) -> Drawing:
    drawing = Drawing(size, size)
    drawing.add(Circle(size / 2, size / 2, size / 2, fillColor=color, strokeColor=None))
    return drawing


def _meter(score: int | None, width: float = 62 * mm, height: float = 6) -> Drawing:
    drawing = Drawing(width, height)
    if score is None:
        drawing.add(Rect(0, 0, width, height, rx=3, ry=3, fillColor=colors.HexColor("#EEF2EE"), strokeColor=None))
        return drawing
    _, color = _status(score)
    track = colors.Color(color.red, color.green, color.blue, alpha=0.18)
    drawing.add(Rect(0, 0, width, height, rx=3, ry=3, fillColor=track, strokeColor=None))
    drawing.add(Rect(0, 0, max(height, width * score / 100), height, rx=3, ry=3, fillColor=color, strokeColor=None))
    return drawing


def _image(data_uri: str | None, max_width: float, max_height: float) -> Image | Paragraph:
    if not data_uri or "," not in data_uri:
        return Paragraph(_text("Görsel yok"), _styles()["muted"])
    data = base64.b64decode(data_uri.split(",", 1)[1])
    width, height = ImageReader(BytesIO(data)).getSize()
    scale = min(max_width / width, max_height / height)
    return Image(BytesIO(data), width=width * scale, height=height * scale)


def _bullets(items: list[str], style: ParagraphStyle) -> list[Paragraph]:
    return [Paragraph(_text(item), style, bulletText="•") for item in items if item]


def _boxed(flowables: list, background: colors.Color = SOFT) -> Table:
    table = Table([[flowables]], colWidths=[CONTENT_WIDTH])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), background),
        ("BOX", (0, 0), (-1, -1), 0.6, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return table


def _grid_style(header: bool = True) -> TableStyle:
    commands = [
        ("FONTNAME", (0, 0), (-1, -1), "Poppins-Regular"), ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("TEXTCOLOR", (0, 0), (-1, -1), INK), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    if header:
        commands += [("FONTNAME", (0, 0), (-1, 0), "Poppins-SemiBold"), ("TEXTCOLOR", (0, 0), (-1, 0), MUTED)]
    return TableStyle(commands)


def _header(story: list, styles: dict, payload: dict, profile: Any | None) -> None:
    created = payload.get("created_at") or datetime.now().strftime("%Y-%m-%d %H:%M")
    name = profile.full_name if profile is not None else ""
    caption = Paragraph(_text("SkinCare Vision AI · Bakım Ön Değerlendirme Raporu"), styles["muted"])
    if LOGO.exists():
        brand = Table([[Image(str(LOGO), width=9 * mm, height=9 * mm), caption]], colWidths=[11 * mm, None])
        brand.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
        story.append(brand)
    else:
        story.append(caption)
    story.append(Paragraph(_text(name or "Cilt Analizi"), styles["title"]))
    details = [f"Tarih: {created}"]
    if profile is not None:
        skin = profile.skin
        details.append(f"Cilt tipi: {SKIN_TYPES.get(skin.skin_type, '-')}")
        details.append(f"Hassasiyet: {SENSITIVITY.get(skin.sensitivity, '-')}")
        if skin.concerns:
            details.append("Hedefler: " + ", ".join(CONCERNS[c] for c in skin.concerns))
    story.append(Paragraph(_text("  ·  ".join(details)), styles["muted"]))
    story.append(Spacer(1, 6))


def _photos(story: list, styles: dict, payload: dict) -> None:
    half = (CONTENT_WIDTH - 6 * mm) / 2
    images = [[_image(payload.get("original_uri"), half, 70 * mm), _image(payload.get("marked_uri"), half, 70 * mm)],
              [Paragraph(_text("Yüklenen fotoğraf"), styles["muted"]),
               Paragraph(_text("İşaretlenen bölgeler (kutu: model, mor halka: renk analizi, mavi halka: Gemini)"), styles["muted"])]]
    table = Table(images, colWidths=[half + 3 * mm, half + 3 * mm])
    table.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    story.append(table)


def _skin_score(story: list, styles: dict, metrics: dict | None, total_spots: int) -> None:
    story.append(Paragraph(_text("Cilt Skoru"), styles["h2"]))
    if not metrics or not metrics.get("available"):
        story.append(Paragraph(_text("Cilt metrikleri bu fotoğraf için hesaplanamadı."), styles["muted"]))
        return
    overall = metrics["overall_score"]
    label, color = _status(overall)
    hero = [Paragraph(_text(overall), styles["hero"]),
            Table([[_dot(color), Paragraph(_text(label), styles["h3"])]], colWidths=[10, 30 * mm], style=[("LEFTPADDING", (0, 0), (-1, -1), 0)]),
            Spacer(1, 4),
            Paragraph(_text(f"Cilt tonu: {metrics['skin_tone']['category']} (ITA {metrics['skin_tone']['ita']}°)"), styles["muted"]),
            Paragraph(_text(f"Toplam nokta: {total_spots}"), styles["muted"])]
    rows = []
    for key, value in metrics["scores"].items():
        name = metrics["score_labels"][key]
        if value is None:
            rows.append([Paragraph(_text(name), styles["base"]), _meter(None), Paragraph(_text("ölçülmedi"), styles["muted"])])
            continue
        status_label, status_color = _status(value)
        rows.append([Paragraph(_text(name), styles["base"]), _meter(value),
                     Table([[_dot(status_color, 6), Paragraph(_text(f"{value}  {status_label}"), styles["base"])]], colWidths=[9, 26 * mm],
                           style=[("LEFTPADDING", (0, 0), (-1, -1), 0), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")])])
    meters = Table(rows, colWidths=[38 * mm, 64 * mm, 34 * mm])
    meters.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    layout = Table([[hero, meters]], colWidths=[40 * mm, CONTENT_WIDTH - 40 * mm])
    layout.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (0, 0), 0)]))
    story.append(layout)
    story.append(Paragraph(_text("Görüntü işleme ile ölçülen görsel indekslerdir (yüksek = daha iyi); ışık ve kameradan etkilenir, tıbbi ölçüm değildir."), styles["muted"]))


def _regions(story: list, styles: dict, region_summary: dict | None, metrics: dict | None) -> None:
    if not region_summary:
        return
    story.append(Paragraph(_text("Bölgesel Dağılım"), styles["h2"]))
    region_metrics = (metrics or {}).get("regions", {})
    rows = [["Bölge", "Nokta", "Yoğunluk", "Kızarıklık dengesi", "Ton eşitliği"]]
    for region in region_summary["regions"]:
        extra = region_metrics.get(region["key"], {})
        if region["visible"]:
            rows.append([region["name"], region["count"], region["density"], extra.get("redness", "–"), extra.get("tone", "–")])
        else:
            rows.append([region["name"], "–", "kadrajda görünmüyor", "–", "–"])
    table = Table([[_text(cell) for cell in row] for row in rows], colWidths=[34 * mm, 20 * mm, 38 * mm, 40 * mm, 36 * mm])
    table.setStyle(_grid_style())
    story.append(table)
    if region_summary.get("most_affected_name"):
        story.append(Paragraph(_text(f"En yoğun bölge (alana göre): {region_summary['most_affected_name']}. Sol/sağ, fotoğrafa göredir."), styles["muted"]))


def _ai_comment(story: list, styles: dict, payload: dict) -> None:
    result = payload.get("result", {})
    vlm = payload.get("vlm_output") or {}
    story.append(Paragraph(_text("Yapay Zekâ Yorumu"), styles["h2"]))
    if not result.get("visible_observations") and not result.get("care_suggestions"):
        story.append(Paragraph(_text("Bu analiz için yapay zekâ yorumu üretilmedi."), styles["muted"]))
        return
    if result.get("visible_observations"):
        story.append(Paragraph(_text("Gözlemler"), styles["h3"]))
        story.extend(_bullets(result["visible_observations"], styles["bullet"]))
    if result.get("care_suggestions"):
        story.append(Paragraph(_text("Öneriler"), styles["h3"]))
        story.extend(_bullets(result["care_suggestions"], styles["bullet"]))
    if vlm.get("provider"):
        story.append(Paragraph(_text(f"Kaynak: {vlm['provider']} ({vlm.get('model', '')})"), styles["muted"]))


def _routine(story: list, styles: dict, routine: dict | None) -> None:
    if not routine:
        return
    story.append(Paragraph(_text("Kişisel Bakım Rutini"), styles["h2"]))
    if routine.get("focus"):
        story.append(Paragraph(_text("Odak: " + ", ".join(routine["focus"])), styles["base"]))
    for active in routine.get("actives", []):
        block = [Paragraph(_text(f"{active['name']}  ·  {active['form']}, {active['strength']}"), styles["h3"]),
                 Paragraph(_text(active["why"]), styles["base"]),
                 Paragraph(_text(f"Kullanım: {active['frequency']}"), styles["muted"])]
        block += _bullets(active.get("cautions", []), styles["small"])
        story.append(KeepTogether([_boxed(block), Spacer(1, 4)]))

    def steps(items: list[dict[str, str]]) -> list[Paragraph]:
        return [Paragraph(f"<b>{index}. {_text(item['step'])}</b><br/>{_text(item['product'])}", styles["small"]) for index, item in enumerate(items, 1)]

    half = CONTENT_WIDTH / 2 - 2 * mm
    columns = Table([[Paragraph(_text("Sabah"), styles["h3"]), Paragraph(_text("Akşam"), styles["h3"])],
                     [steps(routine["am"]), steps(routine["pm"])]], colWidths=[half, half])
    columns.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, 0), 0.6, LINE)]))
    story.append(KeepTogether([columns]))
    week = routine.get("weekly", [])
    if week:
        story.append(Paragraph(_text("Haftalık akşam planı"), styles["h3"]))
        cells = [[Paragraph(f"<b>{_text(day['day'])}</b>", styles["small"]) for day in week],
                 [[Paragraph(_text(item), styles["small"]) for item in day["actives"]] for day in week]]
        table = Table(cells, colWidths=[CONTENT_WIDTH / 7] * 7)
        table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                                   ("INNERGRID", (0, 0), (-1, -1), 0.3, LINE), ("BACKGROUND", (0, 0), (-1, 0), SOFT)]))
        story.append(KeepTogether([table]))
    if routine.get("warnings"):
        story.append(Spacer(1, 4))
        story.append(_boxed(_bullets(routine["warnings"], styles["base"]), WARN_BG))


def _comparison(story: list, styles: dict, comparison: dict | None, previous_label: str | None) -> None:
    if not comparison:
        return
    story.append(Paragraph(_text(f"Önceki Kayda Göre Değişim ({previous_label})" if previous_label else "Önceki Kayda Göre Değişim"), styles["h2"]))
    story.extend(_bullets(comparison["summary"], styles["bullet"]))
    words = {"better": "iyileşti", "worse": "geriledi", "same": "benzer", "unknown": "–"}
    rows = [["Alt skor", "Önce", "Şimdi", "Fark", "Durum"]]
    for item in comparison["scores"]:
        delta = "–" if item["delta"] is None else f"{item['delta']:+d}"
        rows.append([item["label"], item["before"] if item["before"] is not None else "–",
                     item["after"] if item["after"] is not None else "–", delta, words[item["direction"]]])
    table = Table([[_text(cell) for cell in row] for row in rows], colWidths=[48 * mm, 24 * mm, 24 * mm, 24 * mm, 48 * mm])
    table.setStyle(_grid_style())
    story.append(table)
    story.extend(_bullets(comparison.get("comparability_notes", []), styles["small"]))


def _footer(disclaimer: str):
    def draw(canvas, document) -> None:
        canvas.saveState()
        canvas.setStrokeColor(LINE)
        canvas.line(MARGIN, 14 * mm, PAGE_WIDTH - MARGIN, 14 * mm)
        canvas.setFont("Poppins-Regular", 6.5)
        canvas.setFillColor(MUTED)
        text = canvas.beginText(MARGIN, 10.5 * mm)
        for line in _wrap(disclaimer, 150):
            text.textLine(line)
        canvas.drawText(text)
        canvas.drawRightString(PAGE_WIDTH - MARGIN, 10.5 * mm, f"Sayfa {document.page}")
        canvas.drawRightString(PAGE_WIDTH - MARGIN, 7.5 * mm, "© 2026 Sudem Kırmız · SkinCare Vision AI")
        canvas.restoreState()
    return draw


def _wrap(text: str, width: int) -> list[str]:
    words, lines, current = html.unescape(_text(text)).split(), [], ""
    for word in words:
        if len(current) + len(word) + 1 > width:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    return [*lines, current][:2]


def build_pdf_report(
    payload: dict[str, Any],
    profile: Any | None = None,
    routine: dict[str, Any] | None = None,
    mismatch_hints: list[str] | None = None,
    comparison: dict[str, Any] | None = None,
    previous_label: str | None = None,
) -> bytes:
    styles = _styles()
    buffer = BytesIO()
    title = f"Cilt Raporu - {profile.full_name}" if profile is not None else "Cilt Raporu"
    document = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN, topMargin=MARGIN, bottomMargin=20 * mm,
                                 title=title, author="SkinCare Vision AI", subject="Bakım ön değerlendirme raporu")
    result = payload.get("result", {})
    metrics = payload.get("skin_metrics")
    total_spots = (metrics or {}).get("spot_counts", {}).get("total", (payload.get("skin_findings") or {}).get("summary", {}).get("total_detections", 0))

    story: list = []
    _header(story, styles, payload, profile)
    _photos(story, styles, payload)
    _skin_score(story, styles, metrics, total_spots)
    _regions(story, styles, payload.get("region_summary"), metrics)
    notes = []
    quality = result.get("image_quality") or {}
    if quality.get("notes"):
        notes.append(f"Fotoğraf kalitesi: {quality['notes']}")
    notes += mismatch_hints or []
    if notes:
        story.append(Spacer(1, 6))
        story.append(_boxed(_bullets(notes, styles["base"]), WARN_BG))
    story.append(PageBreak())
    _ai_comment(story, styles, payload)
    _routine(story, styles, routine or payload.get("routine"))
    _comparison(story, styles, comparison, previous_label)

    footer = _footer(result.get("disclaimer") or "Bu rapor tıbbi tanı değildir; yalnızca görsel bakım ön değerlendirmesidir.")
    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
