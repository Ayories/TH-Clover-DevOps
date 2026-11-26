"""Functional and integration tests for the application interface (AI-assisted)."""

import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from app.main import Base, SupportRequest, create_app, log
from app.seed import SYNTHETIC_REQUESTS, seed

VALID = {"name": "Test Person", "email": "person@example.com", "message": "Synthetic request."}


def count_rows(app):
    with app.extensions["clover_db"].session() as session:
        return session.scalar(select(func.count()).select_from(SupportRequest))


def csrf_from(response):
    match = re.search(r'name="csrf_token" value="([^"]+)"', response.get_data(as_text=True))
    assert match, "page has no CSRF token"
    return match.group(1)


def create(client, **overrides):
    response = client.post("/api/requests", json={**VALID, **overrides})
    assert response.status_code == 201
    return response.json["id"]


def first_row(client, staff_auth):
    return client.get("/api/requests", auth=staff_auth).json[0]


# --- health and metrics -----------------------------------------------------


def test_health_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json == {
        "status": "ok",
        "database": "ok",
        "version": "0" * 40,
        "environment": "test",
    }
    assert b'"status":"ok"' in response.data  # shell scripts match this exact text


def test_health_503_when_database_down(app_config, tmp_path):
    broken = {**app_config, "DATABASE_URL": f"sqlite:///{tmp_path / 'missing' / 'x.db'}"}
    client = create_app(broken).test_client()  # start-up must not crash
    response = client.get("/health")
    assert response.status_code == 503
    assert response.json["database"] == "unavailable"
    assert b'"status":"ok"' not in response.data
    assert client.post("/api/requests", json=VALID).status_code == 503


def test_database_that_becomes_ready_after_startup(app_config, tmp_path):
    folder = tmp_path / "later"
    config = {**app_config, "DATABASE_URL": f"sqlite:///{folder / 'x.db'}"}
    client = create_app(config).test_client()
    assert client.get("/health").status_code == 503
    folder.mkdir()  # the "database" becomes available
    assert client.get("/health").status_code == 200
    assert client.post("/api/requests", json=VALID).status_code == 201


def test_several_app_instances_can_start_together(app):
    database = app.extensions["clover_db"]
    Base.metadata.drop_all(database.engine)
    # Separate apps imitate separate workers, so the in-process lock cannot help.
    # SQLite serialises writers itself; the PostgreSQL CI job exercises the real race.
    config = dict(app.config)
    with ThreadPoolExecutor(max_workers=4) as pool:
        apps = list(pool.map(lambda _: create_app(config), range(4)))
    for other in apps:
        assert other.test_client().get("/health").status_code == 200
        other.extensions["clover_db"].engine.dispose()


def test_metrics_report_database_up_and_down(client, monkeypatch):
    assert "clover_database_up 1.0" in client.get("/metrics").get_data(as_text=True)

    def broken_session(*args, **kwargs):
        raise SQLAlchemyError("database stopped")

    monkeypatch.setattr(client.application.extensions["clover_db"], "session", broken_session)
    assert "clover_database_up 0.0" in client.get("/metrics").get_data(as_text=True)
    assert client.get("/health").status_code == 503


def test_metrics_count_by_endpoint(client):
    def value():
        body = client.get("/metrics").get_data(as_text=True)
        match = re.search(r'^clover_http_requests_total\{endpoint="health"\} (\S+)', body, re.M)
        return float(match.group(1)) if match else 0.0

    before = value()
    client.get("/health")
    client.get("/health")
    assert value() == before + 2


def test_logs_are_one_json_line_without_personal_data(client, staff_auth):
    lines = []
    handler = logging.Handler()
    handler.emit = lambda record: lines.append(record.getMessage())
    log.addHandler(handler)
    try:
        create(client, name="Zebedee Marker", email="zebedee@example.com", message="PRIVATE-TEXT")
        client.get("/api/requests?email=zebedee@example.com", auth=staff_auth)
        client.get("/nothing/zebedee@example.com")
        metrics = client.get("/metrics").get_data(as_text=True)
    finally:
        log.removeHandler(handler)

    combined = "\n".join(lines) + metrics
    for secret in ("Zebedee", "zebedee", "PRIVATE-TEXT", staff_auth[1]):
        assert secret not in combined
    assert all("\n" not in line for line in lines)
    first = json.loads(lines[0])
    assert first["event"] == "request"
    assert first["method"] == "POST"
    assert first["endpoint"] == "api_create_request"
    assert first["status"] == 201
    assert 'endpoint="unmatched"' in metrics


