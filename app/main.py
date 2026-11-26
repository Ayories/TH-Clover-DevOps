"""Evolving Ltd customer-service app (CMP6237 proof of concept, AI-assisted).

Public users send a support request; staff read the requests and change their
status. Run with one gunicorn worker and several threads so that the in-process
Prometheus counter is correct (see Dockerfile).
"""

from __future__ import annotations

import hmac
import json
import logging
import os
import re
import secrets
import sys
import threading
import time
import unicodedata
from datetime import UTC, datetime
from functools import wraps

from flask import (
    Flask,
    abort,
    current_app,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, generate_latest
from sqlalchemy import DateTime, String, Text, create_engine, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash

STATUSES = ("new", "in_progress", "resolved")
NAME_MAX = 100
EMAIL_MAX = 254
MESSAGE_MAX = 2000
MAX_BODY_BYTES = 128 * 1024  # a full valid form (URL-encoded) is under 32 KiB
LIST_LIMIT = 200
MAX_ID = 2**31 - 1  # PostgreSQL INTEGER
SCHEMA_LOCK_ID = 623700  # arbitrary key for the PostgreSQL advisory lock
EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")

REQUESTS_TOTAL = Counter("clover_http_requests_total", "HTTP requests", ["endpoint"])
DATABASE_UP = Gauge("clover_database_up", "1 if the database answered the last check, else 0")

log = logging.getLogger("clover")


def log_event(event: str, level: int = logging.INFO, **fields) -> None:
    """Write one JSON line. Never pass form values, headers or exception text."""
    record = {
        "ts": datetime.now(UTC).isoformat(timespec="milliseconds"),
        "level": logging.getLevelName(level).lower(),
        "event": event,
        **fields,
    }
    log.log(level, json.dumps(record, separators=(",", ":")))


def _configure_logging() -> None:
    if not log.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(message)s"))
        log.addHandler(handler)
        log.setLevel(logging.INFO)
        log.propagate = False


class Base(DeclarativeBase):
    pass


class SupportRequest(Base):
    __tablename__ = "support_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(NAME_MAX))
    email: Mapped[str] = mapped_column(String(EMAIL_MAX))
    message: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default=STATUSES[0])
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    @property
    def created_utc(self) -> datetime:
        if self.created_at.tzinfo is None:  # SQLite drops the time zone; values are UTC
            return self.created_at.replace(tzinfo=UTC)
        return self.created_at.astimezone(UTC)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "message": self.message,
            "status": self.status,
            "created_at": self.created_utc.isoformat(),
        }


class Database:
    """Engine plus lazy, race-safe table creation."""

    def __init__(self, url: str):
        options: dict = {
            "pool_pre_ping": True,
            # Keep bound values (customer data) out of SQLAlchemy error messages.
            "hide_parameters": True,
        }
        if url.startswith("postgresql"):
            options["connect_args"] = {"connect_timeout": 3}
        self.engine = create_engine(url, **options)
        self._ready = False
        self._lock = threading.Lock()

    def ensure_schema(self) -> None:
        """Create missing tables once. Raises SQLAlchemyError if the DB is not ready.

        Safe to call from several threads, workers or containers at once: on
        PostgreSQL an advisory lock serialises the check-then-create step.
        """
        if self._ready:
            return
        with self._lock:
            if self._ready:
                return
            with self.engine.begin() as connection:
                if self.engine.dialect.name == "postgresql":
                    connection.execute(
                        text("SELECT pg_advisory_xact_lock(:key)"), {"key": SCHEMA_LOCK_ID}
                    )
                Base.metadata.create_all(connection)
            self._ready = True

    def session(self) -> Session:
        self.ensure_schema()
        return Session(self.engine)


def get_db() -> Database:
    return current_app.extensions["clover_db"]


# --- validation -------------------------------------------------------------


def _has_forbidden_characters(value: str, multiline: bool) -> bool:
    allowed = "\n\t" if multiline else ""
    # Cc = control characters (including NUL, which PostgreSQL rejects),
    # Cs = lone surrogates (cannot be encoded as UTF-8).
    return any(unicodedata.category(char) in ("Cc", "Cs") and char not in allowed for char in value)


