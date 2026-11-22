"""Start-up tasks: apply migrations under a PostgreSQL advisory lock, then make
sure the admin user exists. Several replicas may start at once; the lock
ensures only one of them migrates."""

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import select, text

from regdiff_api.core.security import hash_password
from regdiff_common.config import get_settings
from regdiff_common.db import get_engine, session_scope
from regdiff_common.logging import log_event
from regdiff_common.models import User

log = logging.getLogger(__name__)

MIGRATION_LOCK_ID = 7_263_541
MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def run_migrations() -> None:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    with get_engine().connect() as connection:
        connection.execute(text("SELECT pg_advisory_lock(:id)"), {"id": MIGRATION_LOCK_ID})
        try:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
            connection.commit()
        finally:
            connection.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": MIGRATION_LOCK_ID})
            connection.commit()
    log_event(log, "migrations_applied")


def ensure_admin_user() -> None:
    settings = get_settings()
    email = settings.admin_email.lower()
    with session_scope() as session:
        if session.scalar(select(User).where(User.email == email)) is None:
            session.add(User(email=email, password_hash=hash_password(settings.admin_password), role="admin"))
            log_event(log, "admin_user_created", email=email)


def bootstrap() -> None:
    run_migrations()
    ensure_admin_user()