# --- public JSON API --------------------------------------------------------


def test_api_create_and_staff_list(client, staff_auth):
    request_id = create(client, name="  Padded Name  ", message="line one\r\nline two")
    row = first_row(client, staff_auth)
    assert row["id"] == request_id
    assert row["name"] == "Padded Name"
    assert row["email"] == VALID["email"]
    assert row["message"] == "line one\nline two"
    assert row["status"] == "new"
    assert row["created_at"].endswith("+00:00")


@pytest.mark.parametrize(
    "payload",
    [
        {},
        [],
        "text",
        {**VALID, "name": ""},
        {**VALID, "name": "   "},
        {**VALID, "name": 5},
        {**VALID, "name": "x" * 101},
        {**VALID, "name": "two\nlines"},
        {**VALID, "email": "not-an-email"},
        {**VALID, "email": "a b@example.com"},
        {**VALID, "email": "x" * 250 + "@example.com"},
        {**VALID, "message": "x" * 2001},
        {**VALID, "message": "nul\x00byte"},
        {**VALID, "message": "lone \ud800 surrogate"},
        {"name": "Only Name"},
    ],
)
def test_api_rejects_invalid_input(app, client, payload):
    response = client.post(
        "/api/requests", data=json.dumps(payload), content_type="application/json"
    )
    assert response.status_code == 400
    assert "error" in response.json
    assert count_rows(app) == 0


@pytest.mark.parametrize(
    ("body", "content_type"),
    [
        ("{not json", "application/json"),
        ("[" * 100_000, "application/json"),
        (json.dumps(VALID), "text/plain"),
        ("name=a&email=a@example.com&message=b", "application/x-www-form-urlencoded"),
    ],
    ids=["broken", "deeply-nested", "wrong-type", "form-encoded"],
)
def test_api_rejects_bad_bodies(client, body, content_type):
    assert client.post("/api/requests", data=body, content_type=content_type).status_code == 400


def test_maximum_lengths_are_accepted(client):
    create(client, name="n" * 100, message="\U0001f600" * 2000)


def test_maximum_message_fits_through_the_form(client):
    token = csrf_from(client.get("/"))
    data = {**VALID, "message": "\U0001f600" * 2000, "csrf_token": token}
    assert client.post("/requests", data=data).status_code == 303


@pytest.mark.parametrize("url", ["/api/requests", "/requests"])
def test_oversized_request_rejected(app, client, url):
    response = client.post(url, data="x" * 200_000, content_type="application/json")
    assert response.status_code == 413
    assert count_rows(app) == 0


def test_sql_text_is_stored_as_data(client, staff_auth):
    text = "'; DROP TABLE support_requests; --"
    create(client, message=text)
    assert first_row(client, staff_auth)["message"] == text


# --- public form ------------------------------------------------------------


def test_form_submit(app, client):
    token = csrf_from(client.get("/"))
    response = client.post("/requests", data={**VALID, "csrf_token": token})
    assert response.status_code == 303
    assert response.headers["Location"].endswith("/?sent=1")
    assert "has been received" in client.get("/?sent=1").get_data(as_text=True)
    assert count_rows(app) == 1


@pytest.mark.parametrize("token", [None, "", "wrong", "nön-ascii"])
def test_form_requires_csrf_token(app, client, token):
    client.get("/")
    data = dict(VALID) if token is None else {**VALID, "csrf_token": token}
    assert client.post("/requests", data=data).status_code == 400
    assert count_rows(app) == 0


def test_form_token_without_session_rejected(app):
    token = csrf_from(app.test_client().get("/"))
    other = app.test_client()  # has no session cookie
    assert other.post("/requests", data={**VALID, "csrf_token": token}).status_code == 400


def test_form_validation_errors_are_shown_and_escaped(app, client):
    token = csrf_from(client.get("/"))
    data = {"name": "<script>alert(1)</script>", "email": "bad", "message": "hi"}
    response = client.post("/requests", data={**data, "csrf_token": token})
    page = response.get_data(as_text=True)
    assert response.status_code == 400
    assert "Enter a valid email address." in page
    assert "<script>" not in page
    assert "&lt;script&gt;" in page
    assert count_rows(app) == 0