def validate_request(data) -> tuple[dict, dict]:
    """Return (cleaned values, errors by field) for a new support request."""
    if not hasattr(data, "get"):
        return {}, {"body": "Expected an object with name, email and message."}

    cleaned: dict = {}
    errors: dict = {}
    for field, limit in (("name", NAME_MAX), ("email", EMAIL_MAX), ("message", MESSAGE_MAX)):
        value = data.get(field)
        if not isinstance(value, str):
            errors[field] = f"{field.capitalize()} is required."
            continue
        value = value.replace("\r\n", "\n").replace("\r", "\n").strip()
        if not value:
            errors[field] = f"{field.capitalize()} is required."
        elif len(value) > limit:
            errors[field] = f"{field.capitalize()} must be at most {limit} characters."
        elif _has_forbidden_characters(value, multiline=field == "message"):
            errors[field] = f"{field.capitalize()} contains characters that are not allowed."
        elif field == "email" and not EMAIL_RE.fullmatch(value):
            errors[field] = "Enter a valid email address."
        else:
            cleaned[field] = value
    return cleaned, errors


def save_request(values: dict) -> int:
    with get_db().session() as db_session:
        row = SupportRequest(**values)
        db_session.add(row)
        db_session.commit()
        return row.id


def latest_requests() -> list[SupportRequest]:
    with get_db().session() as db_session:
        query = select(SupportRequest).order_by(SupportRequest.id.desc()).limit(LIST_LIMIT)
        return list(db_session.scalars(query))


# --- CSRF and staff authentication -----------------------------------------


def csrf_token() -> str:
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


def require_csrf() -> None:
    expected = session.get("csrf_token", "")
    supplied = request.form.get("csrf_token", "")
    if not expected or not hmac.compare_digest(
        expected.encode(), supplied.encode("utf-8", "replace")
    ):
        abort(400, description="The form has expired. Reload the page and try again.")


def _staff_credentials_ok() -> bool:
    expected_user = current_app.config.get("STAFF_USERNAME") or ""
    password_hash = current_app.config.get("STAFF_PASSWORD_HASH") or ""
    auth = request.authorization
    if not expected_user or not password_hash or auth is None or auth.type != "basic":
        return False
    # Always do both checks so the response time does not reveal a valid username.
    user_ok = hmac.compare_digest(
        (auth.username or "").encode("utf-8", "replace"), expected_user.encode()
    )
    try:
        password_ok = check_password_hash(password_hash, auth.password or "")
    except (ValueError, TypeError):
        log_event("config_error", logging.ERROR, detail="STAFF_PASSWORD_HASH is not valid")
        password_ok = False
    return user_ok & password_ok


def staff_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not _staff_credentials_ok():
            # Record rejected credentials (not the first, empty browser request). The username
            # and password are never logged, because either may contain personal data.
            if request.authorization is not None:
                log_event("staff_login_failed", logging.WARNING, path=request.path)
            abort(401)
        return view(*args, **kwargs)

    return wrapper


# --- application factory ----------------------------------------------------


def create_app(config: dict | None = None) -> Flask:
    _configure_logging()
    app = Flask(__name__)
    app.config.update(
        DATABASE_URL=os.getenv("DATABASE_URL") or "sqlite:///clover.db",
        RELEASE_SHA=os.getenv("RELEASE_SHA") or "local",
        APP_ENV=os.getenv("APP_ENV") or "development",
        SECRET_KEY=os.getenv("SECRET_KEY") or "",
        STAFF_USERNAME=os.getenv("STAFF_USERNAME") or "",
        STAFF_PASSWORD_HASH=os.getenv("STAFF_PASSWORD_HASH") or "",
        MAX_CONTENT_LENGTH=MAX_BODY_BYTES,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Strict",
    )
    app.config.update(config or {})
    # Cookies are not separated by port, and staging and production share a host.
    app.config["SESSION_COOKIE_NAME"] = f"clover_session_{app.config['APP_ENV']}"
    if not app.config["SECRET_KEY"]:
        app.config["SECRET_KEY"] = secrets.token_hex(32)
        log_event("config_warning", logging.WARNING, detail="SECRET_KEY unset; using a random one")
    app.json.compact = True  # shell scripts match '"status":"ok"'

    database = Database(app.config["DATABASE_URL"])
    app.extensions["clover_db"] = database
    try:
        database.ensure_schema()
    except SQLAlchemyError as error:
        # Not fatal: /health reports 503 and the next request tries again.
        log_event("database_not_ready", logging.WARNING, error=type(error).__name__)

    app.jinja_env.globals["csrf_token"] = csrf_token
    _register_hooks(app)
    _register_routes(app)
    return app


def _endpoint_label() -> str:
    # A fixed set of names; never the raw path, which could contain personal data.
    return request.endpoint or "unmatched"


