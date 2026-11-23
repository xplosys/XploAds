"""Persistence for identity tables. Only the identity module writes these tables."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import utcnow
from app.modules.identity.models import AuthToken, MfaRecoveryCode, User, UserSession


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def get(self, user_id: uuid.UUID) -> User | None:
        return await self.s.get(User, user_id)

    async def get_by_email(self, email: str, *, for_update: bool = False) -> User | None:
        q = select(User).where(User.email == email.lower(), User.deleted_at.is_(None))
        if for_update:
            q = q.with_for_update()
        return (await self.s.execute(q)).scalar_one_or_none()

    async def get_many(self, ids: list[uuid.UUID]) -> dict[uuid.UUID, User]:
        if not ids:
            return {}
        rows = (await self.s.execute(select(User).where(User.id.in_(ids)))).scalars()
        return {u.id: u for u in rows}

    def add(self, user: User) -> None:
        self.s.add(user)


class SessionRepository:
    def __init__(self, session: AsyncSession):
        self.s = session

    def add(self, sess: UserSession) -> None:
        self.s.add(sess)

    async def get_for_update(self, session_id: uuid.UUID) -> UserSession | None:
        q = select(UserSession).where(UserSession.id == session_id).with_for_update()
        return (await self.s.execute(q)).scalar_one_or_none()

    async def get(self, session_id: uuid.UUID) -> UserSession | None:
        return await self.s.get(UserSession, session_id)

    async def list_active(self, user_id: uuid.UUID) -> list[UserSession]:
        q = (
            select(UserSession)
            .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None),
                   UserSession.expires_at > utcnow())
            .order_by(UserSession.last_used_at.desc())
        )
        return list((await self.s.execute(q)).scalars())

    async def revoke_all(self, user_id: uuid.UUID, reason: str, *, except_id: uuid.UUID | None = None) -> None:
        q = update(UserSession).where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
        if except_id:
            q = q.where(UserSession.id != except_id)
        await self.s.execute(q.values(revoked_at=utcnow(), revoked_reason=reason))


class TokenRepository:
    def __init__(self, session: AsyncSession):
        self.s = session

    def add(self, token: AuthToken) -> None:
        self.s.add(token)

    async def get_valid(self, token_hash: str, purpose: str) -> AuthToken | None:
        q = (
            select(AuthToken)
            .where(AuthToken.token_hash == token_hash, AuthToken.purpose == purpose,
                   AuthToken.consumed_at.is_(None), AuthToken.expires_at > utcnow())
            .with_for_update()
        )
        return (await self.s.execute(q)).scalar_one_or_none()

    async def invalidate(self, user_id: uuid.UUID, purpose: str, at: datetime | None = None) -> None:
        await self.s.execute(
            update(AuthToken)
            .where(AuthToken.user_id == user_id, AuthToken.purpose == purpose, AuthToken.consumed_at.is_(None))
            .values(consumed_at=at or utcnow())
        )


class RecoveryCodeRepository:
    def __init__(self, session: AsyncSession):
        self.s = session

    async def replace(self, user_id: uuid.UUID, hashes: list[str]) -> None:
        await self.s.execute(
            update(MfaRecoveryCode).where(MfaRecoveryCode.user_id == user_id, MfaRecoveryCode.used_at.is_(None))
            .values(used_at=utcnow())
        )
        for h in hashes:
            self.s.add(MfaRecoveryCode(user_id=user_id, code_hash=h))

    async def consume(self, user_id: uuid.UUID, code_hash: str) -> bool:
        q = (
            select(MfaRecoveryCode)
            .where(MfaRecoveryCode.user_id == user_id, MfaRecoveryCode.code_hash == code_hash,
                   MfaRecoveryCode.used_at.is_(None))
            .with_for_update()
        )
        code = (await self.s.execute(q)).scalar_one_or_none()
        if code is None:
            return False
        code.used_at = utcnow()
        return True