# --- staff pages ------------------------------------------------------------


@pytest.mark.parametrize("url", ["/staff", "/api/requests"])
@pytest.mark.parametrize("auth", [None, ("test-staff", "wrong"), ("someone", "wrong")])
def test_staff_requires_valid_credentials(client, url, auth):
    response = client.get(url, auth=auth)
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"].startswith("Basic")


def test_wrong_username_with_right_password_refused(client, staff_auth):
    assert client.get("/staff", auth=("someone", staff_auth[1])).status_code == 401


@pytest.mark.parametrize("password_hash", ["", "not-a-hash", "unknown$salt$value"])
def test_staff_refused_without_usable_hash(app_config, staff_auth, password_hash):
    client = create_app({**app_config, "STAFF_PASSWORD_HASH": password_hash}).test_client()
    assert client.get("/staff", auth=staff_auth).status_code == 401
    assert client.get("/api/requests", auth=staff_auth).status_code == 401


def test_staff_page_escapes_content(client, staff_auth):
    create(client, message="<img src=x onerror=alert(1)>")
    page = client.get("/staff", auth=staff_auth).get_data(as_text=True)
    assert "<img" not in page
    assert "&lt;img" in page


def test_staff_updates_status(client, staff_auth):
    request_id = create(client)
    token = csrf_from(client.get("/staff", auth=staff_auth))
    response = client.post(
        f"/staff/requests/{request_id}/status",
        data={"status": "resolved", "csrf_token": token},
        auth=staff_auth,
    )
    assert response.status_code == 303
    assert first_row(client, staff_auth)["status"] == "resolved"


@pytest.mark.parametrize(
    ("target", "status", "use_auth", "use_token", "expected"),
    [
        ("{id}", "resolved", False, True, 401),
        ("{id}", "resolved", True, False, 400),
        ("{id}", "deleted", True, True, 400),
        ("999999", "resolved", True, True, 404),
        ("99999999999999999999", "resolved", True, True, 404),
    ],
    ids=["no-auth", "no-csrf", "bad-status", "unknown-id", "huge-id"],
)
def test_status_update_refused(client, staff_auth, target, status, use_auth, use_token, expected):
    request_id = create(client)
    token = csrf_from(client.get("/staff", auth=staff_auth))
    data = {"status": status, **({"csrf_token": token} if use_token else {})}
    response = client.post(
        f"/staff/requests/{target.format(id=request_id)}/status",
        data=data,
        auth=staff_auth if use_auth else None,
    )
    assert response.status_code == expected
    assert first_row(client, staff_auth)["status"] == "new"


# --- headers, cookies, errors, seed ----------------------------------------


@pytest.mark.parametrize("url", ["/", "/health", "/metrics", "/staff", "/no-such-page"])
def test_security_headers(client, url):
    headers = client.get(url).headers
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert headers["Referrer-Policy"] == "no-referrer"
    assert headers["Cache-Control"] == "no-store"
    assert "default-src 'none'" in headers["Content-Security-Policy"]


def test_session_cookie_flags(client):
    cookie = client.get("/").headers["Set-Cookie"]
    assert cookie.startswith("clover_session_test=")
    assert "HttpOnly" in cookie
    assert "SameSite=Strict" in cookie


def test_stylesheet_served(client):
    response = client.get("/static/style.css")
    assert response.status_code == 200
    response.close()


def test_unknown_route_and_method(client):
    assert client.get("/no-such-page").status_code == 404
    assert client.get("/requests").status_code == 405
    assert client.get("/api/no-such").json["error"]


def test_unexpected_error_hides_details(app, client, monkeypatch):
    def explode(_values):
        raise RuntimeError("person@example.com")

    monkeypatch.setattr("app.main.save_request", explode)
    app.config["TESTING"] = False
    response = client.post("/api/requests", json=VALID)
    assert response.status_code == 500
    assert b"person@example.com" not in response.data


def test_seed_is_idempotent_and_synthetic(app):
    with app.app_context():
        assert seed() == len(SYNTHETIC_REQUESTS)
        assert seed() == 0
    assert count_rows(app) == len(SYNTHETIC_REQUESTS)
    assert all(email.endswith("@example.com") for _, email, _, _ in SYNTHETIC_REQUESTS)
