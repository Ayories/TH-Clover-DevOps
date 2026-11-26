"""Security tests for the TH-CLOVER customer-service app (REQ-01, REQ-05).

AI-assisted; area: Quality & Security. Written against plan/CONTRACT.md: the app factory
``create_app(config)``, its routes and its configuration keys. All data is synthetic and the
staff password is generated at run time, so no credential is stored in the repository.
"""

import base64
import html
import logging
import os
import re
import secrets

import pytest
from sqlalchemy import MetaData, create_engine
from werkzeug.security import generate_password_hash

# app.main builds a module-level app on import; keep that away from any real database.
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from app.main import create_app  # noqa: E402

STAFF_USER = "staff-test"
STAFF_PASSWORD = secrets.token_urlsafe(18)
SECRET_KEY = secrets.token_hex(32)
STAFF_HASH = generate_password_hash(STAFF_PASSWORD)

# Distinctive synthetic "personal data" that must never reach logs, health or metrics.
PII = {
    "name": "Zebedee Quillfeather",
    "email": "zq.canary@example.test",
    "message": "canary-message-7f3a please reset my account",
}


# --------------------------------------------------------------------------- helpers
def basic(username=STAFF_USER, password=STAFF_PASSWORD):
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def build_app(db_url, **overrides):
    config = {
        "DATABASE_URL": db_url,
        "SECRET_KEY": SECRET_KEY,
        "STAFF_USERNAME": STAFF_USER,
        "STAFF_PASSWORD_HASH": STAFF_HASH,
        "APP_ENV": "test",
        "RELEASE_SHA": "0" * 40,
    }
    config.update(overrides)
    return create_app(config)


@pytest.fixture
def db_url(tmp_path):
    return f"sqlite:///{(tmp_path / 'security.db').as_posix()}"


@pytest.fixture
def app(db_url):
    return build_app(db_url)


@pytest.fixture
def client(app):
    return app.test_client()


def submit(client, **fields):
    return client.post("/api/requests", json={**PII, **fields})


def stored(client):
    """Rows as seen by an authenticated member of staff."""
    response = client.get("/api/requests", headers=basic())
    assert response.status_code == 200
    body = response.get_json()
    if isinstance(body, dict):
        body = body.get("requests", body.get("items"))
    assert isinstance(body, list), "unexpected shape for GET /api/requests"
    return body


def hidden_fields(page):
    """Hidden inputs of a rendered form (this is where the CSRF token lives)."""
    fields = {}
    for tag in re.findall(r"<input\b[^>]*>", page, flags=re.IGNORECASE):
        attributes = dict(re.findall(r'([\w-]+)="([^"]*)"', tag))
        if attributes.get("type", "").lower() == "hidden" and "name" in attributes:
            fields[attributes["name"]] = html.unescape(attributes.get("value", ""))
    return fields


def csrf_fields(client, path="/", headers=None):
    response = client.get(path, headers=headers or {})
    assert response.status_code == 200
    fields = {
        name: value
        for name, value in hidden_fields(response.get_data(as_text=True)).items()
        if "csrf" in name.lower()
    }
    assert fields, f"no CSRF hidden field found on {path}"
    return fields


def new_status(client):
    """A status value offered by the staff page that differs from the current one."""
    current = stored(client)[0]["status"]
    page = client.get("/staff", headers=basic()).get_data(as_text=True)
    offered = re.findall(r'<option[^>]*value="([^"]+)"', page)
    offered += re.findall(r'name="status"[^>]*value="([^"]+)"', page)
    for value in offered:
        if value != current:
            return value
    pytest.fail("the staff page offers no status value to change to")


# --------------------------------------------------------------------------- authentication
@pytest.mark.parametrize("path", ["/staff", "/api/requests"])
@pytest.mark.parametrize(
    "headers",
    [
        {},
        basic(password="wrong-password"),
        basic(username="someone-else"),
        basic(password=""),
        {"Authorization": "Bearer not-a-real-token"},
        {"Authorization": "Basic %%%not-base64%%%"},
    ],
    ids=["none", "bad-password", "bad-user", "empty-password", "bearer", "garbage"],
)
def test_staff_reads_refuse_missing_or_wrong_credentials(client, path, headers):
    assert submit(client).status_code == 201
    response = client.get(path, headers=headers)
    assert response.status_code == 401
    assert PII["email"] not in response.get_data(as_text=True)


def test_unauthenticated_challenge_names_basic_auth(client):
    response = client.get("/staff")
    assert response.headers.get("WWW-Authenticate", "").lower().startswith("basic")


