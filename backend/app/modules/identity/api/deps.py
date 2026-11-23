"""Authentication dependencies (public interface for other modules)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import session_scope, set_rls_context, utcnow
from app.core.errors import NotAuthenticated, PermissionDenied
from app.core.rate_limit import client_ip
from app.core.security import decode_access_token
from app.modules.identity.models import User, UserSession
from app.shared.audit import RequestMeta

DbSession = Annotated[AsyncSession, Depends(session_scope)]


def request_meta(request: Request) -> RequestMeta:
    return RequestMeta(
        request_id=getattr(request.state, "request_id", None),
        ip_address=client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )


Meta = Annotated[RequestMeta, Depends(request_meta)]


@dataclass
class AuthContext:
    user: User
    session_id: uuid.UUID


async def get_auth(request: Request, db: DbSession) -> AuthContext:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise NotAuthenticated("Authentication required")
    try:
        claims = decode_access_token(token)
        user_id, session_id = uuid.UUID(claims["sub"]), uuid.UUID(claims["sid"])
    except (jwt.PyJWTError, ValueError, KeyError):
        raise NotAuthenticated("Invalid or expired access token", code="invalid_token") from None

    sess = await db.get(UserSession, session_id)
    if sess is None or sess.user_id != user_id or sess.revoked_at is not None or sess.expires_at <= utcnow():
        raise NotAuthenticated("Session has ended", code="session_expired")
    user = await db.get(User, user_id)
    if user is None or user.status != "active" or user.deleted_at is not None:
        raise NotAuthenticated("Account unavailable", code="account_disabled")

    await set_rls_context(db, user_id=user.id)
    request.state.user_id = str(user.id)
    return AuthContext(user=user, session_id=session_id)


Auth = Annotated[AuthContext, Depends(get_auth)]


async def require_verified_email(auth: Auth) -> AuthContext:
    if not auth.user.email_verified:
        raise PermissionDenied("Please verify your email address first", code="email_not_verified")
    return auth


VerifiedAuth = Annotated[AuthContext, Depends(require_verified_email)]


async def require_platform_admin(auth: Auth) -> AuthContext:
    if not auth.user.is_platform_admin:
        raise PermissionDenied("Platform administrator access required")
    return auth
