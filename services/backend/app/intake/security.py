"""Authentication, constant-time key verification, and principal resolution for intake."""

from __future__ import annotations

import hashlib
import hmac
import uuid
from decimal import Decimal

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.errors import ProblemException
from app.core.models import User, UserRole
from app.core.policy import Principal

_hasher = PasswordHasher()
INTAKE_SERVICE_EMAIL = "intake@demo-holdings.example"


def hash_intake_key(plain_key: str) -> str:
    """Hash plaintext key with argon2id."""
    return _hasher.hash(plain_key)


def verify_intake_key(plain_key: str, key_hash: str) -> bool:
    """Verify intake key against stored hash in constant time."""
    if not plain_key or not key_hash:
        return False

    key_hash = key_hash.strip()

    # 1. Argon2 hash
    if key_hash.startswith("$argon2"):
        try:
            return _hasher.verify(key_hash, plain_key)
        except (VerifyMismatchError, Exception):
            return False

    # 2. SHA-256 with optional prefix
    candidate_hash = key_hash
    if candidate_hash.startswith("sha256:"):
        candidate_hash = candidate_hash[7:]

    computed = hashlib.sha256(plain_key.encode("utf-8")).hexdigest()
    return hmac.compare_digest(computed.lower(), candidate_hash.lower())


def get_intake_principal(
    x_intake_key: str | None = Header(None, alias="X-Intake-Key"),
    db: Session = Depends(get_db),
) -> Principal:
    """Authenticate intake request strictly via X-Intake-Key header."""
    if not x_intake_key:
        raise ProblemException(
            status_code=401,
            code="MISSING_INTAKE_KEY",
            title="Unauthorized",
            detail="Missing X-Intake-Key header",
        )

    configured_hash = settings.INTAKE_KEY_HASH
    if not configured_hash:
        raise ProblemException(
            status_code=401,
            code="INTAKE_KEY_NOT_CONFIGURED",
            title="Unauthorized",
            detail="Intake authentication key is not configured on the server",
        )

    if not verify_intake_key(x_intake_key, configured_hash):
        raise ProblemException(
            status_code=401,
            code="INVALID_INTAKE_KEY",
            title="Unauthorized",
            detail="Invalid intake API key",
        )

    # Resolve or provision intake service account user
    user = db.query(User).filter(User.email == INTAKE_SERVICE_EMAIL).first()
    if not user:
        user = User(
            id=uuid.uuid4(),
            email=INTAKE_SERVICE_EMAIL,
            display_name="Intake Service Account",
            approval_limit_aed=Decimal("0.00"),
            is_demo=True,
            active=True,
            password_hash=None,  # Service account only, no password login
        )
        db.add(user)
        db.flush()
        db.add(UserRole(user_id=user.id, role="intake"))
        db.flush()

    return Principal(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        roles=["intake"],
        department_id=None,
        department_name=None,
        approval_limit_aed=Decimal("0.00"),
        is_demo=True,
        active=True,
    )
