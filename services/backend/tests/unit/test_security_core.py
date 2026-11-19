import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from pydantic_core import ValidationError

from app.core.config import Settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


@pytest.mark.unit
def test_argon2_password_hashing() -> None:
    password = "SuperSecretPassword123!"
    pw_hash = hash_password(password)

    assert pw_hash.startswith("$argon2id$")
    assert verify_password(password, pw_hash) is True
    assert verify_password("WrongPassword!", pw_hash) is False


@pytest.mark.unit
def test_jwt_creation_and_payload_claims() -> None:
    user_id = uuid.uuid4()
    dept_id = uuid.uuid4()

    token, expires_in = create_access_token(
        user_id=user_id,
        email="buyer@demo-holdings.example",
        roles=["buyer"],
        department_id=dept_id,
        approval_limit_aed=Decimal("150000.00"),
        expires_delta=timedelta(minutes=15),
    )

    assert isinstance(token, str)
    assert expires_in == 900

    payload = decode_access_token(token)
    assert payload["sub"] == str(user_id)
    assert payload["email"] == "buyer@demo-holdings.example"
    assert payload["roles"] == ["buyer"]
    assert payload["dept"] == str(dept_id)
    assert payload["approval_limit_aed"] == "150000.00"
    assert payload["iss"] == "brilliant-procurement-ai"


@pytest.mark.unit
def test_jwt_secret_requires_minimum_32_characters() -> None:
    # Less than 32 chars should fail validation
    with pytest.raises(ValidationError) as exc:
        Settings(JWT_SECRET="too-short-secret")
    assert "at least 32 characters" in str(exc.value)

    # 32 or more chars should succeed
    valid_settings = Settings(JWT_SECRET="valid-secret-with-at-least-32-chars-long")
    assert valid_settings.JWT_SECRET == "valid-secret-with-at-least-32-chars-long"
