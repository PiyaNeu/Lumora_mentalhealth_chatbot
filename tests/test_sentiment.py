"""Sentiment — mirrors report Tables 4.4.2 (TC-B1…B5) and 4.4.5 (TC-E1…E4)."""
import pytest

from ChatbotWebsite.models import ChatMessage
from ChatbotWebsite.sentiment import analyze, hybrid, ml_available, ml_predict
from tests.test_chat_sessions import login_user_


# Table 4.4.2 — VADER
def test_tc_b1_positive():
    assert analyze("I'm happy today").label == "positive"


def test_tc_b2_negative():
    assert analyze("I feel hopeless").label == "negative"


def test_tc_b3_neutral():
    assert analyze("It is raining").label == "neutral"


def test_tc_b4_mixed_emotions_score_in_range():
    s = analyze("I'm sad but hopeful")
    assert -1.0 <= s.compound <= 1.0
    assert abs(s.pos + s.neu + s.neg - 1.0) < 0.01


@pytest.mark.parametrize("text", ["", "   ", None])
def test_tc_b5_empty_message_no_crash(text):
    s = analyze(text)
    assert s.label == "neutral" and s.compound == 0.0
    assert hybrid(text).label == "neutral"


# Table 4.4.5 — label + score
def test_tc_e1_positive_score_above_zero():
    s = analyze("I feel happy today")
    assert s.label == "positive" and s.compound > 0


def test_tc_e2_negative_score_below_zero():
    s = analyze("I feel hopeless")
    assert s.label == "negative" and s.compound < 0


def test_tc_e3_neutral():
    assert analyze("I went to college").label == "neutral"


def test_tc_e4_mixed_is_neutral_or_negative_with_hybrid():
    # VADER alone scores this positive (the clause after "but" is boosted);
    # the hybrid's mixed-feelings rule brings it to neutral/negative as the report expects.
    assert analyze("Sad but hopeful").label == "positive"
    assert hybrid("Sad but hopeful").label in ("neutral", "negative")


# Hybrid rules
def test_hybrid_risk_screen_forces_negative():
    h = hybrid("I am fine", risk_level="high")
    assert h.label == "negative" and h.rule == "risk_screen"


def test_hybrid_negated_positive():
    assert hybrid("I'm not okay at all").label == "negative"


def test_hybrid_domain_lexicon_catches_what_vader_misses():
    text = "I am so overwhelmed and burnt out"
    assert hybrid(text).label == "negative"


def test_hybrid_without_ml_model_falls_back(tmp_path):
    h = hybrid("I feel great today", model_dir=str(tmp_path))
    assert h.label == "positive" and h.ml_label is None


@pytest.mark.skipif(not ml_available(), reason="run train_sentiment.py first")
def test_ml_classifier_predicts_a_label():
    assert ml_predict("I feel really sad and alone") in ("negative", "neutral", "positive")


# Storage per message (logged-in only)
def test_sentiment_stored_for_logged_in_user_messages(client):
    login_user_(client)
    client.post("/chat/send", json={"message": "I feel hopeless about everything"})
    user_msg = ChatMessage.query.filter_by(role="user").one()
    assert user_msg.sentiment_label == "negative"
    assert user_msg.sentiment_compound < 0 and user_msg.sentiment_score < 0
    bot_msg = ChatMessage.query.filter_by(role="bot").one()
    assert bot_msg.sentiment_label is None


def test_sentiment_uses_translation_for_nepali(client):
    login_user_(client)
    client.post("/chat/send", json={"message": "malai dherai dukha lagyo"})
    assert ChatMessage.query.filter_by(role="user").one().sentiment_label == "negative"


def test_no_sentiment_stored_for_guests(client):
    client.get("/guest")
    client.post("/chat/send", json={"message": "I feel happy"})
    assert ChatMessage.query.count() == 0
