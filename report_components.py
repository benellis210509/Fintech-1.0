import os
from html import escape

from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import Image, Paragraph, Spacer, Table, TableStyle

from report_styles import (
    AMBER_SOFT, BORDER, BORDER_DARK, CONTENT_WIDTH, GREEN, GREEN_BRIGHT,
    GREEN_PALE, GREEN_SOFT, INK, MUTED, ROW, TEXT, WHITE,
)


def p(text, style):
    return Paragraph(escape(str(text if text is not None else "")), style)


def table(data, widths=None, header=True, compact=False, align="LEFT"):
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0,
              hAlign=align, splitByRow=1)
    vpad = 6 if compact else 9
    hpad = 7 if compact else 10
    style = [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), hpad),
        ("RIGHTPADDING", (0, 0), (-1, -1), hpad),
        ("TOPPADDING", (0, 0), (-1, -1), vpad),
        ("BOTTOMPADDING", (0, 0), (-1, -1), vpad),
        ("LINEBELOW", (0, 0), (-1, -2), 0.35, colors.HexColor(BORDER)),
        ("ROWBACKGROUNDS", (0, 1 if header else 0), (-1, -1),
         [colors.white, colors.HexColor(ROW)]),
    ]
    if header:
        style.extend([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(GREEN)),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("TOPPADDING", (0, 0), (-1, 0), 8),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ])
    t.setStyle(TableStyle(style))
    return t


def section_bar(title, styles, number=None):
    # White section heading with a restrained green accent line.
    prefix = (str(number).zfill(2) + "   ") if number is not None else ""
    t = Table([[p(prefix + title, styles["section_on_green"])]],
              colWidths=[CONTENT_WIDTH])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("LINEABOVE", (0, 0), (-1, 0), 2, colors.HexColor(GREEN)),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.HexColor(BORDER_DARK)),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 11),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    return t


def notice_box(text, styles):
    t = Table([[p("IMPORTANT", styles["callout_title"]), p(text, styles["notice"])]],
              colWidths=[66, CONTENT_WIDTH - 66])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(AMBER_SOFT)),
        ("BOX", (0, 0), (-1, -1), 0.55, colors.HexColor(BORDER_DARK)),
        ("LINEBEFORE", (0, 0), (0, -1), 3, colors.HexColor(GREEN)),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 11),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 11),
    ]))
    return t


def callout_box(title, body, styles, tone="green"):
    background = "#F8F8F8" if tone == "neutral" else GREEN_PALE
    accent = GREEN if tone == "green" else BORDER_DARK
    t = Table([[p(title, styles["callout_title"])],
               [p(body, styles["callout_body"])]], colWidths=[CONTENT_WIDTH])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(background)),
        ("BOX", (0, 0), (-1, -1), 0.45, colors.HexColor(BORDER)),
        ("LINEBEFORE", (0, 0), (0, -1), 3, colors.HexColor(accent)),
        ("LEFTPADDING", (0, 0), (-1, -1), 13),
        ("RIGHTPADDING", (0, 0), (-1, -1), 13),
        ("TOPPADDING", (0, 0), (-1, -1), 11),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 11),
    ]))
    return t


def metric_grid(items, styles, columns=4):
    cells = []
    card_width = (CONTENT_WIDTH - 12 * (columns - 1)) / columns
    for label, value, *note in items:
        content = [p(label, styles["metric_label"]), Spacer(1, 7),
                   p(value, styles["metric_value"])]
        if note and note[0]:
            content.extend([Spacer(1, 5), p(note[0], styles["metric_note"])])
        card = Table([[content]], colWidths=[card_width])
        card.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.white),
            ("BOX", (0, 0), (-1, -1), 0.45, colors.HexColor(BORDER)),
            ("LINEABOVE", (0, 0), (-1, 0), 2, colors.HexColor(GREEN)),
            ("LEFTPADDING", (0, 0), (-1, -1), 11),
            ("RIGHTPADDING", (0, 0), (-1, -1), 11),
            ("TOPPADDING", (0, 0), (-1, -1), 12),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ]))
        cells.append(card)

    rows = []
    for start in range(0, len(cells), columns):
        row = cells[start:start + columns]
        while len(row) < columns:
            row.append(Spacer(1, 1))
        rows.append(row)
    outer = Table(rows, colWidths=[CONTENT_WIDTH / columns] * columns,
                  hAlign="LEFT", spaceBefore=0, spaceAfter=0)
    outer.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
    ]))
    return outer


def score_card(score, grade, label, styles):
    score_text = p("{} / 100".format(score), styles["score_big"])
    status = label if str(grade).lower() == str(label).lower() else "{} - {}".format(grade, label)
    t = Table([
        [p("PORTFOLIO HEALTH", styles["metric_label"])],
        [score_text],
        [p(status, styles["score_label"])],
    ], colWidths=[170], rowHeights=[22, 62, 27])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("BOX", (0, 0), (-1, -1), 0.55, colors.HexColor(BORDER_DARK)),
        ("LINEABOVE", (0, 0), (-1, 0), 3, colors.HexColor(GREEN)),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    return t


def insight_strip(items, styles):
    rows = []
    for label, value in items:
        rows.append([p(label, styles["metric_label"]), p(value, styles["metric_value"])])
    t = Table(rows, colWidths=[185, 173])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("LINEBELOW", (0, 0), (-1, -2), 0.35, colors.HexColor(BORDER)),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 13),
        ("RIGHTPADDING", (0, 0), (-1, -1), 13),
        ("TOPPADDING", (0, 0), (-1, -1), 11),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 11),
    ]))
    return t


def add_chart(story, chart_paths, key, caption, width=7.1, height=3.0):
    path = chart_paths.get(key)
    if not path or not os.path.exists(path):
        return False
    story.append(Image(path, width=width * inch, height=height * inch))
    story.append(Paragraph(caption, _caption_style(key)))
    return True


def _caption_style(name):
    from reportlab.lib.styles import ParagraphStyle
    return ParagraphStyle(
        "Caption_{}".format(name), fontName="Helvetica", fontSize=7.1,
        leading=9.7, textColor=colors.HexColor(MUTED), spaceBefore=3,
        spaceAfter=15,
    )


def spacer(points=10):
    return Spacer(1, points)
