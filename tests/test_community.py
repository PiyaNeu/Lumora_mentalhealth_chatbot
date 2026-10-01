"""Anonymous community: tags, screening, reactions, reports, auto-hide, sorting."""
import pytest

from ChatbotWebsite.community.moderation import random_alias, screen
from ChatbotWebsite.models import CommunityComment, CommunityPost, CommunityReaction, CommunityReport
from tests.test_chat_sessions import login_user_


def post(client, title="I feel so tired", body="I am unable to breathe.", tag="anxiety"):
    return client.post("/community/new", data={"title": title, "body": body, "tag": tag}, follow_redirects=True)


def test_post_is_anonymous(client):
    login_user_(client, "piya", "piya@example.com")
    resp = post(client)
    assert b"Posted anonymously" in resp.data
    p = CommunityPost.query.one()
    assert p.status == "visible" and p.alias.split("#")[1].isdigit()
    page = client.get("/community/").data
    assert b"Anonymous " + p.alias.encode() in page
    assert b"piya" not in page.split(b"Anonymous Community")[1]  # username never shown in the feed


@pytest.mark.parametrize("tag", ["", "politics", "Stress "])
def test_only_allowed_tags(client, tag):
    login_user_(client)
    post(client, tag=tag)
    assert CommunityPost.query.count() == (1 if tag.strip().lower() == "stress" else 0)


@pytest.mark.parametrize("body,reason", [
    ("call me on 9812345678", b"phone numbers"),
    ("mail me at someone@example.com", b"phone numbers"),
    ("check https://example.com", b"Links"),
    ("you are stupid", b"keep it kind"),
    ("kys", b"keep it kind"),
])
def test_screening_rejects(client, body, reason):
    login_user_(client)
    assert reason in post(client, body=body).data
    assert CommunityPost.query.count() == 0


def test_crisis_post_goes_under_review_and_shows_sos(client):
    login_user_(client)
    resp = post(client, body="I want to end my life tonight")
    assert b"SOS Hotlines" in resp.data  # redirected to the SOS page
    p = CommunityPost.query.one()
    assert p.status == "under_review"
    assert b"is under review and only visible to you" in client.get("/community/").data


def test_under_review_post_hidden_from_others(client):
    login_user_(client)
    post(client, body="I want to kill myself")
    pid = CommunityPost.query.one().id
    client.get("/logout")
    login_user_(client, "other", "other@example.com")
    assert client.get(f"/community/post/{pid}").status_code == 404


def test_comments_and_comment_screening(client):
    login_user_(client)
    post(client)
    pid = CommunityPost.query.one().id
    client.post(f"/community/post/{pid}/comment", data={"body": "Sending support, you're not alone"})
    client.post(f"/community/post/{pid}/comment", data={"body": "email me at x@y.com"})
    assert CommunityComment.query.count() == 1
    assert b"Sending support" in client.get(f"/community/post/{pid}").data


def test_reactions_toggle(client):
    login_user_(client)
    post(client)
    pid = CommunityPost.query.one().id
    for kind in ("support", "relate", "heart"):
        client.post(f"/community/post/{pid}/react/{kind}")
    assert CommunityReaction.query.count() == 3
    client.post(f"/community/post/{pid}/react/heart")  # toggle off
    assert CommunityReaction.query.count() == 2
    assert client.post(f"/community/post/{pid}/react/angry").status_code == 404


def test_auto_hide_after_threshold_reports(client, app):
    app.config["COMMUNITY_REPORT_THRESHOLD"] = 3
    login_user_(client, "author", "author@example.com")
    post(client)
    pid = CommunityPost.query.one().id
    for i in range(3):
        client.get("/logout")
        login_user_(client, f"r{i}", f"r{i}@example.com")
        client.post(f"/community/post/{pid}/report")
    p = CommunityPost.query.one()
    assert p.report_count == 3 and p.status == "hidden"
    assert client.get(f"/community/post/{pid}").status_code == 404


def test_same_user_cannot_report_twice(client):
    login_user_(client, "author", "author@example.com")
    post(client)
    pid = CommunityPost.query.one().id
    client.get("/logout")
    login_user_(client, "r", "r@example.com")
    client.post(f"/community/post/{pid}/report")
    resp = client.post(f"/community/post/{pid}/report", follow_redirects=True)
    assert b"already reported" in resp.data
    assert CommunityReport.query.count() == 1 and CommunityPost.query.one().report_count == 1


def test_sort_support_first(client):
    login_user_(client)
    post(client, title="older post")
    post(client, title="newer post")
    older = CommunityPost.query.filter_by(title="older post").one()
    client.post(f"/community/post/{older.id}/react/support")
    recent = client.get("/community/?sort=recent").data
    support = client.get("/community/?sort=support").data
    assert recent.index(b"newer post") < recent.index(b"older post")
    assert support.index(b"older post") < support.index(b"newer post")


def test_owner_can_delete_post_others_cannot(client):
    login_user_(client, "author", "author@example.com")
    post(client)
    pid = CommunityPost.query.one().id
    client.get("/logout")
    login_user_(client, "other", "other@example.com")
    assert client.post(f"/community/post/{pid}/delete").status_code == 404
    client.get("/logout")
    client.post("/login", data={"email": "author@example.com", "password": "Str0ng!Pass"})
    client.post(f"/community/post/{pid}/delete")
    assert CommunityPost.query.count() == 0


def test_guests_can_read_but_not_post(client):
    assert client.get("/community/").status_code == 200
    assert client.post("/community/new", data={"title": "t", "body": "b", "tag": "stress"}).status_code == 302
    assert CommunityPost.query.count() == 0


def test_screen_and_alias_units():
    assert screen("I had a rough week with exams").action == "ok"
    assert screen("I want to die").action == "under_review"
    assert random_alias().count("#") == 1
