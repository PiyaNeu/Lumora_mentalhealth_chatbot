import json
import os
from datetime import datetime

from flask import (Blueprint, abort, flash, jsonify, redirect, render_template, request, session,
                   url_for)
from flask_login import current_user, login_required

from ChatbotWebsite import db
from ChatbotWebsite.chat.brain import MODE_LABELS, MODES
from ChatbotWebsite.chat.pipeline import process_message
from ChatbotWebsite.models import ChatMessage, ChatSession, CrisisEvent, SavedInsight
from ChatbotWebsite.mood.service import record_chat_mood
from ChatbotWebsite.sentiment import hybrid

chat = Blueprint("chat", __name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "data")

with open(os.path.join(DATA_DIR, "topics.json"), encoding="utf-8") as file:
    topics_data = json.load(file)


def get_all_topics():
    return topics_data.get("topics", [])


def get_content(title):
    for topic in topics_data.get("topics", []):
        if topic["title"] == title:
            return topic.get("content", ["No content available"])
    return ["Topic not found"]


def current_mode():
    if current_user.is_authenticated:
        return current_user.preferred_mode or "auto"
    return session.get("mode", "auto")


def _owned_session(session_id):
    chat_session = db.session.get(ChatSession, session_id)
    if chat_session is None or chat_session.user_id != current_user.id:
        abort(404)
    return chat_session


def _session_title(text):
    text = " ".join(text.split())
    return text if len(text) <= 40 else text[:39] + "…"


# Chat Page
@chat.route("/chat")
def chat_page():
    sessions, active, messages, saved_ids = [], None, [], set()
    if current_user.is_authenticated:
        sessions = (ChatSession.query.filter_by(user_id=current_user.id, archived=False)
                    .order_by(ChatSession.updated_at.desc()).all())
        session_id = request.args.get("s", type=int)
        if session_id:
            active = _owned_session(session_id)
            messages = active.messages
            saved_ids = {i.message_id for i in SavedInsight.query.filter_by(
                user_id=current_user.id, session_id=active.id)}
    return render_template("chat/chat.html", title="Chat", topics={"topics": get_all_topics()},
                           sessions=sessions, active=active, messages=messages, saved_ids=saved_ids,
                           mode=current_mode(), mode_labels=MODE_LABELS)


@chat.route("/chat/send", methods=["POST"])
def send():
    data = request.get_json(silent=True) or {}
    text = (data.get("message") or "").strip()
    if not text:
        return jsonify({"error": "Please type a message before sending."}), 400

    authed = current_user.is_authenticated
    chat_session, history, prev_user, last_bot = None, [], None, None
    if authed and data.get("session_id"):
        chat_session = _owned_session(int(data["session_id"]))
        recent = chat_session.messages[-6:]
        history = [{"role": m.role, "text": m.message} for m in recent]
        prev_user = next((m.message for m in reversed(recent) if m.role == "user"), None)
        last_bot = next((m.message for m in reversed(recent) if m.role == "bot"), None)
    elif not authed:
        # Guests: only the previous turn lives in the signed cookie; nothing goes to the database
        prev_user, last_bot = session.get("guest_prev_user"), session.get("guest_last_bot")

    reply = process_message(text, current_mode(), history, prev_user, last_bot)

    payload = {"reply": reply.text, "route": reply.route, "sos": reply.sos,
               "strategy": reply.strategy, "language": reply.language}

    if not authed:
        session["guest_prev_user"], session["guest_last_bot"] = text[:500], reply.text[:500]
        return jsonify(payload)

    now = datetime.utcnow()
    if chat_session is None:
        chat_session = ChatSession(user_id=current_user.id, title=_session_title(text), created_at=now)
        db.session.add(chat_session)
        db.session.flush()
    mood = hybrid(reply.text_en, risk_level=reply.risk)
    user_msg = ChatMessage(message=text[:4000], user_id=current_user.id, session_id=chat_session.id,
                           role="user", language=reply.language, risk_level=reply.risk, timestamp=now,
                           sentiment_compound=reply.sentiment.compound, sentiment_score=mood.score,
                           sentiment_label=mood.label)
    bot_msg = ChatMessage(message=reply.text, user_id=current_user.id, session_id=chat_session.id,
                          role="bot", route=reply.route, intent=reply.intent, confidence=reply.confidence,
                          strategy=reply.strategy, language=reply.language, risk_level=reply.risk,
                          timestamp=now)
    db.session.add_all([user_msg, bot_msg])
    db.session.flush()
    record_chat_mood(user_msg, reply.route)
    if reply.risk in ("medium", "high"):
        db.session.add(CrisisEvent(user_id=current_user.id, session_id=chat_session.id,
                                   level=reply.risk, matched=reply.matched[:120]))
    chat_session.updated_at = now
    db.session.commit()

    payload.update(session_id=chat_session.id, session_title=chat_session.title,
                   message_id=bot_msg.id, user_message_id=user_msg.id)
    return jsonify(payload)


