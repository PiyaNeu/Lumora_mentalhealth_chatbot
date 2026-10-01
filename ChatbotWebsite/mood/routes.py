from flask import Blueprint, flash, jsonify, make_response, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ChatbotWebsite.models import MOOD_EMOJI, MOOD_LABELS
from ChatbotWebsite.mood import analytics
from ChatbotWebsite.mood.pdf import build_mood_report
from ChatbotWebsite.mood.service import mood_entries, mood_points, mood_rows, record_manual, sentiment_points
from ChatbotWebsite.utils import local_now, local_today

mood = Blueprint("mood", __name__)

PERIODS = ("daily", "weekly", "monthly")


@mood.route("/")
@login_required
def dashboard():
    points = mood_points(current_user.id)
    today = local_today()
    todays = next((e for e in mood_entries(current_user.id)
                   if e.source == "Manual" and e.day == today), None)
    return render_template("mood/dashboard.html", title="Mood Dashboard",
                           stats=analytics.stats(points, today), insight=analytics.insight(points, today),
                           labels=MOOD_LABELS, emoji=MOOD_EMOJI, todays=todays)


@mood.route("/checkin", methods=["POST"])
@login_required
def checkin():
    value = request.form.get("mood", type=int)
    if value not in MOOD_LABELS:
        flash("Please choose a mood from 1 to 5.", "danger")
        return redirect(url_for("mood.dashboard"))
    _, created = record_manual(current_user.id, value, request.form.get("note"))
    if created:
        flash(f"Mood saved: {MOOD_LABELS[value]}.", "success")
    else:
        flash(f"You already checked in today, so today's mood was updated to {MOOD_LABELS[value]}.", "info")
    return redirect(url_for("mood.dashboard"))


@mood.route("/data")
@login_required
def data():
    """Chart data for the dashboard. ?period=daily|weekly|monthly"""
    period = request.args.get("period", "daily")
    if period not in PERIODS:
        period = "daily"
    moods, sentiments = mood_points(current_user.id), sentiment_points(current_user.id)
    mood_series = analytics.aggregate(moods, period)
    sent_series = analytics.aggregate(sentiments, period)
    return jsonify({
        "period": period,
        "mood": {"labels": list(mood_series), "values": list(mood_series.values())},
        "sentiment": {"labels": list(sent_series), "values": list(sent_series.values())},
        "mood_vs_sentiment": analytics.aligned_daily(moods, sentiments),
    })


@mood.route("/export.pdf")
@login_required
def export_pdf():
    rows = mood_rows(current_user.id)
    if not rows:
        flash("No mood data to export yet. Add a mood check-in first.", "warning")
        return redirect(url_for("mood.dashboard"))
    points = [(dt, m) for dt, m, _ in rows]
    values = [m for _, m in points]
    direction, delta = analytics.trend(points, local_today())
    trend_text = {"up": "Improving", "down": "Declining", "stable": "Stable"}.get(direction, "Not enough data")
    if delta is not None:
        trend_text += f" ({delta:+.2f})"
    summary = {"average": sum(values) / len(values), "best": max(values), "worst": min(values),
               "latest": values[-1], "trend": trend_text, "count": len(rows)}
    pdf = build_mood_report(current_user.username, local_now(), summary, points, rows)
    resp = make_response(pdf)
    resp.headers["Content-Type"] = "application/pdf"
    resp.headers["Content-Disposition"] = f"attachment; filename=Mood_Report-{local_today():%Y-%m-%d}.pdf"
    return resp
