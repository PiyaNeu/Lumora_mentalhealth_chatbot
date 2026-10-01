"""Mood tracker & PDF export — mirrors report Tables 4.4.6 (TC-F1…F3) and 4.4.7 (TC-G1, TC-G2)."""
from datetime import date, datetime, timedelta

import pytest

from ChatbotWebsite import db
from ChatbotWebsite.models import MoodEntry
from ChatbotWebsite.mood import analytics
from tests.test_chat_sessions import login_user_


def checkin(client, mood, note=""):
    return client.post("/mood/checkin", data={"mood": mood, "note": note}, follow_redirects=True)


# TC-F1: add mood record
def test_add_mood_record(client):
    login_user_(client)
    resp = checkin(client, 4, "good day")
    assert b"Mood saved" in resp.data
    entry = MoodEntry.query.one()
    assert (entry.mood, entry.source, entry.note) == (4, "Manual", "good day")


# TC-F2: second check-in the same day updates instead of duplicating
def test_same_day_checkin_updates_existing_entry(client):
    login_user_(client)
    checkin(client, 2)
    resp = checkin(client, 5)
    assert b"already checked in today" in resp.data
    assert MoodEntry.query.filter_by(source="Manual").count() == 1
    assert MoodEntry.query.one().mood == 5


@pytest.mark.parametrize("bad", ["0", "6", "abc", ""])
def test_invalid_mood_rejected(client, bad):
    login_user_(client)
    assert b"choose a mood" in checkin(client, bad).data
    assert MoodEntry.query.count() == 0


# TC-F3: graph renders with multiple moods
def test_dashboard_and_chart_data_with_multiple_moods(client):
    user = login_user_(client)
    for i, m in enumerate([2, 3, 4]):
        db.session.add(MoodEntry(user_id=user.id, mood=m, source="Manual",
                                 day=date.today() - timedelta(days=i),
                                 updated_at=datetime.utcnow() - timedelta(days=i)))
    db.session.commit()
    page = client.get("/mood/")
    assert page.status_code == 200 and b"moodChart" in page.data
    for period in ("daily", "weekly", "monthly"):
        data = client.get(f"/mood/data?period={period}").get_json()
        assert data["period"] == period
        assert len(data["mood"]["values"]) >= 1
    assert len(client.get("/mood/data?period=daily").get_json()["mood"]["values"]) == 3


def test_mood_pages_require_login(client):
    assert client.get("/mood/").status_code == 302
    assert client.get("/mood/export.pdf").status_code == 302


# TC-G1: export PDF with data
def test_export_pdf_generated(client):
    login_user_(client)
    checkin(client, 3)
    resp = client.get("/mood/export.pdf")
    assert resp.status_code == 200
    assert resp.headers["Content-Type"] == "application/pdf"
    assert resp.data.startswith(b"%PDF")
    assert "Mood_Report" in resp.headers["Content-Disposition"]


# TC-G2: export with no data shows an error
def test_export_pdf_without_data_shows_message(client):
    login_user_(client)
    resp = client.get("/mood/export.pdf", follow_redirects=True)
    assert b"No mood data to export" in resp.data


# Chat-derived moods (report PDF shows Source = Chat entries)
def test_chat_messages_create_chat_mood_entries(client):
    login_user_(client)
    client.post("/chat/send", json={"message": "I feel so sad and tired today"})
    client.post("/chat/send", json={"message": "hi"})  # greeting guard: no mood entry
    entries = MoodEntry.query.filter_by(source="Chat").all()
    assert len(entries) == 1 and entries[0].mood <= 2
    assert entries[0].message_id is not None


# Analytics
@pytest.mark.parametrize("score,mood", [(-0.9, 1), (-0.3, 2), (0.0, 3), (0.4, 4), (0.8, 5), (None, None)])
def test_mood_from_sentiment(score, mood):
    assert analytics.mood_from_sentiment(score) == mood


def pts(*day_values, start=date(2026, 2, 1)):
    return [(datetime.combine(start + timedelta(days=d), datetime.min.time()), v) for d, v in day_values]


def test_aggregate_daily_weekly_monthly():
    points = pts((0, 2), (0, 4), (1, 5), (31, 1))
    assert list(analytics.aggregate(points, "daily").values()) == [3.0, 5.0, 1.0]
    # 1 Feb 2026 is a Sunday, so it belongs to the week starting Monday 26 Jan
    assert list(analytics.aggregate(points, "weekly")) == ["Week of 26 Jan", "Week of 02 Feb", "Week of 02 Mar"]
    assert list(analytics.aggregate(points, "monthly").values()) == [3.67, 1.0]


def test_positive_streak():
    today = date(2026, 2, 10)
    points = pts((7, 4), (8, 5), (9, 4), start=date(2026, 2, 1))  # Feb 8, 9, 10
    assert analytics.positive_streak(points, today) == 3
    assert analytics.positive_streak(pts((9, 2)), date(2026, 2, 10)) == 0


def test_trend_and_insight():
    today = date(2026, 2, 14)
    falling = pts(*[(d, 4) for d in range(0, 7)], *[(d, 2.5) for d in range(7, 14)])
    assert analytics.trend(falling, today)[0] == "down"
    assert "Downward trend" in analytics.insight(falling, today)["insight"]
    assert analytics.insight([], today)["insight"].startswith("Not enough data")


def test_low_run_insight_mentions_sos():
    today = date(2026, 2, 3)
    low = pts((0, 1), (1, 2), (2, 1))
    assert "SOS" in analytics.insight(low, today)["suggestion"]
