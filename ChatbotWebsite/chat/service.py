"""Deleting chat data safely (used by the chat page and Privacy & Data Controls).

SQLite does not enforce foreign keys here, so rows that point at deleted messages or
sessions are cleaned up explicitly: insights/feedback keep their content but lose the
link, labels and crisis events are removed with the messages they describe.
"""
from ChatbotWebsite import db
from ChatbotWebsite.models import (ChatMessage, ChatSession, CrisisEvent, MoodEntry, SavedInsight, SentimentLabel,
                                   SessionFeedback)


def _unlink_messages(msg_ids):
    if not msg_ids:
        return
    SavedInsight.query.filter(SavedInsight.message_id.in_(msg_ids)).update(
        {"message_id": None}, synchronize_session=False)
    MoodEntry.query.filter(MoodEntry.message_id.in_(msg_ids)).update(
        {"message_id": None}, synchronize_session=False)
    SentimentLabel.query.filter(SentimentLabel.message_id.in_(msg_ids)).delete(synchronize_session=False)


def delete_sessions(sessions):
    """Delete chat sessions with all their messages. Caller commits. Returns messages removed."""
    removed = 0
    for s in sessions:
        SavedInsight.query.filter_by(session_id=s.id).update({"session_id": None})
        SessionFeedback.query.filter_by(session_id=s.id).update({"session_id": None})
        CrisisEvent.query.filter_by(session_id=s.id).delete()
        msg_ids = [m.id for m in s.messages]
        _unlink_messages(msg_ids)
        removed += len(msg_ids)
        db.session.delete(s)
    return removed


def delete_messages_before(user_id, cutoff):
    """Delete a user's chat messages older than `cutoff` (UTC); drop sessions left empty.
    Caller commits. Returns messages removed."""
    old = ChatMessage.query.filter(ChatMessage.user_id == user_id, ChatMessage.timestamp < cutoff).all()
    ids = [m.id for m in old]
    _unlink_messages(ids)
    for m in old:
        db.session.delete(m)
    CrisisEvent.query.filter(CrisisEvent.user_id == user_id, CrisisEvent.created_at < cutoff).delete()
    db.session.flush()
    empty = [s for s in ChatSession.query.filter_by(user_id=user_id).all() if not s.messages]
    delete_sessions(empty)
    return len(ids)