def test_correct_credentials_are_accepted(client):
    """Control case: the refusals above are meaningful only if the right login works."""
    assert submit(client).status_code == 201
    assert client.get("/staff", headers=basic()).status_code == 200
    assert stored(client)[0]["email"] == PII["email"]


def test_status_change_refused_without_credentials(client):
    assert submit(client).status_code == 201
    before = stored(client)[0]
    token = csrf_fields(client)
    for headers in ({}, basic(password="wrong-password")):
        response = client.post(
            f"/staff/requests/{before['id']}/status",
            data={**token, "status": new_status(client)},
            headers=headers,
        )
        assert response.status_code == 401
    assert stored(client)[0]["status"] == before["status"]


@pytest.mark.parametrize(
    "unset", [None, "", "not-a-werkzeug-hash"], ids=["none", "empty", "malformed"]
)
@pytest.mark.parametrize(
    "password",
    ["", "admin", "password", STAFF_PASSWORD],
    ids=["pw-empty", "pw-admin", "pw-password", "pw-real"],  # keep the value out of test names
)
def test_staff_access_refused_when_hash_is_not_usable(db_url, monkeypatch, unset, password):
    monkeypatch.delenv("STAFF_PASSWORD_HASH", raising=False)
    client = build_app(db_url, STAFF_PASSWORD_HASH=unset).test_client()
    for path in ("/staff", "/api/requests"):
        response = client.get(path, headers=basic(password=password))
        assert response.status_code in (401, 403, 503), path


# --------------------------------------------------------------------------- CSRF
@pytest.mark.parametrize("token", [None, "forged-token"], ids=["missing", "forged"])
def test_public_form_rejects_missing_or_forged_csrf_token(client, token):
    fields = csrf_fields(client)  # establishes a session, as a real browser would have
    data = dict(PII)
    if token is not None:
        data.update(dict.fromkeys(fields, token))
    response = client.post("/requests", data=data)
    assert response.status_code in (400, 403)
    assert stored(client) == []


def test_public_form_rejects_token_from_another_session(app):
    attacker, victim = app.test_client(), app.test_client()
    stolen = csrf_fields(attacker)
    csrf_fields(victim)
    response = victim.post("/requests", data={**PII, **stolen})
    assert response.status_code in (400, 403)
    assert stored(victim) == []


def test_public_form_accepts_valid_csrf_token(client):
    response = client.post("/requests", data={**PII, **csrf_fields(client)})
    assert response.status_code in (200, 201, 302, 303)
    assert len(stored(client)) == 1


@pytest.mark.parametrize("token", [None, "forged-token"], ids=["missing", "forged"])
def test_staff_status_change_requires_csrf_token(client, token):
    # Browsers re-send Basic credentials automatically, so authentication alone is not enough.
    assert submit(client).status_code == 201
    before = stored(client)[0]
    fields = csrf_fields(client, "/staff", basic())
    data = {"status": new_status(client)}
    if token is not None:
        data.update(dict.fromkeys(fields, token))
    response = client.post(f"/staff/requests/{before['id']}/status", data=data, headers=basic())
    assert response.status_code in (400, 403)
    assert stored(client)[0]["status"] == before["status"]


def test_staff_status_change_with_valid_token(client):
    assert submit(client).status_code == 201
    before = stored(client)[0]
    wanted = new_status(client)
    response = client.post(
        f"/staff/requests/{before['id']}/status",
        data={**csrf_fields(client, "/staff", basic()), "status": wanted},
        headers=basic(),
    )
    assert response.status_code in (200, 302, 303)
    assert stored(client)[0]["status"] == wanted


# --------------------------------------------------------------------------- input validation
@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"email": PII["email"], "message": "hello"},
        {"name": "A", "message": "hello"},
        {"name": "A", "email": PII["email"]},
        {**PII, "name": "   "},
        {**PII, "message": ""},
        {**PII, "email": "not-an-email"},
        {**PII, "name": 12345},
        {**PII, "message": ["a", "list"]},
        {**PII, "email": {"nested": "object"}},
        {**PII, "name": "n" * 5000},
        {**PII, "email": "e" * 5000 + "@example.test"},
        {**PII, "message": "m" * 5000},
        {**PII, "message": "nul\x00byte"},  # PostgreSQL cannot store NUL: must not become a 500
    ],
    ids=[
        "empty",
        "no-name",
        "no-email",
        "no-message",
        "blank-name",
        "blank-message",
        "bad-email",
        "int-name",
        "list-message",
        "object-email",
        "long-name",
        "long-email",
        "long-message",
        "nul-byte",
    ],
)
def test_api_rejects_invalid_input(client, payload):
    response = client.post("/api/requests", json=payload)
    assert response.status_code == 400
    assert stored(client) == []


