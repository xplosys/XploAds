from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import EmailStr, Field, field_validator

from app.shared.schemas import APIModel

PASSWORD_MIN, PASSWORD_MAX = 10, 128


def _check_password(v: str) -> str:
    if len(v) < PASSWORD_MIN:
        raise ValueError(f"Password must be at least {PASSWORD_MIN} characters")
    if len(set(v)) < 4:
        raise ValueError("Password is too simple")
    return v


class RegisterRequest(APIModel):
    email: EmailStr
    password: str = Field(max_length=PASSWORD_MAX)
    full_name: str = Field(min_length=1, max_length=200)

    _pw = field_validator("password")(_check_password)


class LoginRequest(APIModel):
    email: EmailStr
    password: str = Field(max_length=PASSWORD_MAX)


class MfaLoginRequest(APIModel):
    mfa_token: str = Field(max_length=200)
    code: str = Field(min_length=6, max_length=20, description="6-digit TOTP code or a recovery code")


class TokenResponse(APIModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105
    expires_in: int
    mfa_required: bool = False


class MfaChallengeResponse(APIModel):
    mfa_required: bool = True
    mfa_token: str


class UserOut(APIModel):
    id: uuid.UUID
    email: str
    full_name: str
    email_verified: bool
    mfa_enabled: bool
    is_platform_admin: bool
    created_at: datetime


class UpdateProfileRequest(APIModel):
    full_name: str = Field(min_length=1, max_length=200)


class TokenRequest(APIModel):
    token: str = Field(min_length=10, max_length=300)


class EmailRequest(APIModel):
    email: EmailStr


class ResetPasswordRequest(APIModel):
    token: str = Field(min_length=10, max_length=300)
    new_password: str = Field(max_length=PASSWORD_MAX)

    _pw = field_validator("new_password")(_check_password)


class ChangePasswordRequest(APIModel):
    current_password: str = Field(max_length=PASSWORD_MAX)
    new_password: str = Field(max_length=PASSWORD_MAX)

    _pw = field_validator("new_password")(_check_password)


class MfaSetupResponse(APIModel):
    secret: str
    otpauth_uri: str


class MfaCodeRequest(APIModel):
    code: str = Field(min_length=6, max_length=10)


class MfaDisableRequest(APIModel):
    password: str = Field(max_length=PASSWORD_MAX)
    code: str = Field(min_length=6, max_length=20)


class RecoveryCodesResponse(APIModel):
    recovery_codes: list[str]


class SessionOut(APIModel):
    id: uuid.UUID
    user_agent: str | None
    ip_address: str | None
    created_at: datetime
    last_used_at: datetime
    expires_at: datetime
    current: bool = False
