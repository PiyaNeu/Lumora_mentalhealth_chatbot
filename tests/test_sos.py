"""SOS page — mirrors report Table 4.4.10 (TC-K1, TC-K2)."""
from ChatbotWebsite import sos_config
from tests.test_chat_sessions import login_user_


# TC-K1: hotline info displayed
def test_sos_lists_nepal_hotlines(client):
    page = client.get("/sos").data
    assert b"SOS Hotlines in Nepal" in page
    for h in sos_config.HOTLINES:
        assert h["name"].encode() in page


# TC-K2: guests can open the SOS page
def test_sos_accessible_as_guest(client):
    assert client.get("/sos").status_code == 200
    client.get("/guest")
    assert client.get("/sos").status_code == 200


def test_sos_accessible_when_logged_in(client):
    login_user_(client)
    assert client.get("/sos").status_code == 200


def test_placeholder_numbers_never_shown_as_real(client):
    page = client.get("/sos").data
    assert b"TODO" not in page and b'href="tel:TODO"' not in page
    assert b"pending verification" in page


def test_verified_number_is_shown(client, monkeypatch):
    entry = {"name": "Test Line", "phone": "1234", "website": "", "hours": "", "verified": True}
    monkeypatch.setattr(sos_config, "HOTLINES", [entry])
    monkeypatch.setattr("ChatbotWebsite.main.routes.HOTLINES", [entry])
    page = client.get("/sos").data
    assert b'href="tel:1234"' in page


def test_sos_linked_from_every_page_navbar(client):
    assert b'href="/sos"' in client.get("/chat").data


def test_sos_lang_param_switches_language(client):
    assert "नेपालका SOS हेल्पलाइनहरू" in client.get("/sos?lang=ne").data.decode()
    assert "SOS Hotlines in Nepal" in client.get("/sos?lang=en").data.decode()
    client.get("/sos?lang=xx")  # ignored
    assert "SOS Hotlines in Nepal" in client.get("/sos").data.decode()


def test_chat_reply_marks_sos_and_language_for_redirect(client):
    data = client.post("/chat/send", json={"message": "malai bachna mann chhaina"}).get_json()
    assert data["sos"] is True and data["language"] == "ne-rom"
