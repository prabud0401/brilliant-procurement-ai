import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.security import create_access_token
from app.main import app


@pytest.mark.security
def test_missing_token_returns_401() -> None:
    client = TestClient(app)
    response = client.get("/api/v1/me")
    assert response.status_code == 401
    data = response.json()
    assert data["code"] == "UNAUTHORIZED"
    assert "Authorization" in data["detail"]


@pytest.mark.security
def test_garbage_token_returns_401() -> None:
    client = TestClient(app)
    response = client.get("/api/v1/me", headers={"Authorization": "Bearer not-a-valid-jwt-token"})
    assert response.status_code == 401
    data = response.json()
    assert data["code"] == "UNAUTHORIZED"


@pytest.mark.security
def test_expired_jwt_returns_401() -> None:
    user_id = uuid.uuid4()
    expired_token, _ = create_access_token(
        user_id=user_id,
        email="test@example.com",
        roles=["requester"],
        expires_delta=timedelta(seconds=-10),  # expired 10s ago
    )

    client = TestClient(app)
    response = client.get("/api/v1/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert response.status_code == 401
    data = response.json()
    assert data["code"] == "UNAUTHORIZED"
    assert "expired" in data["detail"].lower()


@pytest.mark.security
def test_tampered_jwt_returns_401() -> None:
    user_id = uuid.uuid4()
    valid_token, _ = create_access_token(
        user_id=user_id,
        email="test@example.com",
        roles=["requester"],
    )

    # Tamper with the signature (last part of JWT)
    parts = valid_token.split(".")
    tampered_sig = parts[2][:-4] + "AAAA"
    tampered_token = f"{parts[0]}.{parts[1]}.{tampered_sig}"

    client = TestClient(app)
    response = client.get("/api/v1/me", headers={"Authorization": f"Bearer {tampered_token}"})
    assert response.status_code == 401
    data = response.json()
    assert data["code"] == "UNAUTHORIZED"


@pytest.mark.security
def test_wrong_issuer_jwt_returns_401() -> None:
    user_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "email": "test@example.com",
        "roles": ["requester"],
        "iss": "rogue-issuer-not-pda",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=15)).timestamp()),
    }
    rogue_token = jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")

    client = TestClient(app)
    response = client.get("/api/v1/me", headers={"Authorization": f"Bearer {rogue_token}"})
    assert response.status_code == 401
    data = response.json()
    assert data["code"] == "UNAUTHORIZED"
    assert "issuer" in data["detail"].lower()
