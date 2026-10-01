"""Evaluation pages: manual labeling, J1 (Macro-F1), J2 (feedback), J3 (usage & outcomes)."""
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from ChatbotWebsite import db
from ChatbotWebsite.evaluation import metrics
from ChatbotWebsite.models import AssessmentResult, ChatMessage, ChatSession, SentimentLabel, SessionFeedback
from tests.test_chat_sessions import login_user_


def add_messages(user, texts):
    s = ChatSession(user_id=user.id, title="t")
    db.session.add(s)
    db.session.flush()
    msgs = [ChatMessage(user_id=user.id, session_id=s.id, role="user", message=t) for t in texts]
    db.session.add_all(msgs)
    db.session.commit()
    return msgs


# ---------------- unit: metrics
def test_j1_macro_f1_and_confusion():
    gold = ["negative", "negative", "neutral", "positive"]
    pred = {"A": ["negative", "neutral", "neutral", "positive"], "B": gold}
    r = metrics.j1(gold, pred)
    assert r["macro_f1"]["B"] == 1.0
    assert r["macro_f1"]["A"] == pytest.approx((2 / 3 + 2 / 3 + 1) / 3, abs=0.001)
    assert r["confusion"]["A"] == [[1, 1, 0], [0, 1, 0], [0, 0, 1]]
    assert metrics.j1([], {}) is None


def test_j2_summary():
    fb = [SimpleNamespace(rating=r, helpful=h) for r, h in [(4, True), (5, True), (2, False), (3, False)]]
    s = metrics.j2(fb)
    assert (s["total"], s["average"], s["helpful_yes"], s["helpful_rate"]) == (4, 3.5, 2, 50.0)
    assert list(s["distribution"].values()) == [0, 1, 1, 1, 1]


def test_sentiment_trend_recent_minus_previous():
    now = datetime(2026, 2, 15)
    pts = [(now - timedelta(days=2), 0.4), (now - timedelta(days=3), 0.2), (now - timedelta(days=10), -0.2)]
    trend, recent, prev = metrics.sentiment_trend(pts, now)
    assert (trend, recent, prev) == (0.5, 0.3, -0.2)
    assert metrics.sentiment_trend(pts[:2], now)[0] is None


def test_assessment_change_latest_minus_earliest():
    t0 = datetime(2026, 1, 1)
    rs = [SimpleNamespace(test="phq9", score=s, created_at=t0 + timedelta(days=i)) for i, s in enumerate([14, 11, 8])]
    assert metrics.assessment_change(rs)["phq9"] == {"first": 14, "latest": 8, "change": -6, "count": 3}


def test_pearson():
    assert metrics.pearson([1, 2, 3, 4], [2, 4, 6, 8]) == 1.0
    assert metrics.pearson([1, 2, 3], [1, 2, 3]) is None   # too few weeks
    assert metrics.pearson([1, 1, 1, 1], [1, 2, 3, 4]) is None


# ---------------- manual labeling
def test_label_own_messages(client):
    user = login_user_(client)
    (m,) = add_messages(user, ["I feel awful"])
    assert b"I feel awful" in client.get("/evaluation/labeling").data
    r = client.post("/evaluation/labeling/label", json={"message_id": m.id, "label": "negative"})
    assert r.get_json()["labelled"] == 1
    client.post("/evaluation/labeling/label", json={"message_id": m.id, "label": "neutral"})  # relabel
    assert SentimentLabel.query.one().label == "neutral"
    client.post("/evaluation/labeling/label", json={"message_id": m.id, "label": "clear"})
    assert SentimentLabel.query.count() == 0
    assert client.post("/evaluation/labeling/label", json={"message_id": m.id, "label": "angry"}).status_code == 400


def test_cannot_label_others_messages(client):
    owner = login_user_(client)
    (m,) = add_messages(owner, ["private"])
    client.get("/logout")
    login_user_(client, "other", "other@example.com")
    assert client.post("/evaluation/labeling/label", json={"message_id": m.id, "label": "neutral"}).status_code == 404
    assert b"private" not in client.get("/evaluation/labeling").data


def test_only_unlabeled_filter(client):
    user = login_user_(client)
    a, b = add_messages(user, ["first message", "second message"])
    client.post("/evaluation/labeling/label", json={"message_id": a.id, "label": "neutral"})
    page = client.get("/evaluation/labeling?unlabeled=1").data
    assert b"second message" in page and b"first message" not in page


# ---------------- J1
def test_j1_needs_minimum_labels(client):
    login_user_(client)
    assert b"needs at least 10" in client.get("/evaluation/j1").data


def test_j1_computed_from_human_labels(client):
    user = login_user_(client)
    data = [("I am so happy today", "positive"), ("this is great news", "positive"),
            ("I feel hopeless", "negative"), ("I hate everything", "negative"), ("I am sad and alone", "negative"),
            ("I went to college", "neutral"), ("the bus was late", "neutral"), ("it is raining", "neutral"),
            ("sad but hopeful", "neutral"), ("I feel calm and grateful", "positive")]
    msgs = add_messages(user, [t for t, _ in data])
    for m, (_, label) in zip(msgs, data):
        db.session.add(SentimentLabel(message_id=m.id, user_id=user.id, label=label))
    db.session.commit()
    page = client.get("/evaluation/j1").data
    assert b"Macro-F1 (VADER)" in page and b"Macro-F1 (Hybrid)" in page
    assert b"Confusion Matrix (Hybrid)" in page
    assert b"10 human-labelled chat messages" in page


# ---------------- J2
def test_session_feedback_and_j2_page(client):
    login_user_(client)
    sid = client.post("/chat/send", json={"message": "hi"}).get_json()["session_id"]
    assert client.post(f"/chat/sessions/{sid}/feedback", json={"rating": 4, "helpful": True}).status_code == 200
    client.post(f"/chat/sessions/{sid}/feedback", json={"rating": 5, "helpful": True})  # updates, no duplicate
    assert SessionFeedback.query.count() == 1 and SessionFeedback.query.one().rating == 5
    assert client.post(f"/chat/sessions/{sid}/feedback", json={"rating": 9, "helpful": True}).status_code == 400
    page = client.get("/evaluation/j2").data
    assert b"Total Responses: 1" in page and b"100.0%" in page


def test_feedback_kept_after_session_deleted(client):
    login_user_(client)
    sid = client.post("/chat/send", json={"message": "hi"}).get_json()["session_id"]
    client.post(f"/chat/sessions/{sid}/feedback", json={"rating": 3, "helpful": False})
    client.post(f"/chat/sessions/{sid}/delete")
    fb = SessionFeedback.query.one()
    assert fb.session_id is None and fb.session_title == "hi"
    assert b"(deleted)" in client.get("/evaluation/j2").data


# ---------------- J3
def test_j3_page_shows_real_counts(client):
    user = login_user_(client)
    client.post("/chat/send", json={"message": "I feel stressed about exams"})
    for score in (14, 9):
        db.session.add(AssessmentResult(user_id=user.id, test="phq9", score=score, band="x"))
    db.session.commit()
    page = client.get("/evaluation/j3").data
    assert b"Sessions Used" in page
    assert b"-5" in page and b"PHQ-9 (14 \xe2\x86\x92 9" in page


@pytest.mark.parametrize("url", ["/evaluation/labeling", "/evaluation/j1", "/evaluation/j2", "/evaluation/j3"])
def test_evaluation_requires_login(client, url):
    assert client.get(url).status_code == 302
