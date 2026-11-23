"""Operational commands.

    python -m app.cli make-platform-admin user@example.com
    python -m app.cli relay-outbox          # deliver pending outbox events once (useful without Celery beat)
    python -m app.cli sync-permissions      # re-apply the permission catalog (runs as the owner role)
    python -m app.cli ensure-storage        # create the asset bucket (S3 backend) or folder (local backend)
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


def _ensure_storage() -> None:
    import time
    from pathlib import Path

    from app.shared.storage import LocalStorage, S3Storage, get_storage

    storage = get_storage()
    if isinstance(storage, S3Storage):
        for attempt in range(30):  # the storage container may still be starting
            try:
                storage.ensure_bucket()
                break
            except Exception:  # noqa: BLE001
                if attempt == 29:
                    raise
                time.sleep(2)
        print(f"bucket {storage.bucket} ready")  # noqa: T201
    elif isinstance(storage, LocalStorage):
        Path(storage.root).mkdir(parents=True, exist_ok=True)
        print(f"local storage at {storage.root}")  # noqa: T201


def main() -> None:
    cmd, *args = sys.argv[1:] or ["help"]
    if cmd == "make-platform-admin" and args:
        asyncio.run(_make_admin(args[0]))
    elif cmd == "relay-outbox":
        asyncio.run(_relay())
    elif cmd == "sync-permissions":
        _sync()
    elif cmd == "ensure-storage":
        _ensure_storage()
    else:
        print(__doc__)  # noqa: T201


if __name__ == "__main__":
    main()
