from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet

# Restrained print palette: mostly black, white and grey with one green accent.
INK = "#111111"
TEXT = "#333333"
MUTED = "#6B6B6B"
GREEN = "#176B3A"
GREEN_BRIGHT = "#2AA866"
GREEN_MID = "#2B7A4B"
GREEN_SOFT = "#F2F7F4"
GREEN_PALE = "#FAFCFB"
AMBER = "#8A5A14"
AMBER_SOFT = "#FAF7F1"
RED = "#A12A2A"
RED_SOFT = "#FBF3F3"
BORDER = "#D8D8D8"
BORDER_DARK = "#AFAFAF"
ROW = "#F6F6F6"
ROW_ALT = "#FBFBFB"
WHITE = "#FFFFFF"
BLACK = "#000000"

PAGE_MARGIN = 42
CONTENT_WIDTH = 528
SPACE_XS = 6
SPACE_SM = 10
SPACE_MD = 16
SPACE_LG = 26
SPACE_XL = 38


def make_styles():
    base = getSampleStyleSheet()
    return {
        "cover_kicker": ParagraphStyle(
            "CoverKicker", parent=base["BodyText"], fontName="Helvetica-Bold",
            fontSize=7.5, leading=10, textColor=colors.HexColor(GREEN),
            textTransform="uppercase", spaceAfter=10,
        ),
        "cover_title": ParagraphStyle(
            "CoverTitle", parent=base["Title"], fontName="Helvetica-Bold",
            fontSize=27, leading=31, textColor=colors.HexColor(INK),
            spaceAfter=10, letterSpacing=-0.25,
        ),
        "cover_subtitle": ParagraphStyle(
            "CoverSubtitle", parent=base["BodyText"], fontName="Helvetica",
            fontSize=10, leading=15, textColor=colors.HexColor(MUTED),
            spaceAfter=22,
        ),
        "section": ParagraphStyle(
            "Section", parent=base["Heading1"], fontName="Helvetica-Bold",
            fontSize=14, leading=18, textColor=colors.HexColor(INK),
            spaceBefore=24, spaceAfter=12, keepWithNext=True,
        ),
        "section_on_green": ParagraphStyle(
            "SectionOnGreen", parent=base["Heading1"], fontName="Helvetica-Bold",
            fontSize=12.5, leading=15, textColor=colors.HexColor(INK),
        ),
        "subsection": ParagraphStyle(
            "Subsection", parent=base["Heading2"], fontName="Helvetica-Bold",
            fontSize=10.5, leading=14, textColor=colors.HexColor(INK),
            spaceBefore=15, spaceAfter=8, keepWithNext=True,
        ),
        "body": ParagraphStyle(
            "Body", parent=base["BodyText"], fontName="Helvetica",
            fontSize=8.8, leading=13.4, textColor=colors.HexColor(TEXT),
            spaceAfter=10,
        ),
        "body_bold": ParagraphStyle(
            "BodyBold", parent=base["BodyText"], fontName="Helvetica-Bold",
            fontSize=8.8, leading=13.2, textColor=colors.HexColor(INK),
            spaceAfter=8,
        ),
        "body_tight": ParagraphStyle(
            "BodyTight", parent=base["BodyText"], fontName="Helvetica",
            fontSize=8.1, leading=11.8, textColor=colors.HexColor(TEXT),
            spaceAfter=5,
        ),
        "small": ParagraphStyle(
            "Small", parent=base["BodyText"], fontName="Helvetica",
            fontSize=7.1, leading=9.7, textColor=colors.HexColor(MUTED),
            spaceAfter=5,
        ),
        "caption": ParagraphStyle(
            "Caption", parent=base["BodyText"], fontName="Helvetica",
            fontSize=7.1, leading=9.7, textColor=colors.HexColor(MUTED),
            spaceAfter=14,
        ),
        "table_head": ParagraphStyle(
            "TableHead", parent=base["BodyText"], fontName="Helvetica-Bold",
            fontSize=7.2, leading=9, textColor=colors.white,
        ),
        "table_cell": ParagraphStyle(
            "TableCell", parent=base["BodyText"], fontName="Helvetica",
            fontSize=7.25, leading=9.8, textColor=colors.HexColor(TEXT),
        ),
        "table_cell_bold": ParagraphStyle(
            "TableCellBold", parent=base["BodyText"], fontName="Helvetica-Bold",
            fontSize=7.25, leading=9.8, textColor=colors.HexColor(INK),
        ),
        "metric_label": ParagraphStyle(
            "MetricLabel", parent=base["BodyText"], fontName="Helvetica-Bold",
            fontSize=6.8, leading=8.4, textColor=colors.HexColor(MUTED),
            textTransform="uppercase",
        ),
        "metric_value": ParagraphStyle(
            "MetricValue", parent=base["BodyText"], fontName="Helvetica-Bold",
            fontSize=11.2, leading=13.8, textColor=colors.HexColor(INK),
        ),
        "metric_note": ParagraphStyle(
            "MetricNote", parent=base["BodyText"], fontName="Helvetica",
            fontSize=6.6, leading=8.4, textColor=colors.HexColor(MUTED),
        ),
        "notice": ParagraphStyle(
            "Notice", parent=base["BodyText"], fontName="Helvetica",
            fontSize=7.5, leading=10.6, textColor=colors.HexColor(TEXT),
        ),
        "callout_title": ParagraphStyle(
            "CalloutTitle", parent=base["BodyText"], fontName="Helvetica-Bold",
            fontSize=8, leading=10.5, textColor=colors.HexColor(INK),
            spaceAfter=5,
        ),
        "callout_body": ParagraphStyle(
            "CalloutBody", parent=base["BodyText"], fontName="Helvetica",
            fontSize=8, leading=11.8, textColor=colors.HexColor(TEXT),
        ),
        "score_big": ParagraphStyle(
            "ScoreBig", parent=base["Title"], fontName="Helvetica-Bold",
            fontSize=29, leading=32, textColor=colors.HexColor(GREEN), alignment=1,
        ),
        "score_label": ParagraphStyle(
            "ScoreLabel", parent=base["BodyText"], fontName="Helvetica-Bold",
            fontSize=8.2, leading=10.5, textColor=colors.HexColor(INK), alignment=1,
        ),
        "holding_title": ParagraphStyle(
            "HoldingTitle", parent=base["Heading2"], fontName="Helvetica-Bold",
            fontSize=11, leading=14, textColor=colors.HexColor(INK),
        ),
    }
