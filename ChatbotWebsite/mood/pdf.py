"""Mood report PDF (ReportLab): summary, chart and entries table (report appendix "Report PDF")."""
import io

from matplotlib.figure import Figure
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from ChatbotWebsite.models import MOOD_LABELS

LAVENDER = colors.HexColor("#f3ecff")
PURPLE = colors.HexColor("#5b2a9d")


def _chart_png(points):
    """Mood over time as a PNG (Figure API, safe inside a web request)."""
    fig = Figure(figsize=(7.5, 3.0), dpi=150)
    ax = fig.add_subplot()
    xs = [dt for dt, _ in points]
    ys = [v for _, v in points]
    ax.plot(xs, ys, marker="o", ms=3, color="#7c4dff", lw=1.2)
    ax.set_ylim(0.5, 5.5)
    ax.set_yticks([1, 2, 3, 4, 5])
    ax.set_yticklabels([f"{i} {MOOD_LABELS[i]}" for i in range(1, 6)], fontsize=7)
    ax.set_title("Mood", fontsize=9)
    ax.grid(alpha=0.3)
    ax.tick_params(axis="x", labelsize=7, rotation=30)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    buf.seek(0)
    return buf


def build_mood_report(username, generated_at, summary, points, entries):
    """Return PDF bytes.

    summary: dict with average, best, worst, latest, trend
    points:  [(local datetime, mood)] for the chart
    entries: [(local datetime, mood, source)] for the table
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=1.8 * cm, bottomMargin=1.8 * cm,
                            title="LUMORA Mood Report", author="LUMORA")
    styles = getSampleStyleSheet()
    title = ParagraphStyle("t", parent=styles["Title"], textColor=colors.HexColor("#d32f2f"),
                           alignment=0, fontSize=20, spaceAfter=2)
    small = ParagraphStyle("s", parent=styles["Normal"], fontSize=8.5, textColor=colors.HexColor("#555555"))
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], textColor=PURPLE, fontSize=12, spaceBefore=10)

    story = [
        Paragraph("LUMORA <font color='#333333' size='12'>Mood Report</font>", title),
        Paragraph(f"User: {username}", small),
        Paragraph(f"Generated: {generated_at:%Y-%m-%d %H:%M}", small),
        Spacer(1, 10),
    ]

    summary_rows = [
        ["Average mood", f"{summary['average']:.2f} ({MOOD_LABELS[round(summary['average'])]})",
         "Best", f"{summary['best']} ({MOOD_LABELS[summary['best']]})"],
        ["Latest mood", f"{summary['latest']} ({MOOD_LABELS[summary['latest']]})",
         "Worst", f"{summary['worst']} ({MOOD_LABELS[summary['worst']]})"],
        ["Trend (7 days)", summary["trend"], "Entries", str(summary["count"])],
    ]
    t = Table(summary_rows, colWidths=[3.3 * cm, 5.2 * cm, 2.2 * cm, 4.3 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LAVENDER),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#d9c8ff")),
    ]))
    story += [Paragraph("Summary", h2), t, Spacer(1, 8),
              Paragraph("Mood scale: " + " · ".join(f"{k} = {v}" for k, v in MOOD_LABELS.items()), small),
              Spacer(1, 6), Image(_chart_png(points), width=17 * cm, height=6.8 * cm)]

    rows = [["Date & Time", "Mood", "Label", "Source"]]
    rows += [[f"{dt:%Y-%m-%d %H:%M}", str(m), MOOD_LABELS[m], src] for dt, m, src in entries]
    table = Table(rows, colWidths=[5 * cm, 2 * cm, 4 * cm, 4 * cm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PURPLE),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LAVENDER]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#e0d4ff")),
    ]))
    story += [Paragraph("Entries", h2), table, Spacer(1, 12),
              Paragraph("This report is for personal reflection only. It is not a diagnosis.", small)]
    doc.build(story)
    return buf.getvalue()
