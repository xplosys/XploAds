from __future__ import annotations

from app.core.security import decrypt_secret, encrypt_secret, hash_password, verify_password
from app.shared import notifications
from app.shared.outbox import relay_batch
from tests.conftest import owner_query, register


def test_envelope_encryption_roundtrip_and_aad_binding():
    blob = encrypt_secret("sk-test-123", associated_data=b"tenant:1")
    assert b"sk-test-123" not in blob
    assert decrypt_secret(blob, associated_data=b"tenant:1") == "sk-test-123"
    import pytest
    from cryptography.exceptions import InvalidTag

    with pytest.raises(InvalidTag):
        decrypt_secret(blob, associated_data=b"tenant:2")


def test_password_hashing():
    h = hash_password("correct horse battery")
    assert verify_password("correct horse battery", h)
    assert not verify_password("wrong", h)
    assert not verify_password("anything", None)


async def test_outbox_relay_sends_email_and_purges_token(client):
    import app.workers.handlers  # noqa: F401
    from app.core.database import get_sessionmaker

    notifications.console_outbox.clear()
    u = await register(client, verify=False)
    delivered = await relay_batch(get_sessionmaker())
    assert delivered >= 1
    mail = [m for m in notifications.console_outbox if m.to == u["email"]]
    assert mail and "/verify-email?token=" in mail[0].text
    rows = owner_query("SELECT status, payload ? 'token', payload ? 'link' FROM outbox_events "
                       "WHERE payload->>'email' = %s", u["email"])
    assert rows == [("done", False, False)]


async def test_outbox_retries_then_dead_letters():
    from app.core.database import get_sessionmaker
    from app.shared import outbox

    calls = {"n": 0}

    @outbox.handles("test.always_fails")
    async def _boom(event):  # noqa: ANN001
        calls["n"] += 1
        raise RuntimeError("provider down")

    async with get_sessionmaker()() as s, s.begin():
        outbox.enqueue_event(s, "test.always_fails", {"x": 1})
    for _ in range(outbox.MAX_ATTEMPTS):
        owner_query("UPDATE outbox_events SET available_at = now() - interval '1 second' WHERE status = 'pending'")
        await relay_batch(get_sessionmaker())
    (status, attempts, err) = owner_query(
        "SELECT status, attempts, last_error FROM outbox_events WHERE event_type = 'test.always_fails'")[0]
    assert status == "dead" and attempts == outbox.MAX_ATTEMPTS and "provider down" in err


async def test_health_and_error_envelope(client):
    assert (await client.get("/health/live")).json() == {"status": "ok"}
    ready = await client.get("/health/ready")
    assert ready.status_code == 200 and ready.json()["checks"] == {"database": "ok", "redis": "ok"}
    r = await client.get("/api/v1/organizations")
    body = r.json()
    assert r.status_code == 401 and set(body["error"]) == {"code", "message", "request_id", "details"}
    assert r.headers["x-request-id"] == body["error"]["request_id"]


def test_production_refuses_dev_defaults(monkeypatch):
    from app.core.config import Settings

    s = Settings(environment="production")
    try:
        s.assert_safe_for_environment()
    except RuntimeError as e:
        assert "DATA_ENCRYPTION_KEY" in str(e) and "COOKIE_SECURE" in str(e)
    else:
        raise AssertionError("expected unsafe production config to be refused")
