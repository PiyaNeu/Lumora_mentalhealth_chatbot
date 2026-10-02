"""Account settings and Privacy & Data Controls."""
import io
from datetime import date, datetime, timedelta

from PIL import Image

from ChatbotWebsite import db
from ChatbotWebsite.models import (ChatMessage, ChatSession, CrisisEvent, Journal, MoodEntry, SavedInsight,
                                   SentimentLabel, SessionFeedback, User)
from tests.test_chat_sessions import login_user_


def chat(client, text, sid=None):
    return client.post("/chat/send", json={"message": text, "session_id": sid}).get_json()


def age_messages(user_id, days):
    old = datetime.utcnow() - timedelta(days=days)
    for m in ChatMessage.query.filter_by(user_id=user_id):
        m.timestamp = old
    for c in CrisisEvent.query.filter_by(user_id=user_id):
        c.created_at = old
    db.session.commit()


# Account
def test_update_username_and_preferred_mode(client):
    user = login_user_(client)
    resp = client.post("/account/", data={"username": "newname", "preferred_mode": "therapist"},
                       follow_redirects=True)
    assert b"has been updated" in resp.data
    db.session.refresh(user)
    assert (user.username, user.preferred_mode) == ("newname", "therapist")


def test_profile_picture_upload_resized(client, app):
    user = login_user_(client)
    buf = io.BytesIO()
    Image.new("RGB", (800, 600), "purple").save(buf, "PNG")
    buf.seek(0)
    client.post("/account/", data={"username": user.username, "preferred_mode": "auto",
                                   "picture": (buf, "me.png")}, content_type="multipart/form-data")
    db.session.refresh(user)
    assert user.profile_image != "default.jpg"
    import os
    path = os.path.join(app.static_folder, "profile_images", user.profile_image)
    with Image.open(path) as img:
        assert max(img.size) <= 250
    os.remove(path)


def test_non_image_upload_rejected(client):
    user = login_user_(client)
    resp = client.post("/account/", data={"username": user.username, "preferred_mode": "auto",
                                          "picture": (io.BytesIO(b"not an image"), "evil.exe")},
                       content_type="multipart/form-data")
    assert b"Images only" in resp.data


# Privacy: delete by time window
def test_delete_old_messages_keeps_recent(client):
    user = login_user_(client)
    old_sid = chat(client, "old message about sleep")["session_id"]
    age_messages(user.id, 40)
    new_sid = chat(client, "new message about exams")["session_id"]
    resp = client.post("/account/privacy/delete-messages", data={"window": "1m"}, follow_redirects=True)
    assert b"Deleted 2 chat messages" in resp.data
    assert db.session.get(ChatSession, old_sid) is None          # emptied session removed
    assert db.session.get(ChatSession, new_sid) is not None
    assert ChatMessage.query.count() == 2


def test_delete_old_messages_cleans_linked_rows(client):
    user = login_user_(client)
    data = chat(client, "I want to end my life")       # creates a CrisisEvent
    client.post("/chat/insights", json={"message_id": data["message_id"]})
    db.session.add(SentimentLabel(message_id=data["user_message_id"], user_id=user.id, label="negative"))
    db.session.commit()
    age_messages(user.id, 400)
    client.post("/account/privacy/delete-messages", data={"window": "6m"})
    assert ChatMessage.query.count() == 0 and CrisisEvent.query.count() == 0
    assert SentimentLabel.query.count() == 0
    assert SavedInsight.query.one().message_id is None   # the saved text stays with the user


