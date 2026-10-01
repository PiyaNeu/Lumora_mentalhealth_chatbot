"""Authentication module — mirrors report Table 4.4.1 (TC-A1 … TC-A5)."""
import re

from ChatbotWebsite import mail
from ChatbotWebsite.models import User

PASSWORD = "Str0ng!Pass"


def register(client, username="piya", email="piya@example.com", password=PASSWORD):
    return client.post("/register", data={
        "username": username, "email": email,
        "password": password, "confirm_password": password,
    }, follow_redirects=True)


def login(client, email="piya@example.com", password=PASSWORD):
    return client.post("/login", data={"email": email, "password": password}, follow_redirects=True)


def make_verified_user(client, **kw):
    register(client, **kw)
    user = User.query.filter_by(email=kw.get("email", "piya@example.com")).first()
    user.is_verified = True
    from ChatbotWebsite import db
    db.session.commit()
    return user


def is_logged_in(client):
    with client.session_transaction() as sess:
        return "_user_id" in sess


# TC-A1: successful registration
def test_register_creates_account_and_shows_success(client):
    resp = register(client)
    assert resp.status_code == 200
    assert b"Account created" in resp.data
    user = User.query.filter_by(email="piya@example.com").first()
    assert user is not None and not user.is_verified
    assert user.password != PASSWORD  # stored hashed


# TC-A2: duplicate email is rejected
def test_register_duplicate_email_shows_error(client):
    register(client)
    resp = register(client, username="other")
    assert b"Email already exists" in resp.data
    assert User.query.count() == 1


def test_register_rejects_weak_password(client):
    resp = register(client, password="weak")
    assert b"Password needs 8+ characters" in resp.data
    assert User.query.count() == 0


# TC-A3: valid login
def test_login_with_valid_credentials(client):
    make_verified_user(client)
    resp = login(client)
    assert resp.status_code == 200
    assert is_logged_in(client)


# TC-A4: wrong password
def test_login_with_wrong_password_shows_error(client):
    make_verified_user(client)
    resp = login(client, password="Wr0ng!Pass")
    assert b"Login unsuccessful" in resp.data
    assert not is_logged_in(client)


def test_login_blocked_until_email_verified(client):
    register(client)
    resp = login(client)
    assert b"Please verify your email" in resp.data
    assert not is_logged_in(client)


# TC-A5: logout clears session and redirects to login
def test_logout_clears_session_and_redirects_to_login(client):
    make_verified_user(client)
    login(client)
    resp = client.get("/logout")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")
    assert not is_logged_in(client)


def test_email_verification_link_verifies_user(client):
    with mail.record_messages() as outbox:
        register(client)
    assert len(outbox) == 1
    link = re.search(r'href="(http[^"]+/verify/[^"]+)"', outbox[0].html).group(1)
    assert link.startswith("http://localhost/verify/")  # built on PUBLIC_BASE_URL
    resp = client.get(link.replace("http://localhost", ""), follow_redirects=True)
    assert b"has been verified" in resp.data
    assert User.query.first().is_verified
    login(client)
    assert is_logged_in(client)


def test_invalid_verification_token_rejected(client):
    resp = client.get("/verify/not-a-real-token", follow_redirects=True)
    assert b"invalid or has expired" in resp.data


def test_reset_token_cannot_be_used_for_verification(client):
    register(client)
    user = User.query.first()
    assert User.verify_confirmation_token(user.get_reset_token()) is None


def test_password_reset_flow(client):
    make_verified_user(client)
    with mail.record_messages() as outbox:
        client.post("/reset_password", data={"email": "piya@example.com"})
    link = re.search(r'href="http://localhost([^"]+)"', outbox[0].html).group(1)
    new_pw = "N3w!Password"
    client.post(link, data={"password": new_pw, "confirm_password": new_pw})
    login(client, password=new_pw)
    assert is_logged_in(client)


def test_guest_mode_sets_guest_flag_without_login(client):
    resp = client.get("/guest")
    assert resp.status_code == 302 and resp.headers["Location"].endswith("/chat")
    with client.session_transaction() as sess:
        assert sess.get("guest") is True
        assert "_user_id" not in sess


def test_login_ignores_external_next_redirect(client):
    make_verified_user(client)
    resp = client.post("/login?next=https://evil.example.com",
                       data={"email": "piya@example.com", "password": PASSWORD})
    assert resp.headers["Location"] == "/"
