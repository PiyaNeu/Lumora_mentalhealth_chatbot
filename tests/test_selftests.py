"""Self-assessment tests — mirrors report Table 4.4.9 (TC-I1, TC-I2) plus bands and burnout."""
from datetime import datetime, timedelta

import pytest

from ChatbotWebsite import db
from ChatbotWebsite.models import AssessmentResult, ChatMessage, Journal, MoodEntry
from ChatbotWebsite.selfhelp import burnout
from ChatbotWebsite.selfhelp.assessments import ASSESSMENTS, IncompleteAnswers, score
from tests.test_chat_sessions import login_user_


def form(answers):
    return {f"q{i}": str(a) for i, a in enumerate(answers) if a is not None}


def test_standard_item_counts():
    assert len(ASSESSMENTS["phq9"]["questions"]) == 9
    assert len(ASSESSMENTS["gad7"]["questions"]) == 7


# TC-I1: score calculated correctly
def test_phq9_score_and_result_page(client):
    answers = [1, 2, 0, 3, 1, 0, 2, 1, 0]  # 10 -> Moderate
    resp = client.post("/selfhelp/tests/phq9", data=form(answers))
    assert resp.status_code == 200
    assert b"10 <span" in resp.data and b"Moderate" in resp.data
    assert b"not a diagnosis" in resp.data


@pytest.mark.parametrize("total,band", [(0, "Minimal"), (4, "Minimal"), (5, "Mild"), (9, "Mild"), (10, "Moderate"),
                                        (14, "Moderate"), (15, "Moderately severe"), (19, "Moderately severe"),
                                        (20, "Severe"), (27, "Severe")])
def test_phq9_bands(total, band):
    answers = [3] * (total // 3) + ([total % 3] if total % 3 else [])
    answers += [0] * (9 - len(answers))
    assert sum(answers) == total
    assert score("phq9", answers)["band"] == band


@pytest.mark.parametrize("total,band", [(4, "Minimal"), (5, "Mild"), (10, "Moderate"), (15, "Severe"), (21, "Severe")])
def test_gad7_bands(total, band):
    answers = [3] * (total // 3) + ([total % 3] if total % 3 else [])
    answers += [0] * (7 - len(answers))
    assert score("gad7", answers)["band"] == band


def test_phq9_item9_shows_safety_message_regardless_of_score(client):
    answers = [0, 0, 0, 0, 0, 0, 0, 0, 1]  # total 1 = Minimal, but item 9 endorsed
    resp = client.post("/selfhelp/tests/phq9", data=form(answers))
    assert b"Minimal" in resp.data
    assert b"Open SOS helplines" in resp.data


# TC-I2: incomplete submission is blocked with a warning
def test_incomplete_submission_blocked(client):
    resp = client.post("/selfhelp/tests/gad7", data=form([1, 1, 1, None, 1, 1, 1]))
    assert resp.status_code == 400
    assert b"Please answer every question" in resp.data
    assert b"your result" not in resp.data


@pytest.mark.parametrize("answers", [[], [1] * 6, [1, 1, 1, 1, 1, 1, 9]])
def test_score_rejects_incomplete_or_invalid(answers):
    with pytest.raises(IncompleteAnswers):
        score("gad7", answers)


def test_results_saved_only_for_logged_in_users(client):
    client.post("/selfhelp/tests/gad7", data=form([1] * 7))
    assert AssessmentResult.query.count() == 0
    login_user_(client)
    client.post("/selfhelp/tests/gad7", data=form([1] * 7))
    r = AssessmentResult.query.one()
    assert (r.test, r.score, r.band) == ("gad7", 7, "Mild")
    assert b"GAD-7" in client.get("/selfhelp/tests").data


def test_unknown_test_404(client):
    assert client.get("/selfhelp/tests/nope").status_code == 404


def test_burnout_questionnaire_bands():
    assert score("burnout", [0] * 6)["band"] == "Low"
    assert score("burnout", [2] * 6)["band"] == "Moderate"
    assert score("burnout", [4] * 6)["band"] == "High"


# Signals-based burnout check
def sig(kind, low):
    return {"kind": kind, "value": "x", "low": low, "when": datetime.utcnow()}


def test_burnout_not_enough_data():
    assert burnout.evaluate([sig("mood", True)])["level"] == "Not enough data"


def test_burnout_one_bad_signal_is_normal():
    signals = [sig("mood", False)] * 4 + [sig("chat_sentiment", True)]
    assert burnout.evaluate(signals)["level"] == "Normal"


def test_burnout_high_needs_repeated_lows_across_sources():
    signals = [sig("mood", True)] * 3 + [sig("chat_sentiment", True)] * 3 + [sig("mood", False)]
    assert burnout.evaluate(signals)["level"] == "High"
    only_one_source = [sig("chat_sentiment", True)] * 6 + [sig("mood", False)]
    assert burnout.evaluate(only_one_source)["level"] == "Elevated"


def test_questionnaire_raises_but_never_lowers_level():
    normal = [sig("mood", False)] * 5
    assert burnout.evaluate(normal, "High")["level"] == "High"
    high = [sig("mood", True)] * 3 + [sig("journal_mood", True)] * 3
    assert burnout.evaluate(high, "Low")["level"] == "High"


def test_burnout_page_combines_mood_journal_and_chat(client):
    user = login_user_(client)
    now = datetime.utcnow()
    for i in range(3):
        db.session.add(MoodEntry(user_id=user.id, mood=1, source="Manual", day=(now - timedelta(days=i)).date(),
                                 created_at=now - timedelta(days=i), updated_at=now - timedelta(days=i)))
    db.session.add(Journal(user_id=user.id, title="t", content="c", mood_tag="Sad", mood=2))
    db.session.add(ChatMessage(user_id=user.id, message="m", role="user", sentiment_label="negative"))
    db.session.add(ChatMessage(user_id=user.id, message="m", role="user", sentiment_label="negative"))
    db.session.commit()
    page = client.get("/selfhelp/burnout").data
    assert b"Level: High" in page
    assert b"journal_mood" in page and b"chat_sentiment" in page and b"LOW" in page


def test_burnout_requires_login(client):
    assert client.get("/selfhelp/burnout").status_code == 302
