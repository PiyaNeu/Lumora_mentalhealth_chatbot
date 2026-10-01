def test_app_creates_with_all_blueprints(app):
    expected = {
        "main", "auth", "chat", "mood", "journal", "community",
        "selfhelp", "consultation", "evaluation", "account", "errors",
    }
    assert expected <= set(app.blueprints)


def test_home_page_loads(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Lumora" in resp.data


def test_unknown_page_returns_404(client):
    assert client.get("/does-not-exist").status_code == 404


def test_topic_endpoint_returns_content(client):
    resp = client.post("/topic", data={"title": "nonexistent"})
    assert resp.status_code == 200
    assert resp.get_json()["contents"] == ["Topic not found"]
