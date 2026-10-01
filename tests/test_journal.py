"""Journaling — mirrors report Table 4.4.8 (TC-H1 … TC-H3) plus mood tag, pagination and privacy."""
from ChatbotWebsite import db
from ChatbotWebsite.models import Journal
from tests.test_chat_sessions import login_user_


def create(client, content="Today was long but I managed.", mood_tag="Calm", title=""):
    return client.post("/journal/new", data={"mood_tag": mood_tag, "title": title, "content": content},
                       follow_redirects=True)


# TC-H1: save journal entry
def test_save_journal_entry(client):
    login_user_(client)
    resp = create(client, "I felt anxious before class but better after a walk.", "Anxious")
    assert b"has been saved" in resp.data
    j = Journal.query.one()
    assert (j.mood_tag, j.mood, j.title) == ("Anxious", 2, "Feeling Anxious")
    assert j.sentiment_label in ("negative", "neutral", "positive") and j.sentiment_compound is not None


# TC-H2: edit journal entry
def test_edit_journal_entry(client):
    login_user_(client)
    create(client)
    j = Journal.query.one()
    resp = client.post(f"/journal/{j.id}/edit", data={"mood_tag": "Happy", "title": "Good news",
                                                      "content": "I passed my exam!"}, follow_redirects=True)
    assert b"has been updated" in resp.data
    db.session.refresh(j)
    assert (j.mood_tag, j.mood, j.title, j.content) == ("Happy", 5, "Good news", "I passed my exam!")
    assert j.updated_at is not None and j.sentiment_label == "positive"


def test_edit_form_prefilled(client):
    login_user_(client)
    create(client, "prefill me")
    j = Journal.query.one()
    assert b"prefill me" in client.get(f"/journal/{j.id}/edit").data


# TC-H3: delete journal entry
def test_delete_journal_entry(client):
    login_user_(client)
    create(client)
    j = Journal.query.one()
    resp = client.post(f"/journal/{j.id}/delete", follow_redirects=True)
    assert b"has been deleted" in resp.data
    assert Journal.query.count() == 0


def test_empty_content_rejected(client):
    login_user_(client)
    resp = create(client, content="")
    assert b"has been saved" not in resp.data
    assert Journal.query.count() == 0


def test_invalid_mood_tag_rejected(client):
    login_user_(client)
    create(client, mood_tag="Ecstatic")
    assert Journal.query.count() == 0


def test_pagination(client):
    login_user_(client)
    for i in range(8):
        create(client, f"entry number {i}")
    page1 = client.get("/journal/").data
    page2 = client.get("/journal/?page=2").data
    assert b"entry number 7" in page1 and b"entry number 0" not in page1  # newest first
    assert b"entry number 0" in page2 and b"entry number 7" not in page2


def test_journals_are_private(client):
    login_user_(client)
    create(client, "my private thoughts")
    jid = Journal.query.one().id
    client.get("/logout")
    login_user_(client, "other", "other@example.com")
    assert client.get(f"/journal/{jid}").status_code == 404
    assert client.post(f"/journal/{jid}/delete").status_code == 404
    assert b"my private thoughts" not in client.get("/journal/").data


def test_journal_requires_login(client):
    assert client.get("/journal/").status_code == 302


def test_journal_mood_appears_in_mood_dashboard_and_pdf(client):
    login_user_(client)
    create(client, "rough day", "Sad")
    data = client.get("/mood/data").get_json()
    assert data["mood"]["values"] == [2.0]
    pdf = client.get("/mood/export.pdf")
    assert pdf.status_code == 200 and pdf.data.startswith(b"%PDF")


def test_nepali_journal_sentiment_uses_translation(client):
    login_user_(client)
    create(client, "आज मलाई धेरै दुःख लाग्यो", "Sad")
    assert Journal.query.one().sentiment_label == "negative"
