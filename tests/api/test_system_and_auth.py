def test_health_and_readiness(client):
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/health/ready").json()["database"] == "up"


def test_version_reports_build_info_without_login(client):
    body = client.get("/api/version").json()
    assert body == {"service": "backend", "build_number": "42", "git_commit": "abc1234", "build_time": "unknown"}


def test_login_and_me(client, auth):
    me = client.get("/api/auth/me", headers=auth)
    assert me.status_code == 200 and me.json()["email"] == "admin@test.local"


def test_wrong_password_gives_uniform_error(client):
    response = client.post("/api/auth/login", json={"email": "admin@test.local", "password": "nope"})
    assert response.status_code == 401
    body = response.json()
    assert body["code"] == "unauthorized" and body["request_id"] == response.headers["x-request-id"]


def test_protected_routes_need_a_token(client):
    for path in ("/api/documents", "/api/comparisons", "/api/search?q=threshold"):
        assert client.get(path).status_code == 401


def test_invalid_payload_is_a_422(client):
    response = client.post("/api/auth/login", json={"email": "not-an-email"})
    assert response.status_code == 422 and response.json()["code"] == "validation_error"
