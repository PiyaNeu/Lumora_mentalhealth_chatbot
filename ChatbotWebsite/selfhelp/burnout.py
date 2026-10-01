"""Signals-based burnout check (report appendix "Burnout Detection").

Looks for repeated low signals across mood check-ins, journal moods and chat
sentiment over the last WINDOW_DAYS days. One bad day is not burnout, so the
level only rises when low signals are both frequent and numerous. Indicative only.
"""
from datetime import datetime, timedelta

from ChatbotWebsite.models import ChatMessage, Journal, MoodEntry

WINDOW_DAYS = 14
MIN_SIGNALS = 3


def collect_signals(user_id, now=None):
    """Recent signals, newest first: dict(kind, value, low, when)."""
    since = (now or datetime.utcnow()) - timedelta(days=WINDOW_DAYS)
    signals = []
    for e in MoodEntry.query.filter(MoodEntry.user_id == user_id, MoodEntry.created_at >= since):
        when = e.updated_at if e.source == "Manual" else e.created_at
        signals.append({"kind": "mood", "value": str(e.mood), "low": e.mood <= 2, "when": when})
    for j in Journal.query.filter(Journal.user_id == user_id, Journal.date_created >= since,
                                  Journal.mood.isnot(None)):
        signals.append({"kind": "journal_mood", "value": j.mood_tag, "low": j.mood <= 2, "when": j.date_created})
    for m in ChatMessage.query.filter(ChatMessage.user_id == user_id, ChatMessage.role == "user",
                                      ChatMessage.timestamp >= since, ChatMessage.sentiment_label.isnot(None)):
        signals.append({"kind": "chat_sentiment", "value": m.sentiment_label,
                        "low": m.sentiment_label == "negative", "when": m.timestamp})
    return sorted(signals, key=lambda s: s["when"], reverse=True)


def evaluate(signals, questionnaire_band=None):
    """Return dict(level, title, why, low, total). Levels: Not enough data | Normal | Elevated | High."""
    total = len(signals)
    low = sum(s["low"] for s in signals)
    kinds_low = {s["kind"] for s in signals if s["low"]}
    ratio = low / total if total else 0

    if total < MIN_SIGNALS and not questionnaire_band:
        return {"level": "Not enough data", "title": "Not enough recent data",
                "why": "Check in with your mood, write a journal entry or chat with Lumora for a few days.",
                "low": low, "total": total}

    if total >= MIN_SIGNALS and ratio >= 0.6 and low >= 5 and len(kinds_low) >= 2:
        level = "High"
    elif total >= MIN_SIGNALS and ratio >= 0.4 and low >= 3:
        level = "Elevated"
    else:
        level = "Normal"

    # A recent questionnaire can raise (never lower) the level
    order = ["Normal", "Elevated", "High"]
    from_q = {"Low": "Normal", "Moderate": "Elevated", "High": "High"}.get(questionnaire_band)
    if from_q and order.index(from_q) > order.index(level):
        level = from_q

    title, why = {
        "Normal": ("No Burnout Detected",
                   "Your recent signals are not consistently low. Lumora looks for patterns across mood, "
                   "journaling and chat sentiment to reduce false positives."),
        "Elevated": ("Some burnout signals",
                     f"{low} of your last {total} signals were low. That can be a sign of building strain."),
        "High": ("Possible burnout",
                 f"{low} of your last {total} signals were low, across more than one source. Please take rest "
                 "seriously and consider talking to someone you trust or a professional."),
    }[level]
    return {"level": level, "title": title, "why": why, "low": low, "total": total}
