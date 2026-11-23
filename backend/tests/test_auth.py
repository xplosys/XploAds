from __future__ import annotations

import pyotp

from app.core.database import utcnow
from tests.conftest import PASSWORD, latest_event_token, owner_query, register, unique_email


async def test_register_returns_session_and_requires_verification(client):
    email = unique_email()
    r = await client.post("/api/v1/auth/register", json={"email": email.upper(), "password": PASSWORD,
                                                          "full_name": "Asha"})
    assert r.status_code == 201
    assert "xploads_refresh" in r.headers.get("set-cookie", "")
    assert "HttpOnly" in r.headers["set-cookie"] and "SameSite=strict" in r.headers["set-cookie"]
    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"})
    assert me.json()["email"] == email.lower()
    assert me.json()["email_verified"] is False
    # password hash is argon2id, never plaintext
    (h,) = owner_query("SELECT password_hash FROM users WHERE email = %s", email.lower())[0]
    assert h.startswith("$argon2id$") and PASSWORD not in h


async def test_duplicate_email_rejected(client):
    u = await register(client)
    r = await client.post("/api/v1/auth/register", json={"email": u["email"], "password": PASSWORD,
                                                          "full_name": "X"})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "email_taken"


async def test_weak_password_rejected(client):
    r = await client.post("/api/v1/auth/register", json={"email": unique_email(), "password": "short",
                                                          "full_name": "X"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


async def test_email_verification_token_single_use(client):
    email = unique_email()
    await client.post("/api/v1/auth/register", json={"email": email, "password": PASSWORD, "full_name": "X"})
    token = latest_event_token("identity.email_verification_requested", email)
    assert (await client.post("/api/v1/auth/verify-email", json={"token": token})).status_code == 200
    again = await client.post("/api/v1/auth/verify-email", json={"token": token})
    assert again.status_code == 400 and again.json()["error"]["code"] == "invalid_token"


async def test_login_wrong_password_and_unknown_user_look_identical(client):
    u = await register(client)
    bad = await client.post("/api/v1/auth/login", json={"email": u["email"], "password": "wrong-password-1"})
    unknown = await client.post("/api/v1/auth/login", json={"email": unique_email(), "password": "whatever-123"})
    assert bad.status_code == unknown.status_code == 401
    assert bad.json()["error"]["message"] == unknown.json()["error"]["message"]


async def test_lockout_after_repeated_failures(client):
    u = await register(client)
    for _ in range(10):
        await client.post("/api/v1/auth/login", json={"email": u["email"], "password": "wrong-password-1"})
    (locked,) = owner_query("SELECT locked_until FROM users WHERE email = %s", u["email"])[0]
    assert locked is not None and locked > utcnow()
    r = await client.post("/api/v1/auth/login", json={"email": u["email"], "password": PASSWORD})
    assert r.status_code == 401  # correct password still refused while locked


async def test_refresh_rotation_and_reuse_detection(client):
    u = await register(client)
    old_cookie = client.cookies.get("xploads_refresh")
    r1 = await client.post("/api/v1/auth/refresh")
    assert r1.status_code == 200
    new_cookie = client.cookies.get("xploads_refresh")
    assert new_cookie and new_cookie != old_cookie
    # A replay within the grace window (two tabs racing) is refused but does not revoke the session.
    client.cookies.clear()
    client.cookies.set("xploads_refresh", old_cookie, path="/api/v1/auth")
    race = await client.post("/api/v1/auth/refresh")
    assert race.status_code == 401 and race.json()["error"]["code"] == "refresh_conflict"
    assert (await client.get("/api/v1/auth/me", headers=u["headers"])).status_code == 200
    # Replaying the rotated (old) token later revokes the session entirely.
    owner_query("UPDATE sessions SET last_used_at = now() - interval '5 minutes'")
    client.cookies.clear()
    client.cookies.set("xploads_refresh", old_cookie, path="/api/v1/auth")
    replay = await client.post("/api/v1/auth/refresh")
    assert replay.status_code == 401 and replay.json()["error"]["code"] == "session_expired"
    client.cookies.clear()
    client.cookies.set("xploads_refresh", new_cookie, path="/api/v1/auth")
    assert (await client.post("/api/v1/auth/refresh")).status_code == 401
    # ...and the access token bound to that session stops working too.
    me = await client.get("/api/v1/auth/me", headers=u["headers"])
    assert me.status_code == 401


async def test_logout_revokes_session(client):
    u = await register(client)
    assert (await client.post("/api/v1/auth/logout")).status_code == 200
    assert (await client.get("/api/v1/auth/me", headers=u["headers"])).status_code == 401


async def test_password_reset_flow_revokes_sessions(client):
    u = await register(client)
    r = await client.post("/api/v1/auth/forgot-password", json={"email": u["email"]})
    assert r.status_code == 202
    # unknown emails get the same answer (no enumeration)
    r2 = await client.post("/api/v1/auth/forgot-password", json={"email": unique_email()})
    assert r2.status_code == 202 and r2.json() == r.json()
    token = latest_event_token("identity.password_reset_requested", u["email"])
    new_pw = "Brand-New-Passw0rd"
    assert (await client.post("/api/v1/auth/reset-password",
                              json={"token": token, "new_password": new_pw})).status_code == 200
    assert (await client.get("/api/v1/auth/me", headers=u["headers"])).status_code == 401
    ok = await client.post("/api/v1/auth/login", json={"email": u["email"], "password": new_pw})
    assert ok.status_code == 200 and ok.json()["access_token"]


async def test_mfa_enable_and_login_challenge(client):
    u = await register(client)
    setup = await client.post("/api/v1/auth/mfa/setup", headers=u["headers"])
    secret = setup.json()["secret"]
    assert setup.json()["otpauth_uri"].startswith("otpauth://totp/")
    (enc,) = owner_query("SELECT mfa_secret_encrypted FROM users WHERE email = %s", u["email"])[0]
    assert secret.encode() not in bytes(enc)  # stored encrypted
    bad = await client.post("/api/v1/auth/mfa/enable", json={"code": "000000"}, headers=u["headers"])
    assert bad.status_code == 400
    en = await client.post("/api/v1/auth/mfa/enable", json={"code": pyotp.TOTP(secret).now()}, headers=u["headers"])
    assert en.status_code == 200
    codes = en.json()["recovery_codes"]
    assert len(codes) == 10

    login = await client.post("/api/v1/auth/login", json={"email": u["email"], "password": PASSWORD})
    assert login.json()["mfa_required"] is True and "access_token" not in login.json()
    mfa_token = login.json()["mfa_token"]
    wrong = await client.post("/api/v1/auth/mfa/verify", json={"mfa_token": mfa_token, "code": "123456"})
    assert wrong.status_code == 401
    ok = await client.post("/api/v1/auth/mfa/verify", json={"mfa_token": mfa_token, "code": pyotp.TOTP(secret).now()})
    assert ok.status_code == 200 and ok.json()["access_token"]
    # challenge token is single-use
    again = await client.post("/api/v1/auth/mfa/verify",
                              json={"mfa_token": mfa_token, "code": pyotp.TOTP(secret).now()})
    assert again.status_code == 401

    # recovery code works once
    login2 = await client.post("/api/v1/auth/login", json={"email": u["email"], "password": PASSWORD})
    rc = await client.post("/api/v1/auth/mfa/verify", json={"mfa_token": login2.json()["mfa_token"], "code": codes[0]})
    assert rc.status_code == 200
    login3 = await client.post("/api/v1/auth/login", json={"email": u["email"], "password": PASSWORD})
    rc2 = await client.post("/api/v1/auth/mfa/verify", json={"mfa_token": login3.json()["mfa_token"], "code": codes[0]})
    assert rc2.status_code == 401


async def test_change_password_keeps_current_session_only(client):
    u = await register(client)
    other = await client.post("/api/v1/auth/login", json={"email": u["email"], "password": PASSWORD})
    other_headers = {"Authorization": f"Bearer {other.json()['access_token']}"}
    r = await client.post("/api/v1/auth/change-password", headers=u["headers"],
                          json={"current_password": PASSWORD, "new_password": "Another-Passw0rd!"})
    assert r.status_code == 200
    assert (await client.get("/api/v1/auth/me", headers=u["headers"])).status_code == 200
    assert (await client.get("/api/v1/auth/me", headers=other_headers)).status_code == 401


async def test_sessions_listing_and_revocation(client):
    u = await register(client)
    await client.post("/api/v1/auth/login", json={"email": u["email"], "password": PASSWORD})
    sessions = (await client.get("/api/v1/auth/sessions", headers=u["headers"])).json()
    assert len(sessions) == 2 and sum(s["current"] for s in sessions) == 1
    other = next(s for s in sessions if not s["current"])
    assert (await client.delete(f"/api/v1/auth/sessions/{other['id']}", headers=u["headers"])).status_code == 200
    assert len((await client.get("/api/v1/auth/sessions", headers=u["headers"])).json()) == 1


async def test_tampered_access_token_rejected(client):
    u = await register(client)
    tampered = u["token"][:-4] + ("AAAA" if not u["token"].endswith("AAAA") else "BBBB")
    r = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tampered}"})
    assert r.status_code == 401
    assert (await client.get("/api/v1/auth/me")).status_code == 401
