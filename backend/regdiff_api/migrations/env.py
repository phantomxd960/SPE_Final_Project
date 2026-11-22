from alembic import context
from sqlalchemy import create_engine

from regdiff_common.config import get_settings
from regdiff_common.models import Base

target_metadata = Base.metadata


def run_migrations() -> None:
    connection = context.config.attributes.get("connection")
    if connection is not None:  # called from bootstrap, which holds the advisory lock
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
        return

    engine = create_engine(get_settings().sqlalchemy_url)
    with engine.connect() as conn:
        context.configure(connection=conn, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations()
