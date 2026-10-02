"""'Export my data' PDF: everything Lumora stores about the user, in one readable document."""
import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from xml.sax.saxutils import escape

from ChatbotWebsite.models import (MOOD_LABELS, Appointment, AssessmentResult, ChatSession, CommunityPost, Journal,
                                   MoodEntry, SavedInsight)
from ChatbotWebsite.utils import local_now, to_local

PURPLE = colors.HexColor("#5b2a9d")
LAVENDER = colors.HexColor("#f3ecff")


def _p(text, style):
    """Paragraph with user text escaped (ReportLab parses a small HTML-like markup)."""
    return Paragraph(escape(text or "").replace("\n", "<br/>"), style)


def _table(rows, widths):
    t = Table(rows, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PURPLE), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LAVENDER]), ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return t


def build_user_export(user):
    styles = getSampleStyleSheet()
    body = ParagraphStyle("b", parent=styles["Normal"], fontSize=9, leading=12)
    small = ParagraphStyle("s", parent=body, fontSize=8, textColor=colors.HexColor("#555555"))
    h1 = ParagraphStyle("h1", parent=styles["Title"], textColor=colors.HexColor("#d32f2f"), alignment=0)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], textColor=PURPLE, fontSize=13)
    fmt = "%Y-%m-%d %H:%M"

    story = [Paragraph("LUMORA <font color='#333333' size='13'>My Data Export</font>", h1),
             _p(f"User: {user.username} ({user.email})", body),
             _p(f"Account created: {to_local(user.created_at):{fmt}}" if user.created_at else "", body),
             _p(f"Generated: {local_now():{fmt}}", small), Spacer(1, 8)]

    moods = MoodEntry.query.filter_by(user_id=user.id).order_by(MoodEntry.created_at).all()
    journals = Journal.query.filter_by(user_id=user.id).order_by(Journal.date_created).all()
    sessions = ChatSession.query.filter_by(user_id=user.id).order_by(ChatSession.created_at).all()
    tests = AssessmentResult.query.filter_by(user_id=user.id).order_by(AssessmentResult.created_at).all()
    insights = SavedInsight.query.filter_by(user_id=user.id).all()
    appts = Appointment.query.filter_by(user_id=user.id).order_by(Appointment.date).all()
    posts = CommunityPost.query.filter_by(user_id=user.id).all()

    summary = [["Data", "Items"], ["Chat sessions", len(sessions)],
               ["Chat messages", sum(len(s.messages) for s in sessions)], ["Mood entries", len(moods)],
               ["Journal entries", len(journals)], ["Self-test results", len(tests)],
               ["Saved insights", len(insights)], ["Appointments", len(appts)], ["Community posts", len(posts)]]
    story += [Paragraph("Summary", h2), _table(summary, [8 * cm, 4 * cm])]

    if moods:
        rows = [["Date & time", "Mood", "Source", "Note"]]
        rows += [[f"{to_local(m.updated_at if m.source == 'Manual' else m.created_at):{fmt}}",
                  f"{m.mood} {MOOD_LABELS[m.mood]}", m.source, _p(m.note, small)] for m in moods]
        story += [Paragraph("Mood entries", h2), _table(rows, [3.5 * cm, 3 * cm, 2 * cm, 8.5 * cm])]
    if tests:
        rows = [["Date", "Test", "Score", "Result (indicative)"]]
        rows += [[f"{to_local(t.created_at):{fmt}}", t.test.upper(), t.score, t.band] for t in tests]
        story += [Paragraph("Self-test results", h2), _table(rows, [3.5 * cm, 3 * cm, 2 * cm, 8.5 * cm])]
    if appts:
        rows = [["Date", "Time", "Psychiatrist", "Payment", "Status"]]
        rows += [[a.date.isoformat(), a.time, a.psychiatrist.name, f"{a.payment_method} / {a.payment_status}",
                  a.status] for a in appts]
        story += [Paragraph("Appointments", h2), _table(rows, [2.5 * cm, 1.5 * cm, 4.5 * cm, 5 * cm, 3.5 * cm])]
    if journals:
        story += [PageBreak(), Paragraph("Journal entries", h2)]
        for j in journals:
            story += [Paragraph(f"<b>{to_local(j.date_created):{fmt}}</b> · {escape(j.mood_tag or '')} · "
                                f"{escape(j.title)}", body), _p(j.content, body), Spacer(1, 6)]
    if sessions:
        story += [PageBreak(), Paragraph("Chat conversations", h2)]
        for s in sessions:
            story.append(Paragraph(f"<b>{escape(s.title)}</b> <font size='8'>({to_local(s.created_at):{fmt}})</font>",
                                   body))
            for m in s.messages:
                who = "You" if m.role == "user" else "Lumora"
                story.append(Paragraph(f"<font color='#5b2a9d'><b>{who}:</b></font> "
                                       f"{escape(m.message).replace(chr(10), '<br/>')}", small))
            story.append(Spacer(1, 6))
    if posts:
        story += [Paragraph("Community posts (shown anonymously to others)", h2)]
        for p in posts:
            story += [Paragraph(f"<b>{escape(p.title)}</b> · {p.tag} · {p.status}", body), _p(p.body, small),
                      Spacer(1, 4)]

    story += [Spacer(1, 10), _p("This export contains personal information. Store it somewhere private.", small)]
    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm,
                      bottomMargin=1.8 * cm, title="LUMORA data export").build(story)
    return buf.getvalue()
