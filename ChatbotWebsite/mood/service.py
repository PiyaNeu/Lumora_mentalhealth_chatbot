"""Reading and writing mood data for one user."""
from datetime import datetime

from ChatbotWebsite import db
from ChatbotWebsite.models import ChatMessage, Journal, MoodEntry
from ChatbotWebsite.mood.analytics import mood_from_sentiment
from ChatbotWebsite.utils import local_today, to_local

# Chat replies that don't say anything about mood (greetings, "too short", etc.)
NO_MOOD_ROUTES = {"guard"}


def record_manual(user_id, mood, note=None):
    """One manual entry per local day: update today's entry if it exists. Returns (entry, created)."""
    today = local_today()
    entry = MoodEntry.query.filter_by(user_id=user_id, source="Manual", day=today).first()
    created = entry is None
    if created:
        entry = MoodEntry(user_id=user_id, source="Manual", day=today)
        db.session.add(entry)
    entry.mood = mood
    entry.note = (note or "").strip()[:300] or None
    entry.updated_at = datetime.utcnow()
    db.session.commit()
    return entry, created


def record_chat_mood(user_msg, route):
    """Add a source="Chat" mood entry derived from a user message's sentiment (not committed)."""
    if route in NO_MOOD_ROUTES or user_msg.sentiment_score is None:
        return None
    entry = MoodEntry(user_id=user_msg.user_id, source="Chat", message_id=user_msg.id,
                      mood=mood_from_sentiment(user_msg.sentiment_score),
                      day=to_local(user_msg.timestamp).date(),
                      created_at=user_msg.timestamp, updated_at=user_msg.timestamp)
    db.session.add(entry)
    return entry


def mood_entries(user_id):
    return MoodEntry.query.filter_by(user_id=user_id).order_by(MoodEntry.created_at).all()


def mood_points(user_id, include_journal=True):
    """[(local datetime, 1–5)] from manual + chat entries and (optionally) journal mood tags."""
    points = [(to_local(e.updated_at if e.source == "Manual" else e.created_at), e.mood)
              for e in mood_entries(user_id)]
    if include_journal and hasattr(Journal, "mood"):
        points += [(to_local(j.date_created), j.mood)
                   for j in Journal.query.filter_by(user_id=user_id).filter(Journal.mood.isnot(None))]
    return sorted(points, key=lambda p: p[0])


def sentiment_points(user_id):
    """[(local datetime, hybrid score)] for the user's own chat messages."""
    rows = (ChatMessage.query.filter_by(user_id=user_id, role="user")
            .filter(ChatMessage.sentiment_score.isnot(None)).order_by(ChatMessage.timestamp))
    return [(to_local(m.timestamp), m.sentiment_score) for m in rows]
