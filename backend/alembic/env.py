"""Alembic environment. Migrations run as the schema owner (MIGRATION_DATABASE_URL), never as the app role."""

from __future__ import annotations

from sqlalchemy import create_engine, pool

from alembic import context
from app.core.config import get_settings

config = context.config
target_metadata = None  # Migrations are hand-written: RLS policies, grants and constraints are explicit.


def run_migrations_offline() -> None:
    context.configure(url=get_settings().migration_database_url, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = config.attributes.get("url") or get_settings().migration_database_url
    engine = create_engine(url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, transaction_per_migration=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
