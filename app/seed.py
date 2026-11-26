"""Add a few clearly synthetic support requests. Safe to run more than once.

Usage: python -m app.seed   (uses DATABASE_URL, like the application)
"""

from __future__ import annotations

from sqlalchemy import select

from app.main import SupportRequest, app, get_db

SYNTHETIC_REQUESTS = (
    ("Synthetic Alex", "alex@example.com", "SYNTHETIC: I cannot sign in.", "new"),
    ("Synthetic Blair", "blair@example.com", "SYNTHETIC: Send my invoice.", "in_progress"),
    ("Synthetic Casey", "casey@example.com", "SYNTHETIC: Change my address.", "resolved"),
)


def seed() -> int:
    """Insert missing synthetic rows and return how many were added."""
    added = 0
    with get_db().session() as db_session:
        for name, email, message, status in SYNTHETIC_REQUESTS:
            query = select(SupportRequest.id).where(
                SupportRequest.email == email, SupportRequest.message == message
            )
            if db_session.execute(query).first() is None:
                row = SupportRequest(name=name, email=email, message=message, status=status)
                db_session.add(row)
                added += 1
        db_session.commit()
    return added


def main() -> None:
    with app.app_context():
        print(f"Seed complete: {seed()} synthetic request(s) added.")


if __name__ == "__main__":
    main()
