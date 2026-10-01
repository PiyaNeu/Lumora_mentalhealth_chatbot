import random

from flask import Blueprint, abort, jsonify, render_template, request
from flask_login import current_user, login_required

from ChatbotWebsite import db
from ChatbotWebsite.chat.language import detect_language
from ChatbotWebsite.chat.translate import to_english
from ChatbotWebsite.evaluation import metrics
from ChatbotWebsite.models import (AssessmentResult, ChatMessage, ChatSession, Journal, MoodEntry, SentimentLabel,
                                   SessionFeedback, ToolUsage)
from ChatbotWebsite.mood.service import sentiment_points
from ChatbotWebsite.sentiment import analyze, hybrid, ml_probabilities
from ChatbotWebsite.utils import local_now

evaluation = Blueprint("evaluation", __name__)

MIN_LABELS_FOR_J1 = 10


# ---------------------------------------------------------------- Manual labeling
@evaluation.route("/labeling")
@login_required
def labeling():
    limit = min(max(request.args.get("limit", 50, type=int), 10), 500)
    only_unlabeled = request.args.get("unlabeled") == "1"
    balanced = request.args.get("balanced", type=int)
    labels = {l.message_id: l.label for l in SentimentLabel.query.filter_by(user_id=current_user.id)}
    q = ChatMessage.query.filter_by(user_id=current_user.id, role="user").order_by(ChatMessage.timestamp.desc())
    if only_unlabeled and labels:
        q = q.filter(ChatMessage.id.notin_(labels))
    messages = q.limit(limit if not balanced else 2000).all()
    if balanced:
        # Up to `balanced` messages per predicted class, so all three classes get labelled
        rng = random.Random(current_user.id)
        by_class = {}
        for m in messages:
            by_class.setdefault(m.sentiment_label or "neutral", []).append(m)
        messages = [m for group in by_class.values() for m in rng.sample(group, min(balanced, len(group)))]
        messages.sort(key=lambda m: m.timestamp, reverse=True)
    return render_template("evaluation/labeling.html", title="Manual Labeling", messages=messages, labels=labels,
                           labelled=len(labels), limit=limit, only_unlabeled=only_unlabeled, balanced=balanced)


@evaluation.route("/labeling/label", methods=["POST"])
@login_required
def set_label():
    data = request.get_json(silent=True) or {}
    label = data.get("label")
    msg = db.session.get(ChatMessage, int(data.get("message_id") or 0))
    if msg is None or msg.user_id != current_user.id or msg.role != "user":
        abort(404)
    if label not in metrics.LABELS + ["clear"]:
        return jsonify({"error": "Unknown label"}), 400
    existing = SentimentLabel.query.filter_by(message_id=msg.id).first()
    if label == "clear":
        if existing:
            db.session.delete(existing)
    elif existing:
        existing.label = label
    else:
        db.session.add(SentimentLabel(message_id=msg.id, user_id=current_user.id, label=label))
    db.session.commit()
    return jsonify({"ok": True, "labelled": SentimentLabel.query.filter_by(user_id=current_user.id).count()})


# ---------------------------------------------------------------- J1
def j1_predictions(rows):
    """VADER / ML / Hybrid labels for labelled messages (translated to English first)."""
    texts = [to_english(r.message.message, detect_language(r.message.message)) for r in rows]
    try:
        ml = ml_probabilities(texts)
    except Exception:
        ml = None
    vader = [analyze(t).label for t in texts]
    ml_labels = [max(p, key=p.get) for p in ml] if ml else None
    hyb = [hybrid(t, risk_level=r.message.risk_level, ml_probs=(ml[i] if ml else None)).label
           for i, (t, r) in enumerate(zip(texts, rows))]
    preds = {"VADER": vader, "Hybrid": hyb}
    if ml_labels:
        preds = {"VADER": vader, "ML": ml_labels, "Hybrid": hyb}
    return preds


@evaluation.route("/j1")
@login_required
def j1():
    rows = SentimentLabel.query.filter_by(user_id=current_user.id).all()
    result = None
    if len(rows) >= MIN_LABELS_FOR_J1:
        result = metrics.j1([r.label for r in rows], j1_predictions(rows))
    return render_template("evaluation/j1.html", title="J1: Sentiment Model Evaluation", result=result,
                           labelled=len(rows), min_labels=MIN_LABELS_FOR_J1, labels=metrics.LABELS)


# ---------------------------------------------------------------- J2
@evaluation.route("/j2")
@login_required
def j2():
    feedback = (SessionFeedback.query.filter_by(user_id=current_user.id)
                .order_by(SessionFeedback.created_at.desc()).all())
    return render_template("evaluation/j2.html", title="J2: User Feedback Evaluation",
                           summary=metrics.j2(feedback), feedback=feedback)


# ---------------------------------------------------------------- J3
@evaluation.route("/j3")
@login_required
def j3():
    uid = current_user.id
    sessions = ChatSession.query.filter_by(user_id=uid, archived=False).all()
    points = sentiment_points(uid)  # (local time, hybrid score)
    trend, recent_avg, prev_avg = metrics.sentiment_trend(points, local_now())
    results = AssessmentResult.query.filter(AssessmentResult.user_id == uid,
                                            AssessmentResult.test.in_(["phq9", "gad7"])).all()
    engagement = {
        "Chat sessions": len(sessions),
        "Messages sent": ChatMessage.query.filter_by(user_id=uid, role="user").count(),
        "Mood check-ins": MoodEntry.query.filter_by(user_id=uid, source="Manual").count(),
        "Journal entries": Journal.query.filter_by(user_id=uid).count(),
        "Mindfulness sessions": ToolUsage.query.filter_by(user_id=uid, tool="mindfulness").count(),
        "Self-tests taken": AssessmentResult.query.filter_by(user_id=uid).count(),
    }
    weekly = metrics.weekly_engagement([s.created_at for s in sessions], points)
    return render_template("evaluation/j3.html", title="J3: Usage & Outcome Indicators", sessions_used=len(sessions),
                           trend=trend, recent_avg=recent_avg, prev_avg=prev_avg,
                           assessment=metrics.assessment_change(results), engagement=engagement, weekly=weekly,
                           correlation=metrics.pearson(weekly["sessions"], weekly["sentiment"]))
