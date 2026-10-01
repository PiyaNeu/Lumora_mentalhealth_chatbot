from datetime import datetime, timedelta

from flask import Blueprint, abort, render_template, request
from flask_login import current_user, login_required

from ChatbotWebsite import db
from ChatbotWebsite.models import AssessmentResult
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
