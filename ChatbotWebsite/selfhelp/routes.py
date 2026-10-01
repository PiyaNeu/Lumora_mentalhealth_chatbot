import json
import os
from datetime import datetime, timedelta

from flask import Blueprint, abort, current_app, jsonify, render_template, request
from flask_login import current_user, login_required

from ChatbotWebsite import db
from ChatbotWebsite.models import AssessmentResult, ToolUsage
from ChatbotWebsite.selfhelp import burnout as burnout_check
from ChatbotWebsite.selfhelp.assessments import ASSESSMENTS, IncompleteAnswers, parse_answers, score

selfhelp = Blueprint("selfhelp", __name__)

QUESTIONNAIRE_FRESH_DAYS = 14


@selfhelp.route("/tests")
def tests():
    history = []
    if current_user.is_authenticated:
        history = (AssessmentResult.query.filter_by(user_id=current_user.id)
                   .order_by(AssessmentResult.created_at.desc()).limit(10).all())
    return render_template("selfhelp/tests.html", title="Self-Tests", assessments=ASSESSMENTS, history=history)


@selfhelp.route("/tests/<key>", methods=["GET", "POST"])
def take_test(key):
    if key not in ASSESSMENTS:
        abort(404)
    test = ASSESSMENTS[key]
    answers, error = [None] * len(test["questions"]), None
    if request.method == "POST":
        answers = parse_answers(key, request.form)
        try:
            result = score(key, answers)
        except IncompleteAnswers as exc:
            error = str(exc)
        else:
            if current_user.is_authenticated:
                db.session.add(AssessmentResult(user_id=current_user.id, test=key, score=result["score"],
                                                band=result["band"], answers=",".join(map(str, answers))))
                db.session.commit()
            return render_template("selfhelp/result.html", title=test["title"], key=key, test=test,
                                   result=result)
    status = 400 if error else 200
    return render_template("selfhelp/test_form.html", title=test["title"], key=key, test=test,
                           answers=answers, error=error), status


@selfhelp.route("/burnout")
@login_required
def burnout():
    signals = burnout_check.collect_signals(current_user.id)
    recent_q = (AssessmentResult.query.filter_by(user_id=current_user.id, test="burnout")
                .filter(AssessmentResult.created_at >= datetime.utcnow() - timedelta(days=QUESTIONNAIRE_FRESH_DAYS))
                .order_by(AssessmentResult.created_at.desc()).first())
    result = burnout_check.evaluate(signals, recent_q.band if recent_q else None)
    return render_template("selfhelp/burnout.html", title="Burnout Check", result=result,
                           signals=signals[:8], questionnaire=recent_q)


_MINDFULNESS = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "mindfulness.json")


def load_exercises():
    with open(_MINDFULNESS, encoding="utf-8") as fh:
        exercises = json.load(fh)["exercises"]
    audio_dir = os.path.join(current_app.static_folder, "mindfulness")
    for ex in exercises:
        ex["has_audio"] = bool(ex.get("audio")) and os.path.exists(os.path.join(audio_dir, ex["audio"]))
    return exercises


@selfhelp.route("/mindfulness")
def mindfulness():
    return render_template("selfhelp/mindfulness.html", title="Mindfulness", exercises=load_exercises())


@selfhelp.route("/mindfulness/<exercise_id>/played", methods=["POST"])
def mindfulness_played(exercise_id):
    """Record that an exercise was started (logged-in users only; guests are not tracked)."""
    if exercise_id not in {e["id"] for e in load_exercises()}:
        abort(404)
    if current_user.is_authenticated:
        db.session.add(ToolUsage(user_id=current_user.id, tool="mindfulness", detail=exercise_id))
        db.session.commit()
    return jsonify({"ok": True})