@pytest.mark.parametrize(
    "body, content_type",
    [
        ("{not json", "application/json"),
        ("[1, 2, 3]", "application/json"),
        ('"just a string"', "application/json"),
        ("null", "application/json"),
        ("name=a&email=a@example.test&message=hi", "application/x-www-form-urlencoded"),
    ],
    ids=["broken", "array", "string", "null", "form-encoded"],
)
def test_api_rejects_non_object_bodies_without_crashing(client, body, content_type):
    response = client.post("/api/requests", data=body, content_type=content_type)
    assert response.status_code in (400, 415)
    assert stored(client) == []


def test_api_rejects_oversize_request(client):
    response = client.post("/api/requests", json={**PII, "message": "x" * (2 * 1024 * 1024)})
    assert response.status_code in (400, 413)
    assert stored(client) == []


def test_request_body_size_is_capped_by_the_framework(app):
    limit = app.config.get("MAX_CONTENT_LENGTH")
    assert limit is not None and limit <= 1024 * 1024


def test_form_rejects_oversize_request(client):
    data = {**csrf_fields(client), **PII, "message": "x" * (2 * 1024 * 1024)}
    response = client.post("/requests", data=data)
    assert response.status_code in (400, 413)
    assert stored(client) == []


def test_staff_rejects_unknown_status_and_unknown_id(client):
    assert submit(client).status_code == 201
    before = stored(client)[0]
    token = csrf_fields(client, "/staff", basic())
    bad = client.post(
        f"/staff/requests/{before['id']}/status",
        data={**token, "status": "<b>owned</b>"},
        headers=basic(),
    )
    assert bad.status_code in (400, 422)
    assert stored(client)[0]["status"] == before["status"]
    missing = client.post(
        "/staff/requests/999999/status",
        data={**token, "status": new_status(client)},
        headers=basic(),
    )
    assert missing.status_code == 404
    injected = client.post(
        "/staff/requests/1%20OR%201=1/status", data={**token, "status": "x"}, headers=basic()
    )
    assert injected.status_code == 404


# --------------------------------------------------------------------------- injection
XSS = '<script>alert("clover")</script>'


def test_stored_input_is_html_escaped_on_staff_page(client):
    response = submit(client, name=XSS, message=f'"><img src=x onerror=alert(1)> {XSS}')
    # Either refusing markup or storing it and escaping on output is safe.
    assert response.status_code in (201, 400)
    page = client.get("/staff", headers=basic()).get_data(as_text=True)
    assert "<script>alert" not in page
    assert "<img src=x" not in page
    if response.status_code == 201:
        assert "&lt;script&gt;" in page


def test_rejected_form_input_is_not_reflected_unescaped(client):
    data = {**csrf_fields(client), "name": XSS, "email": XSS, "message": XSS}
    response = client.post("/requests", data=data, follow_redirects=True)
    assert "<script>alert" not in response.get_data(as_text=True)


@pytest.mark.parametrize(
    "value",
    [
        "Robert'); DROP TABLE requests;--",
        "' OR '1'='1",
        "1; DELETE FROM requests WHERE 1=1",
        "%' UNION SELECT NULL,NULL,NULL--",
    ],
)
def test_sql_injection_looking_input_is_stored_as_plain_text(client, value):
    assert submit(client).status_code == 201
    assert submit(client, name=value, message=value).status_code == 201
    rows = stored(client)
    assert len(rows) == 2, "table damaged or rows duplicated"
    assert any(row["name"] == value and row["message"] == value for row in rows)


# --------------------------------------------------------------------------- headers and cookies
@pytest.mark.parametrize("path", ["/", "/staff", "/health", "/does-not-exist"])
def test_security_headers_on_responses(client, path):
    headers = client.get(path, headers=basic()).headers
    assert headers.get("X-Content-Type-Options") == "nosniff"
    csp = headers.get("Content-Security-Policy", "")
    assert csp, "Content-Security-Policy missing"
    assert headers.get("X-Frame-Options", "").upper() in ("DENY", "SAMEORIGIN") or (
        "frame-ancestors" in csp
    )
    assert headers.get("Referrer-Policy"), "Referrer-Policy missing"


