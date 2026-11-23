"""/api/v1/auth — authentication endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request, Response, status

from app.core.config import get_settings
from app.core.errors import NotAuthenticated
from app.core.rate_limit import client_ip, hit, limiter
from app.modules.identity.api.deps import Auth, DbSession, Meta
from app.modules.identity.models import User
from app.modules.identity.repositories import SessionRepository
from app.modules.identity.schemas import (
    ChangePasswordRequest,
    EmailRequest,
    LoginRequest,
    MfaChallengeResponse,
    MfaCodeRequest,
    MfaDisableRequest,
    MfaLoginRequest,
    MfaSetupResponse,
    RecoveryCodesResponse,
    RegisterRequest,
    ResetPasswordRequest,
    SessionOut,
    TokenRequest,
    TokenResponse,
    UpdateProfileRequest,
    UserOut,
)
from app.modules.identity.services import IdentityService, IssuedTokens, MfaChallenge
from app.shared.schemas import Message

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_PATH = "/api/v1/auth"


def user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id, email=user.email, full_name=user.full_name, email_verified=user.email_verified,
        mfa_enabled=user.mfa_enabled, is_platform_admin=user.is_platform_admin, created_at=user.created_at,
    )


def _set_refresh_cookie(response: Response, tokens: IssuedTokens) -> TokenResponse:
    s = get_settings()
    response.set_cookie(
        s.refresh_cookie_name, tokens.refresh_token, max_age=s.refresh_token_ttl_days * 86400,
        httponly=True, secure=s.cookie_secure, samesite="strict", path=REFRESH_PATH, domain=s.cookie_domain,
    )
    return TokenResponse(access_token=tokens.access_token, expires_in=tokens.expires_in)


def _clear_refresh_cookie(response: Response) -> None:
    s = get_settings()
    response.delete_cookie(s.refresh_cookie_name, path=REFRESH_PATH, domain=s.cookie_domain,
                           secure=s.cookie_secure, httponly=True, samesite="strict")


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(limiter("register", limit=10, window_seconds=3600))])
async def register(body: RegisterRequest, response: Response, db: DbSession, meta: Meta) -> TokenResponse:
    _, tokens = await IdentityService(db, meta).register(
        email=body.email, password=body.password, full_name=body.full_name)
    return _set_refresh_cookie(response, tokens)


@router.post("/login", response_model=TokenResponse | MfaChallengeResponse,
             dependencies=[Depends(limiter("login_ip", limit=30, window_seconds=300))])
async def login(body: LoginRequest, response: Response, db: DbSession, meta: Meta):  # type: ignore[no-untyped-def]
    await hit("login_email", body.email.lower(), limit=10, window_seconds=300)
    result = await IdentityService(db, meta).login(email=body.email, password=body.password)
    if isinstance(result, MfaChallenge):
        return MfaChallengeResponse(mfa_token=result.mfa_token)
    return _set_refresh_cookie(response, result)


@router.post("/mfa/verify", response_model=TokenResponse,
             dependencies=[Depends(limiter("mfa_verify", limit=10, window_seconds=300))])
async def mfa_verify(body: MfaLoginRequest, response: Response, db: DbSession, meta: Meta) -> TokenResponse:
    tokens = await IdentityService(db, meta).complete_mfa_login(mfa_token=body.mfa_token, code=body.code)
    return _set_refresh_cookie(response, tokens)


@router.post("/refresh", response_model=TokenResponse,
             dependencies=[Depends(limiter("refresh", limit=60, window_seconds=60))])
async def refresh(request: Request, response: Response, db: DbSession, meta: Meta) -> TokenResponse:
    raw = request.cookies.get(get_settings().refresh_cookie_name)
    if not raw:
        raise NotAuthenticated("No active session", code="no_session")
    try:
        tokens = await IdentityService(db, meta).refresh(raw)
    except NotAuthenticated as exc:
        if exc.code != "refresh_conflict":
            _clear_refresh_cookie(response)
        raise
    return _set_refresh_cookie(response, tokens)


@router.post("/logout", response_model=Message)
async def logout(request: Request, response: Response, db: DbSession, meta: Meta) -> Message:
    raw = request.cookies.get(get_settings().refresh_cookie_name)
    if raw:
        try:
            sid, _ = IdentityService._parse_refresh(raw)
            await IdentityService(db, meta).logout(sid)
        except NotAuthenticated:
            pass
    _clear_refresh_cookie(response)
    return Message(message="Signed out")


@router.get("/me", response_model=UserOut)
async def me(auth: Auth) -> UserOut:
    return user_out(auth.user)


@router.patch("/me", response_model=UserOut)
async def update_me(body: UpdateProfileRequest, auth: Auth) -> UserOut:
    auth.user.full_name = body.full_name
    return user_out(auth.user)


@router.post("/verify-email", response_model=UserOut,
             dependencies=[Depends(limiter("verify_email", limit=20, window_seconds=600))])
async def verify_email(body: TokenRequest, db: DbSession, meta: Meta) -> UserOut:
    return user_out(await IdentityService(db, meta).verify_email(body.token))


@router.post("/resend-verification", response_model=Message)
async def resend_verification(auth: Auth, db: DbSession, meta: Meta, request: Request) -> Message:
    await hit("resend_verification", str(auth.user.id), limit=5, window_seconds=3600)
    await IdentityService(db, meta).resend_verification(auth.user)
    return Message(message="If your email is not yet verified, a new link has been sent")


@router.post("/forgot-password", response_model=Message, status_code=status.HTTP_202_ACCEPTED)
async def forgot_password(body: EmailRequest, db: DbSession, meta: Meta, request: Request) -> Message:
    await hit("forgot_ip", client_ip(request), limit=10, window_seconds=3600)
    await hit("forgot_email", body.email.lower(), limit=3, window_seconds=3600)
    await IdentityService(db, meta).forgot_password(body.email)
    return Message(message="If an account exists for this email, a reset link has been sent")


@router.post("/reset-password", response_model=Message,
             dependencies=[Depends(limiter("reset_password", limit=10, window_seconds=600))])
async def reset_password(body: ResetPasswordRequest, db: DbSession, meta: Meta) -> Message:
    await IdentityService(db, meta).reset_password(body.token, body.new_password)
    return Message(message="Password updated. Please sign in.")


@router.post("/change-password", response_model=Message)
async def change_password(body: ChangePasswordRequest, auth: Auth, db: DbSession, meta: Meta) -> Message:
    await hit("change_password", str(auth.user.id), limit=10, window_seconds=600)
    await IdentityService(db, meta).change_password(auth.user, auth.session_id, body.current_password,
                                                    body.new_password)
    return Message(message="Password changed. Other sessions were signed out.")


@router.post("/mfa/setup", response_model=MfaSetupResponse)
async def mfa_setup(auth: Auth, db: DbSession, meta: Meta) -> MfaSetupResponse:
    secret, uri = await IdentityService(db, meta).mfa_setup(auth.user)
    return MfaSetupResponse(secret=secret, otpauth_uri=uri)


@router.post("/mfa/enable", response_model=RecoveryCodesResponse)
async def mfa_enable(body: MfaCodeRequest, auth: Auth, db: DbSession, meta: Meta) -> RecoveryCodesResponse:
    await hit("mfa_enable", str(auth.user.id), limit=10, window_seconds=600)
    return RecoveryCodesResponse(recovery_codes=await IdentityService(db, meta).mfa_enable(auth.user, body.code))


@router.post("/mfa/disable", response_model=Message)
async def mfa_disable(body: MfaDisableRequest, auth: Auth, db: DbSession, meta: Meta) -> Message:
    await hit("mfa_disable", str(auth.user.id), limit=10, window_seconds=600)
    await IdentityService(db, meta).mfa_disable(auth.user, body.password, body.code)
    return Message(message="Two-factor authentication disabled")


@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(auth: Auth, db: DbSession) -> list[SessionOut]:
    rows = await SessionRepository(db).list_active(auth.user.id)
    return [SessionOut.model_validate(r).model_copy(update={"current": r.id == auth.session_id}) for r in rows]


@router.delete("/sessions/{session_id}", response_model=Message)
async def revoke_session(session_id: uuid.UUID, auth: Auth, db: DbSession, meta: Meta) -> Message:
    await IdentityService(db, meta).revoke_session(auth.user, session_id)
    return Message(message="Session revoked")
