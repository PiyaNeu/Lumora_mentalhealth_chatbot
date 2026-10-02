"""UI: navigation layout and the English / Nepali interface toggle."""
import pytest

from ChatbotWebsite.i18n import STRINGS
from tests.test_chat_sessions import login_user_


def test_default_language_is_english(client):
    page = client.get("/chat").data.decode()
    assert '<html lang="en">' in page and "Your Chats" in page


def test_switch_to_nepali_and_back(client):
    resp = client.get("/lang/ne", headers={"Referer": "http://localhost/sos"})
    assert resp.status_code == 302 and resp.headers["Location"] == "/sos"
    page = client.get("/sos").data.decode()
    assert '<html lang="ne">' in page and "नेपालका SOS हेल्पलाइनहरू" in page
    client.get("/lang/en")
    assert "SOS Hotlines in Nepal" in client.get("/sos").data.decode()


def test_language_toggle_ignores_external_referrer(client):
    resp = client.get("/lang/ne", headers={"Referer": "https://evil.example.com/phish"})
    assert resp.headers["Location"] == "/"


def test_unknown_language_ignored(client):
    client.get("/lang/fr")
    assert '<html lang="en">' in client.get("/").data.decode()


def test_language_kept_after_logout(client):
    login_user_(client)
    client.get("/lang/ne")
    client.get("/logout")
    assert '<html lang="ne">' in client.get("/").data.decode()


def test_every_string_has_both_languages():
    for key, value in STRINGS.items():
        assert value.get("en") and value.get("ne"), key


def test_navbar_groups_match_report(client):
    login_user_(client)
    page = client.get("/chat").data.decode()
    for label in ("More", "Mood", "Evaluation", "Consultation", "SOS"):
        assert label in page


@pytest.mark.parametrize("url", ["/", "/chat", "/sos", "/selfhelp/tests", "/selfhelp/mindfulness", "/community/",
                                 "/login", "/register"])
def test_public_pages_render_in_both_languages(client, url):
    for lang in ("en", "ne"):
        client.get(f"/lang/{lang}")
        assert client.get(url).status_code == 200