@chat.route("/chat/sessions/<int:session_id>/delete", methods=["POST"])
@login_required
def delete_session(session_id):
    chat_session = _owned_session(session_id)
    SavedInsight.query.filter_by(session_id=session_id).update({"session_id": None})
    CrisisEvent.query.filter_by(session_id=session_id).update({"session_id": None})
    msg_ids = [m.id for m in chat_session.messages]
    if msg_ids:
        SavedInsight.query.filter(SavedInsight.message_id.in_(msg_ids)).update(
            {"message_id": None}, synchronize_session=False)
    db.session.delete(chat_session)
    db.session.commit()
    if request.is_json or request.accept_mimetypes.best == "application/json":
        return jsonify({"ok": True})
    flash("Chat deleted.", "info")
    return redirect(url_for("chat.chat_page"))


@chat.route("/chat/mode", methods=["POST"])
def set_mode():
    mode = (request.get_json(silent=True) or {}).get("mode") or request.form.get("mode")
    if mode not in MODES:
        return jsonify({"error": "Unknown mode"}), 400
    if current_user.is_authenticated:
        current_user.preferred_mode = mode
        db.session.commit()
    else:
        session["mode"] = mode
    return jsonify({"mode": mode, "label": MODE_LABELS[mode]})


@chat.route("/chat/insights", methods=["POST"])
@login_required
def save_insight():
    message_id = (request.get_json(silent=True) or {}).get("message_id")
    msg = db.session.get(ChatMessage, int(message_id)) if str(message_id or "").isdigit() else None
    if msg is None or msg.user_id != current_user.id or msg.role != "bot":
        abort(404)
    existing = SavedInsight.query.filter_by(user_id=current_user.id, message_id=msg.id).first()
    if existing is None:
        db.session.add(SavedInsight(user_id=current_user.id, message_id=msg.id,
                                    session_id=msg.session_id, content=msg.message))
        db.session.commit()
    return jsonify({"ok": True})


@chat.route("/chat/insights")
@login_required
def insights():
    saved = (SavedInsight.query.filter_by(user_id=current_user.id)
             .order_by(SavedInsight.created_at.desc()).all())
    return render_template("chat/insights.html", title="Saved Insights", insights=saved)


@chat.route("/chat/insights/<int:insight_id>/delete", methods=["POST"])
@login_required
def delete_insight(insight_id):
    insight = db.session.get(SavedInsight, insight_id)
    if insight is None or insight.user_id != current_user.id:
        abort(404)
    db.session.delete(insight)
    db.session.commit()
    flash("Insight removed.", "info")
    return redirect(url_for("chat.insights"))


# Topic Selection
@chat.route("/topic", methods=["POST"])
def topic():
    title = request.form.get("title", "")
    return jsonify({"contents": get_content(title)})