def test_delete_old_moods_and_journals(client):
    user = login_user_(client)
    old = datetime.utcnow() - timedelta(days=100)
    db.session.add_all([
        MoodEntry(user_id=user.id, mood=2, source="Manual", day=date.today() - timedelta(days=100), created_at=old),
        MoodEntry(user_id=user.id, mood=4, source="Manual", day=date.today()),
        Journal(user_id=user.id, title="old", content="old", date_created=old),
        Journal(user_id=user.id, title="new", content="new"),
    ])
    db.session.commit()
    client.post("/account/privacy/delete-moods", data={"window": "3m"})
    client.post("/account/privacy/delete-journals", data={"window": "3m"})
    assert [m.mood for m in MoodEntry.query.all()] == [4]
    assert [j.title for j in Journal.query.all()] == ["new"]


def test_delete_everything_window(client):
    login_user_(client)
    client.post("/mood/checkin", data={"mood": 3})
    client.post("/account/privacy/delete-moods", data={"window": "all"})
    assert MoodEntry.query.count() == 0


def test_invalid_window_rejected(client):
    login_user_(client)
    assert client.post("/account/privacy/delete-moods", data={"window": "forever"}).status_code == 400


def test_privacy_actions_only_touch_own_data(client):
    login_user_(client, "a", "a@example.com")
    chat(client, "my data")
    client.get("/logout")
    login_user_(client, "b", "b@example.com")
    client.post("/account/privacy/delete-messages", data={"window": "all"})
    client.post("/account/privacy/delete-all-conversations", data={"confirm": "DELETE"})
    assert ChatMessage.query.count() == 2


# Conversations
def test_delete_one_conversation(client):
    login_user_(client)
    keep = chat(client, "keep me")["session_id"]
    drop = chat(client, "drop me")["session_id"]
    client.post(f"/chat/sessions/{keep}/feedback", json={"rating": 4, "helpful": True})
    client.post("/account/privacy/delete-conversation", data={"session_id": drop})
    assert [s.id for s in ChatSession.query.all()] == [keep]


def test_delete_all_conversations_needs_confirmation(client):
    login_user_(client)
    sid = chat(client, "hello there")["session_id"]
    client.post(f"/chat/sessions/{sid}/feedback", json={"rating": 4, "helpful": True})
    resp = client.post("/account/privacy/delete-all-conversations", data={"confirm": "yes"}, follow_redirects=True)
    assert b"Type DELETE" in resp.data and ChatSession.query.count() == 1
    client.post("/account/privacy/delete-all-conversations", data={"confirm": "DELETE"})
    assert ChatSession.query.count() == 0 and ChatMessage.query.count() == 0
    assert SessionFeedback.query.one().session_id is None


# Export
def test_export_my_data_pdf(client):
    login_user_(client)
    chat(client, "I feel stressed")
    client.post("/mood/checkin", data={"mood": 3})
    resp = client.get("/account/privacy/export.pdf")
    assert resp.status_code == 200 and resp.data.startswith(b"%PDF")
    assert resp.headers["Cache-Control"] == "no-store"
    assert "Lumora_My_Data" in resp.headers["Content-Disposition"]


def test_export_handles_markup_in_user_text(client):
    login_user_(client)
    chat(client, "<b>bold</b> & <script>alert(1)</script>")
    assert client.get("/account/privacy/export.pdf").status_code == 200


# Delete account
def test_delete_account_requires_password_and_removes_everything(client):
    login_user_(client)
    chat(client, "I feel stressed")
    client.post("/mood/checkin", data={"mood": 3})
    client.post("/journal/new", data={"mood_tag": "Calm", "content": "note"})
    resp = client.post("/account/delete", data={"password": "wrong"}, follow_redirects=True)
    assert b"Password incorrect" in resp.data and User.query.count() == 1
    resp = client.post("/account/delete", data={"password": "Str0ng!Pass"}, follow_redirects=True)
    assert b"have been deleted" in resp.data
    assert User.query.count() == 0
    for model in (ChatMessage, ChatSession, MoodEntry, Journal):
        assert model.query.count() == 0


def test_privacy_requires_login(client):
    assert client.get("/account/privacy").status_code == 302
    assert client.get("/account/privacy/export.pdf").status_code == 302
