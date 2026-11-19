import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Header, HTTPException, status

from app.core.config import settings

ph = PasswordHasher()


def hash_password(password: str) -> str:
    """Hash a plaintext password with argon2id."""
    return ph.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against an argon2 hash."""
    try:
        return ph.verify(hashed_password, plain_password)
    except (VerifyMismatchError, Exception):
        return False


def create_access_token(
    user_id: uuid.UUID,
    email: str,
    roles: list[str],
    department_id: uuid.UUID | None = None,
    approval_limit_aed: str | float | Decimal | None = None,
    expires_delta: timedelta | None = None,
) -> tuple[str, int]:
    """Create a signed HS256 JWT access token.

    Returns (token_str, expires_in_seconds).
    """
    now = datetime.now(timezone.utc)
    delta = expires_delta or timedelta(minutes=settings.JWT_TTL_MINUTES)
    expire = now + delta

    payload: dict[str, Any] = {
        "sub": str(user_id),
        "email": email,
        "roles": roles,
        "dept": str(department_id) if department_id else None,
        "iss": settings.JWT_ISSUER,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    if approval_limit_aed is not None:
        payload["approval_limit_aed"] = str(approval_limit_aed)

    token = jwt.encode(
        payload,
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )
    expires_in = int(delta.total_seconds())
    return token, expires_in


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT access token.

    Raises HTTPException with status 401 on any failure (expired, tampered, invalid issuer).
    """
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
            issuer=settings.JWT_ISSUER,
            options={"require": ["sub", "exp", "iss"]},
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidIssuerError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token issuer",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or tampered token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def extract_bearer_token(authorization: str | None = Header(None)) -> str:
    """Extract bearer token from Authorization header."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format. Expected 'Bearer <token>'",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return parts[1]