@pytest.mark.parametrize("path", ["/staff", "/api/requests"])
def test_pages_with_personal_data_are_not_cached(client, path):
    assert submit(client).status_code == 201
    response = client.get(path, headers=basic())
    assert "no-store" in response.headers.get("Cache-Control", "")


def test_session_cookie_is_httponly_and_samesite(client):
    cookies = client.get("/").headers.getlist("Set-Cookie")
    assert cookies, "expected a session cookie for CSRF protection"
    for cookie in cookies:
        assert "HttpOnly" in cookie
        assert "SameSite=Lax" in cookie or "SameSite=Strict" in cookie


# --------------------------------------------------------------------------- information leaks
def assert_no_sensitive_text(text, *extra):
    for secret in (SECRET_KEY, STAFF_PASSWORD, STAFF_HASH, *PII.values(), *extra):
        assert secret not in text, f"sensitive value exposed: {secret[:12]}..."


def test_health_exposes_only_the_agreed_fields(client, db_url):
    assert submit(client).status_code == 201
    response = client.get("/health")
    assert response.status_code == 200
    assert set(response.get_json()) == {"status", "database", "version", "environment"}
    assert_no_sensitive_text(response.get_data(as_text=True), db_url, STAFF_USER)


def test_metrics_expose_no_secrets_or_personal_data(client, db_url):
    assert submit(client).status_code == 201
    client.get("/api/requests", headers=basic())
    client.get(f"/probe-{PII['email']}")  # user-controlled paths must not become labels
    body = client.get("/metrics").get_data(as_text=True)
    assert "clover_http_requests_total" in body
    assert_no_sensitive_text(body, db_url, STAFF_USER, "probe-")


class Everything(logging.Handler):
    """Collects every log record, including loggers that do not propagate to root."""

    def __init__(self):
        super().__init__(level=logging.DEBUG)
        self.lines = []

    def emit(self, record):
        self.lines.append(self.format(record))


@pytest.fixture
def all_logs(app, caplog, capfd):
    handler = Everything()
    named = [logging.getLogger(name) for name in list(logging.Logger.manager.loggerDict)]
    # Root, plus every logger that would not pass its records up to root (e.g. "clover").
    loggers = [logging.getLogger(), *(lg for lg in named if not lg.propagate)]
    for logger in loggers:
        logger.addHandler(handler)
    caplog.set_level(logging.DEBUG)

    def read():
        captured = capfd.readouterr()
        return "\n".join([caplog.text, *handler.lines, captured.out, captured.err])

    yield read
    for logger in loggers:
        logger.removeHandler(handler)


def test_normal_and_rejected_traffic_logs_no_personal_data(client, all_logs):
    client.post("/requests", data={**csrf_fields(client), **PII})
    submit(client)
    submit(client, email="broken-" + PII["email"].replace("@", ""))
    client.post("/requests", data=PII)  # rejected: no CSRF token
    client.get("/api/requests", headers=basic(password="guess-" + "q" * 12))
    client.get("/api/requests", headers=basic())
    output = all_logs()
    assert '"event":"request"' in output, "no log output captured, so the check proves nothing"
    assert_no_sensitive_text(output, "guess-" + "q" * 12, basic()["Authorization"])


def test_database_failure_leaks_no_personal_data(client, db_url, all_logs):
    # SQLAlchemy puts bound parameters (name, email, message) into its exception text.
    engine = create_engine(db_url)
    metadata = MetaData()
    metadata.reflect(engine)
    metadata.drop_all(engine)
    engine.dispose()
    try:
        response = submit(client)
    except Exception as error:  # an unhandled error would be written to the log by gunicorn
        pytest.fail(f"unhandled {type(error).__name__} when the database is broken")
    assert response.status_code in (500, 503)
    assert_no_sensitive_text(response.get_data(as_text=True))
    output = all_logs()
    assert "database_error" in output, "the failure should be logged (by type, without data)"
    assert_no_sensitive_text(output)


# --------------------------------------------------------------------------- how to show the gate failing
# Demonstrating that a failed check blocks promotion needs no committed failing test:
# set QUALITY_GATE_DEMO=1 and the test below fails on purpose. See
# docs/quality/test-strategy.md ("Demonstrating a failing quality gate").
def test_quality_gate_demonstration_switch():
    # pytest.fail rather than assert, so that the environment is never dumped into the log.
    if os.environ.get("QUALITY_GATE_DEMO") == "1":
        pytest.fail("Deliberate failure: QUALITY_GATE_DEMO=1 shows the quality gate blocking")
