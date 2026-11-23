"""Identity use cases: registration, login (with MFA), refresh rotation, email verification, password reset."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import timedelta

import structlog
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import run_in_independent_transaction, utcnow
from app.core.errors import AppError, Conflict, NotAuthenticated
from app.core.security import (
    create_access_token,
    decrypt_secret,
    encrypt_secret,
    generate_recovery_codes,
    generate_token,
    hash_password,
    hash_token,
    new_totp_secret,
    password_needs_rehash,
    totp_uri,
    verify_password,
    verify_totp,
)
from app.modules.identity.models import AuthToken, User, UserSession
from app.modules.identity.repositories import (
    RecoveryCodeRepository,
    SessionRepository,
    TokenRepository,
    UserRepository,
)
from app.shared.audit import RequestMeta, record_audit
from app.shared.outbox import enqueue_event

log = structlog.get_logger(__name__)

INVALID_CREDENTIALS = "Invalid email or password"
REFRESH_RACE_GRACE = timedelta(seconds=20)


@dataclass
class IssuedTokens:
    access_token: str
    expires_in: int
    refresh_token: str
    session_id: uuid.UUID


@dataclass
class MfaChallenge:
    mfa_token: str


def _mfa_aad(user_id: uuid.UUID) -> bytes:
    return f"mfa:{user_id}".encode()


class IdentityService:
    def __init__(self, session: AsyncSession, meta: RequestMeta | None = None):
        self.s = session
        self.meta = meta or RequestMeta()
        self.users = UserRepository(session)
        self.sessions = SessionRepository(session)
        self.tokens = TokenRepository(session)
        self.recovery = RecoveryCodeRepository(session)
        self.settings = get_settings()

    # --- registration & verification ----------------------------------------------------------------------

    async def register(self, *, email: str, password: str, full_name: str) -> tuple[User, IssuedTokens]:
        email = email.lower()
        if await self.users.get_by_email(email):
            raise Conflict("An account with this email already exists", code="email_taken")
        user = User(id=uuid.uuid4(), email=email, password_hash=hash_password(password), full_name=full_name,
                    password_changed_at=utcnow())
        self.users.add(user)
        await self.s.flush()
        await self._send_verification(user)
        await record_audit(self.s, action="user.registered", actor_user_id=user.id, resource_type="user",
                           resource_id=user.id, meta=self.meta)
        return user, await self._issue_session(user)

    async def _issue_token(self, user: User, purpose: str, ttl: timedelta) -> str:
        await self.tokens.invalidate(user.id, purpose)
        raw = generate_token()
        self.tokens.add(AuthToken(user_id=user.id, purpose=purpose, token_hash=hash_token(raw),
                                  expires_at=utcnow() + ttl))
        return raw

    async def _send_verification(self, user: User) -> None:
        raw = await self._issue_token(user, "email_verification",
                                      timedelta(hours=self.settings.email_verification_ttl_hours))
        enqueue_event(self.s, "identity.email_verification_requested", {
            "user_id": str(user.id), "email": user.email, "full_name": user.full_name,
            "link": f"{self.settings.frontend_url}/verify-email?token={raw}", "token": raw,
        })

    async def resend_verification(self, user: User) -> None:
        if user.email_verified:
            return
        await self._send_verification(user)

    async def verify_email(self, raw_token: str) -> User:
        token = await self.tokens.get_valid(hash_token(raw_token), "email_verification")
        if token is None:
            raise AppError("This verification link is invalid or has expired", code="invalid_token")
        token.consumed_at = utcnow()
        user = await self.users.get(token.user_id)
        assert user is not None
        user.email_verified_at = user.email_verified_at or utcnow()
        await record_audit(self.s, action="user.email_verified", actor_user_id=user.id, resource_type="user",
                           resource_id=user.id, meta=self.meta)
        return user

    # --- login ----------------------------------------------------------------------------------------------

    async def login(self, *, email: str, password: str) -> IssuedTokens | MfaChallenge:
        user = await self.users.get_by_email(email)
        now = utcnow()
        if user and user.locked_until and user.locked_until > now:
            # Same message as bad credentials: do not reveal that the account exists or is locked.
            raise NotAuthenticated(INVALID_CREDENTIALS, code="invalid_credentials")
        if not verify_password(password, user.password_hash if user else None) or user is None:
            if user is not None:
                await self._record_failed_login(user.id)
            raise NotAuthenticated(INVALID_CREDENTIALS, code="invalid_credentials")
        if user.status != "active":
            raise NotAuthenticated("This account is disabled", code="account_disabled")

        user.failed_login_count = 0
        user.locked_until = None
        if password_needs_rehash(user.password_hash or ""):
            user.password_hash = hash_password(password)

        if user.mfa_enabled:
            raw = await self._issue_token(user, "mfa_challenge",
                                          timedelta(minutes=self.settings.mfa_challenge_ttl_minutes))
            return MfaChallenge(mfa_token=raw)
        return await self._complete_login(user)

    async def _record_failed_login(self, user_id: uuid.UUID) -> None:
        s = self.settings
        meta = self.meta

        async def _bump(db: AsyncSession) -> None:
            user = await db.get(User, user_id, with_for_update=True)
            if user is None:
                return
            user.failed_login_count += 1
            if user.failed_login_count >= s.max_failed_logins:
                user.locked_until = utcnow() + timedelta(minutes=s.lockout_minutes)
                user.failed_login_count = 0
                await record_audit(db, action="user.locked_out", actor_user_id=user.id, resource_type="user",
                                   resource_id=user.id, meta=meta, actor_type="system")

        await run_in_independent_transaction(_bump)

    async def complete_mfa_login(self, *, mfa_token: str, code: str) -> IssuedTokens:
        token = await self.tokens.get_valid(hash_token(mfa_token), "mfa_challenge")
        if token is None:
            raise NotAuthenticated("The sign-in challenge has expired. Please sign in again.", code="mfa_expired")
        user = await self.users.get(token.user_id)
        assert user is not None
        if not await self._check_second_factor(user, code):
            await self._record_failed_login(user.id)
            raise NotAuthenticated("Invalid authentication code", code="invalid_mfa_code")
        token.consumed_at = utcnow()
        return await self._complete_login(user)

    async def _check_second_factor(self, user: User, code: str) -> bool:
        if not user.mfa_enabled or not user.mfa_secret_encrypted:
            return False
        secret = decrypt_secret(user.mfa_secret_encrypted, associated_data=_mfa_aad(user.id))
        if verify_totp(secret, code):
            return True
        return await self.recovery.consume(user.id, hash_token(code.strip().lower()))

    async def _complete_login(self, user: User) -> IssuedTokens:
        user.last_login_at = utcnow()
        tokens = await self._issue_session(user)
        await record_audit(self.s, action="user.login", actor_user_id=user.id, resource_type="session",
                           resource_id=tokens.session_id, meta=self.meta)
        return tokens

    async def _issue_session(self, user: User) -> IssuedTokens:
        secret = generate_token()
        sess = UserSession(
            id=uuid.uuid4(), user_id=user.id, refresh_token_hash=hash_token(secret),
            user_agent=(self.meta.user_agent or "")[:500] or None, ip_address=self.meta.ip_address,
            expires_at=utcnow() + timedelta(days=self.settings.refresh_token_ttl_days),
        )
        self.sessions.add(sess)
        await self.s.flush()
        access, ttl = create_access_token(user_id=user.id, session_id=sess.id)
        return IssuedTokens(access_token=access, expires_in=ttl, refresh_token=f"{sess.id}.{secret}",
                            session_id=sess.id)

    # --- refresh & logout -----------------------------------------------------------------------------------

    @staticmethod
    def _parse_refresh(refresh_token: str) -> tuple[uuid.UUID, str]:
        try:
            sid, secret = refresh_token.split(".", 1)
            return uuid.UUID(sid), secret
        except (ValueError, AttributeError):
            raise NotAuthenticated("Invalid session", code="invalid_refresh_token") from None

    async def refresh(self, refresh_token: str) -> IssuedTokens:
        sid, secret = self._parse_refresh(refresh_token)
        # Read without a row lock; rotation below is an atomic compare-and-swap on the current hash.
        sess = await self.sessions.get(sid)
        presented = hash_token(secret)
        if sess is None or sess.revoked_at is not None or sess.expires_at <= utcnow():
            raise NotAuthenticated("Session expired. Please sign in again.", code="session_expired")
        if presented != sess.refresh_token_hash:
            if presented == sess.previous_token_hash and utcnow() - sess.last_used_at < REFRESH_RACE_GRACE:
                # Two tabs refreshed at the same moment; the other one already rotated. Not an attack.
                raise NotAuthenticated("Session was just refreshed elsewhere; retry", code="refresh_conflict")
            if presented == sess.previous_token_hash:
                # A rotated token was replayed: assume theft and revoke the whole session (persisted even
                # though this request fails).
                await self._revoke_independently(sess.id, "refresh_reuse_detected")
                log.warning("refresh_token_reuse", session_id=str(sess.id))
            raise NotAuthenticated("Session expired. Please sign in again.", code="session_expired")
        user = await self.users.get(sess.user_id)
        if user is None or user.status != "active" or user.deleted_at is not None:
            raise NotAuthenticated("Account unavailable", code="account_disabled")
        new_secret = generate_token()
        rotated = await self.s.execute(
            update(UserSession)
            .where(UserSession.id == sess.id, UserSession.refresh_token_hash == presented,
                   UserSession.revoked_at.is_(None))
            .values(previous_token_hash=presented, refresh_token_hash=hash_token(new_secret), last_used_at=utcnow())
            .execution_options(synchronize_session=False)
        )
        if rotated.rowcount != 1:  # lost a race with a concurrent refresh of the same token
            raise NotAuthenticated("Session expired. Please sign in again.", code="session_expired")
        access, ttl = create_access_token(user_id=user.id, session_id=sess.id)
        return IssuedTokens(access_token=access, expires_in=ttl, refresh_token=f"{sess.id}.{new_secret}",
                            session_id=sess.id)

    async def _revoke_independently(self, session_id: uuid.UUID, reason: str) -> None:
        async def _revoke(db: AsyncSession) -> None:
            sess = await db.get(UserSession, session_id, with_for_update=True)
            if sess and sess.revoked_at is None:
                sess.revoked_at, sess.revoked_reason = utcnow(), reason
                await record_audit(db, action="session.revoked", actor_user_id=sess.user_id, actor_type="system",
                                   resource_type="session", resource_id=sess.id, metadata={"reason": reason})

        await run_in_independent_transaction(_revoke)

    async def logout(self, session_id: uuid.UUID) -> None:
        sess = await self.sessions.get_for_update(session_id)
        if sess and sess.revoked_at is None:
            sess.revoked_at, sess.revoked_reason = utcnow(), "logout"

    async def revoke_session(self, user: User, session_id: uuid.UUID) -> None:
        sess = await self.sessions.get_for_update(session_id)
        if sess is None or sess.user_id != user.id:
            from app.core.errors import NotFound

            raise NotFound("Session not found")
        if sess.revoked_at is None:
            sess.revoked_at, sess.revoked_reason = utcnow(), "revoked_by_user"
        await record_audit(self.s, action="session.revoked", actor_user_id=user.id, resource_type="session",
                           resource_id=session_id, meta=self.meta)

    # --- passwords ------------------------------------------------------------------------------------------

    async def forgot_password(self, email: str) -> None:
        """Always succeeds from the caller's view to avoid account enumeration."""
        user = await self.users.get_by_email(email)
        if user is None or user.status != "active":
            return
        raw = await self._issue_token(user, "password_reset",
                                      timedelta(minutes=self.settings.password_reset_ttl_minutes))
        enqueue_event(self.s, "identity.password_reset_requested", {
            "user_id": str(user.id), "email": user.email, "full_name": user.full_name,
            "link": f"{self.settings.frontend_url}/reset-password?token={raw}", "token": raw,
        })

    async def reset_password(self, raw_token: str, new_password: str) -> None:
        token = await self.tokens.get_valid(hash_token(raw_token), "password_reset")
        if token is None:
            raise AppError("This reset link is invalid or has expired", code="invalid_token")
        token.consumed_at = utcnow()
        user = await self.users.get(token.user_id)
        assert user is not None
        await self._set_password(user, new_password)
        # Proving control of the mailbox also verifies the email address.
        user.email_verified_at = user.email_verified_at or utcnow()
        user.failed_login_count, user.locked_until = 0, None
        await self.sessions.revoke_all(user.id, "password_reset")
        await record_audit(self.s, action="user.password_reset", actor_user_id=user.id, resource_type="user",
                           resource_id=user.id, meta=self.meta)

    async def change_password(self, user: User, current_session: uuid.UUID, current: str, new: str) -> None:
        if not verify_password(current, user.password_hash):
            raise AppError("Current password is incorrect", code="invalid_password")
        await self._set_password(user, new)
        await self.sessions.revoke_all(user.id, "password_changed", except_id=current_session)
        await record_audit(self.s, action="user.password_changed", actor_user_id=user.id, resource_type="user",
                           resource_id=user.id, meta=self.meta)

    async def _set_password(self, user: User, new_password: str) -> None:
        if user.email.split("@")[0] in new_password.lower() and len(user.email.split("@")[0]) >= 4:
            raise AppError("Password must not contain your email address", code="weak_password")
        user.password_hash = hash_password(new_password)
        user.password_changed_at = utcnow()

    # --- MFA ------------------------------------------------------------------------------------------------

    async def mfa_setup(self, user: User) -> tuple[str, str]:
        if user.mfa_enabled:
            raise Conflict("Two-factor authentication is already enabled", code="mfa_already_enabled")
        secret = new_totp_secret()
        user.mfa_secret_encrypted = encrypt_secret(secret, associated_data=_mfa_aad(user.id))
        return secret, totp_uri(secret, user.email)

    async def mfa_enable(self, user: User, code: str) -> list[str]:
        if user.mfa_enabled:
            raise Conflict("Two-factor authentication is already enabled", code="mfa_already_enabled")
        if not user.mfa_secret_encrypted:
            raise AppError("Start two-factor setup first", code="mfa_not_setup")
        secret = decrypt_secret(user.mfa_secret_encrypted, associated_data=_mfa_aad(user.id))
        if not verify_totp(secret, code):
            raise AppError("Invalid authentication code", code="invalid_mfa_code")
        user.mfa_enabled = True
        codes = generate_recovery_codes()
        await self.recovery.replace(user.id, [hash_token(c) for c in codes])
        await record_audit(self.s, action="user.mfa_enabled", actor_user_id=user.id, resource_type="user",
                           resource_id=user.id, meta=self.meta)
        return codes

    async def mfa_disable(self, user: User, password: str, code: str) -> None:
        if not user.mfa_enabled:
            return
        if not verify_password(password, user.password_hash) or not await self._check_second_factor(user, code):
            raise AppError("Password or authentication code is incorrect", code="invalid_credentials")
        user.mfa_enabled = False
        user.mfa_secret_encrypted = None
        await self.recovery.replace(user.id, [])
        await record_audit(self.s, action="user.mfa_disabled", actor_user_id=user.id, resource_type="user",
                           resource_id=user.id, meta=self.meta)