def _register_hooks(app: Flask) -> None:
    @app.before_request
    def start_timer():
        g.started = time.perf_counter()

    @app.after_request
    def finish_request(response):
        endpoint = _endpoint_label()
        REQUESTS_TOTAL.labels(endpoint=endpoint).inc()
        response.headers.update(
            {
                "Content-Security-Policy": (
                    "default-src 'none'; style-src 'self'; form-action 'self'; "
                    "frame-ancestors 'none'; base-uri 'none'"
                ),
                "X-Content-Type-Options": "nosniff",
                "X-Frame-Options": "DENY",
                "Referrer-Policy": "no-referrer",
                "Permissions-Policy": "camera=(), geolocation=(), microphone=()",
                "Cache-Control": "no-store",
            }
        )
        started = g.get("started")
        log_event(
            "request",
            method=request.method,
            endpoint=endpoint,
            status=response.status_code,
            duration_ms=round((time.perf_counter() - started) * 1000, 1) if started else None,
        )
        return response

    def error_response(status: int, message: str):
        if request.path.startswith("/api/"):
            response = jsonify(error=message)
        else:
            response = current_app.make_response(
                render_template("error.html", status=status, message=message)
            )
        response.status_code = status
        if status == 401:
            response.headers["WWW-Authenticate"] = 'Basic realm="staff", charset="UTF-8"'
        return response

    @app.errorhandler(HTTPException)
    def handle_http_error(error):
        if error.code is None or error.code < 400:
            return error
        return error_response(error.code, error.description)

    @app.errorhandler(SQLAlchemyError)
    def handle_database_error(error):
        log_event("database_error", logging.ERROR, error=type(error).__name__)
        return error_response(503, "The service is temporarily unavailable.")

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        # Exception messages can quote user input, so log only type and location.
        frame = error.__traceback__
        while frame and frame.tb_next:
            frame = frame.tb_next
        location = (
            f"{os.path.basename(frame.tb_frame.f_code.co_filename)}:{frame.tb_lineno}"
            if frame
            else "unknown"
        )
        log_event("unhandled_error", logging.ERROR, error=type(error).__name__, at=location)
        return error_response(500, "Something went wrong.")


def _register_routes(app: Flask) -> None:
    @app.get("/")
    def index():
        return render_template(
            "form.html", values={}, errors={}, sent=request.args.get("sent") == "1"
        )

    @app.post("/requests")
    def submit_request():
        require_csrf()
        cleaned, errors = validate_request(request.form)
        if errors:
            return render_template("form.html", values=request.form, errors=errors), 400
        save_request(cleaned)
        return redirect(url_for("index", sent=1), code=303)

    @app.post("/api/requests")
    def api_create_request():
        # Only application/json is accepted, so a cross-site HTML form cannot use this.
        if not request.is_json:
            return jsonify(error="Content-Type must be application/json."), 400
        try:
            data = request.get_json(silent=True)
        except RecursionError:
            data = None
        cleaned, errors = validate_request(data)
        if errors:
            return jsonify(error="Invalid request.", fields=errors), 400
        return jsonify(id=save_request(cleaned)), 201

    @app.get("/api/requests")
    @staff_required
    def api_list_requests():
        return jsonify([row.to_dict() for row in latest_requests()])

    @app.get("/staff")
    @staff_required
    def staff():
        return render_template("staff.html", requests=latest_requests(), statuses=STATUSES)

    @app.post("/staff/requests/<int:request_id>/status")
    @staff_required
    def update_status(request_id: int):
        require_csrf()
        status = request.form.get("status", "")
        if status not in STATUSES:
            abort(400, description="Unknown status.")
        if request_id > MAX_ID:
            abort(404)
        with get_db().session() as db_session:
            row = db_session.get(SupportRequest, request_id)
            if row is None:
                abort(404)
            row.status = status
            db_session.commit()
        return redirect(url_for("staff"), code=303)

    def database_error() -> str | None:
        """Return None if the database answers, else the error class name."""
        try:
            # Querying the table proves both the connection and the schema.
            with get_db().session() as db_session:
                db_session.execute(select(SupportRequest.id).limit(1))
        except SQLAlchemyError as error:
            DATABASE_UP.set(0)
            return type(error).__name__
        DATABASE_UP.set(1)
        return None

    @app.get("/health")
    def health():
        details = {
            "version": current_app.config["RELEASE_SHA"],
            "environment": current_app.config["APP_ENV"],
        }
        error = database_error()
        if error:
            log_event("health_check_failed", logging.ERROR, error=error)
            return jsonify(status="error", database="unavailable", **details), 503
        return jsonify(status="ok", database="ok", **details), 200

    @app.get("/metrics")
    def metrics():
        database_error()  # refresh clover_database_up on every scrape
        return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}


app = create_app()
