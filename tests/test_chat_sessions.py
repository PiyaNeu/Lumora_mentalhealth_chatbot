"""Chat sessions / "Your Chats" — mirrors report Table 4.4.3 (TC-C1 … TC-C3) plus guest mode."""
from markupsafe import escape

from ChatbotWebsite import bcrypt, db
from ChatbotWebsite.models import ChatMessage, ChatSession, SavedInsight, User


def login_user_(client, username="piya", email="piya@example.com"):
    user = User(username=username, email=email, is_verified=True,
                password=bcrypt.generate_password_hash("Str0ng!Pass").decode())
    db.session.add(user)
    db.session.commit()
    client.post("/login", data={"email": email, "password": "Str0ng!Pass"})
    return user


def send(client, text, session_id=None):
    return client.post("/chat/send", json={"message": text, "session_id": session_id})


# TC-C1: a new session is created; after refresh /chat starts a fresh one
def test_new_session_created_and_refresh_starts_new_chat(client):
    login_user_(client)
    first = send(client, "Hi").get_json()
    assert first["session_id"]
    assert ChatSession.query.count() == 1
    # Refresh (open /chat without ?s=) and send again -> second session
    assert client.get("/chat").status_code == 200
    second = send(client, "Hello again").get_json()
    assert second["session_id"] != first["session_id"]
    assert ChatSession.query.count() == 2


def test_messages_in_same_session_stay_together(client):
    login_user_(client)
    sid = send(client, "Hi").get_json()["session_id"]
    send(client, "I feel stressed about exams", sid)
    s = db.session.get(ChatSession, sid)
    assert [m.role for m in s.messages] == ["user", "bot", "user", "bot"]
    assert s.title == "Hi"


# TC-C2: switching sessions loads the correct messages
def test_switching_sessions_loads_correct_messages(client):
    login_user_(client)
    a = send(client, "message about sleep").get_json()["session_id"]
    b = send(client, "message about exams").get_json()["session_id"]
    page_a = client.get(f"/chat?s={a}").data
    page_b = client.get(f"/chat?s={b}").data
    # Titles of all sessions appear in the sidebar; check the message bubbles
    bubble = b'<div class="chat-text">%s</div>'
    assert bubble % b"message about sleep" in page_a and bubble % b"message about exams" not in page_a
    assert bubble % b"message about exams" in page_b and bubble % b"message about sleep" not in page_b


def test_cannot_open_or_post_to_another_users_session(client):
    login_user_(client)
    sid = send(client, "private thing").get_json()["session_id"]
    client.get("/logout")
    login_user_(client, "other", "other@example.com")
    assert client.get(f"/chat?s={sid}").status_code == 404
    assert send(client, "hi", sid).status_code == 404
    assert client.post(f"/chat/sessions/{sid}/delete").status_code == 404


# TC-C3: delete a session removes it and its messages
def test_delete_session_removes_session_and_messages(client):
    login_user_(client)
    sid = send(client, "Hi").get_json()["session_id"]
    send(client, "another", sid)
    assert ChatMessage.query.count() == 4
    resp = client.post(f"/chat/sessions/{sid}/delete", headers={"Accept": "application/json"})
    assert resp.get_json() == {"ok": True}
    assert ChatSession.query.count() == 0
    assert ChatMessage.query.count() == 0


def test_guest_chat_is_not_persisted(client):
    client.get("/guest")
    data = send(client, "Hi").get_json()
    assert data["reply"]
    assert "session_id" not in data
    assert ChatSession.query.count() == 0 and ChatMessage.query.count() == 0


def test_guest_page_explains_chats_are_not_saved(client):
    assert b"Chats are saved only for logged-in users" in client.get("/chat").data


def test_save_insight_on_bot_message(client):
    login_user_(client)
    data = send(client, "Hi").get_json()
    assert client.post("/chat/insights", json={"message_id": data["message_id"]}).status_code == 200
    # Saving twice does not duplicate
    client.post("/chat/insights", json={"message_id": data["message_id"]})
    assert SavedInsight.query.count() == 1
    page = client.get("/chat/insights").data.decode()
    assert str(escape(data["reply"].split("\n")[0])) in page


def test_cannot_save_user_message_as_insight(client):
    login_user_(client)
    data = send(client, "Hi").get_json()
    assert client.post("/chat/insights", json={"message_id": data["user_message_id"]}).status_code == 404


def test_insight_survives_session_deletion(client):
    login_user_(client)
    data = send(client, "Hi").get_json()
    client.post("/chat/insights", json={"message_id": data["message_id"]})
    client.post(f"/chat/sessions/{data['session_id']}/delete")
    assert SavedInsight.query.count() == 1


def test_preferred_mode_saved_to_profile(client):
    user = login_user_(client)
    assert client.post("/chat/mode", json={"mode": "coach"}).status_code == 200
    db.session.refresh(user)
    assert user.preferred_mode == "coach"
    assert client.post("/chat/mode", json={"mode": "nonsense"}).status_code == 400
