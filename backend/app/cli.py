"""Operational commands.

    python -m app.cli make-platform-admin user@example.com
    python -m app.cli relay-outbox          # deliver pending outbox events once (useful without Celery beat)
    python -m app.cli sync-permissions      # re-apply the permission catalog (runs as the owner role)
"""

from __future__ import annotations

import asyncio
import sys

from sqlalchemy import create_engine, text, update

from app.core.config import get_settings
from app.core.database import get_sessionmaker
from app.modules.identity.models import User
from app.modules.tenant.permissions.catalog import sync_catalog_sql
from app.shared.outbox import relay_batch


async def _make_admin(email: str) -> None:
    async with get_sessionmaker()() as s, s.begin():
        res = await s.execute(update(User).where(User.email == email.lower()).values(is_platform_admin=True))
        print("updated" if res.rowcount else "no such user")  # noqa: T201


async def _relay() -> None:
    import app.workers.handlers  # noqa: F401  (registers handlers)

    print(f"delivered {await relay_batch(get_sessionmaker())} event(s)")  # noqa: T201


def _sync() -> None:
    engine = create_engine(get_settings().migration_database_url)
    with engine.begin() as conn:
        for sql, params in sync_catalog_sql():
            conn.execute(text(sql), params)
    print("permission catalog synchronized")  # noqa: T201


def main() -> None:
    cmd, *args = sys.argv[1:] or ["help"]
    if cmd == "make-platform-admin" and args:
        asyncio.run(_make_admin(args[0]))
    elif cmd == "relay-outbox":
        asyncio.run(_relay())
    elif cmd == "sync-permissions":
        _sync()
    else:
        print(__doc__)  # noqa: T201


if __name__ == "__main__":
    main()
