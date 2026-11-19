"""Microsoft Entra ID identity adapter and mock implementation."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from app.integrations.base import NotConfiguredError


class EntraUser(BaseModel):
    """User profile as represented in Microsoft Entra ID."""

    oid: str
    email: str
    display_name: str
    roles: list[str] = Field(default_factory=list)
    department: str = ""
    approval_limit_aed: Decimal | None = None
    tid: str = "tenant-demo-holdings-0000-0000"


@runtime_checkable
class IdentityAdapter(Protocol):
    """Protocol contract for Microsoft Entra ID identity service."""

    @property
    def name(self) -> str:
        """Adapter display name."""
        ...

    def get_user_by_email(self, email: str) -> EntraUser | None:
        """Map email to Entra profile including external_oid."""
        ...

    def get_user_by_oid(self, oid: str) -> EntraUser | None:
        """Find Entra profile by object ID."""
        ...

    def map_email_to_oid(self, email: str) -> str | None:
        """Helper to quickly resolve email -> external_oid."""
        ...

    def validate_token(self, token: str) -> dict[str, Any]:
        """Validate access token and return token claims."""
        ...


class IdentityMockAdapter:
    """Mock identity adapter providing simulated Entra ID user directory and token decoding."""

    def __init__(self) -> None:
        self._users_by_email: dict[str, EntraUser] = {}
        self._users_by_oid: dict[str, EntraUser] = {}
        self._seed_default_users()

    def _seed_default_users(self) -> None:
        defaults = [
            EntraUser(
                oid="11111111-1111-1111-1111-111111111111",
                email="requester@demo-holdings.fake",
                display_name="Ahmed Al Mansoori (Demo Requester)",
                roles=["Procurement.Requester"],
                department="IT",
            ),
            EntraUser(
                oid="22222222-2222-2222-2222-222222222222",
                email="buyer@demo-holdings.fake",
                display_name="Sara Al Zaabi (Demo Buyer)",
                roles=["Procurement.Buyer"],
                department="IT",
            ),
            EntraUser(
                oid="33333333-3333-3333-3333-333333333331",
                email="manager.facilities@demo-holdings.fake",
                display_name="Khalid Al Hashimi (Facilities Manager)",
                roles=["Procurement.Manager"],
                department="Facilities",
                approval_limit_aed=Decimal("50000.00"),
            ),
            EntraUser(
                oid="33333333-3333-3333-3333-333333333332",
                email="manager.it@demo-holdings.fake",
                display_name="Fatima Al Nuaimi (IT Manager)",
                roles=["Procurement.Manager"],
                department="IT",
                approval_limit_aed=Decimal("50000.00"),
            ),
            EntraUser(
                oid="33333333-3333-3333-3333-333333333333",
                email="manager.projects@demo-holdings.fake",
                display_name="Tariq Al Suwaidi (Projects Director)",
                roles=["Procurement.Manager"],
                department="Projects",
                approval_limit_aed=Decimal("250000.00"),
            ),
            EntraUser(
                oid="44444444-4444-4444-4444-444444444444",
                email="admin@demo-holdings.fake",
                display_name="Admin User (System Administrator)",
                roles=["Procurement.Admin"],
                department="IT",
            ),
        ]
        for u in defaults:
            self._users_by_email[u.email.lower()] = u
            self._users_by_oid[u.oid] = u

    @property
    def name(self) -> str:
        return "Microsoft Entra ID (mock adapter)"

    def get_user_by_email(self, email: str) -> EntraUser | None:
        cleaned = email.strip().lower()
        if cleaned in self._users_by_email:
            return self._users_by_email[cleaned]

        # Generate deterministic synthetic user profile for arbitrary test email
        generated_oid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"entra:{cleaned}"))
        synthetic_user = EntraUser(
            oid=generated_oid,
            email=cleaned,
            display_name=f"Demo User ({cleaned.split('@')[0]})",
            roles=["Procurement.Requester"],
            department="IT",
        )
        self._users_by_email[cleaned] = synthetic_user
        self._users_by_oid[generated_oid] = synthetic_user
        return synthetic_user

    def get_user_by_oid(self, oid: str) -> EntraUser | None:
        return self._users_by_oid.get(oid)

    def map_email_to_oid(self, email: str) -> str | None:
        user = self.get_user_by_email(email)
        return user.oid if user else None

    def validate_token(self, token: str) -> dict[str, Any]:
        """Validate mock token string and return decoded claims."""
        if not token or not isinstance(token, str):
            raise ValueError("Token cannot be empty")

        # Allow simple "mock:<email>" token format or standard Bearer format for unit tests
        clean_token = token.replace("Bearer ", "").strip()
        if clean_token.startswith("mock:"):
            email = clean_token.split("mock:", 1)[1]
            user = self.get_user_by_email(email)
            if not user:
                raise ValueError(f"Unknown mock user: {email}")
            return {
                "oid": user.oid,
                "email": user.email,
                "name": user.display_name,
                "roles": user.roles,
                "tid": user.tid,
                "iss": "https://login.microsoftonline.com/demo-holdings/v2.0",
                "aud": "procurement-api-client-id",
            }

        # Otherwise if it matches an existing email or OID directly
        user = self.get_user_by_email(clean_token) or self.get_user_by_oid(clean_token)
        if user:
            return {
                "oid": user.oid,
                "email": user.email,
                "name": user.display_name,
                "roles": user.roles,
                "tid": user.tid,
                "iss": "https://login.microsoftonline.com/demo-holdings/v2.0",
                "aud": "procurement-api-client-id",
            }

        # Generic token fallback for tests
        return {
            "oid": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"token:{clean_token}")),
            "email": "test@demo-holdings.fake",
            "name": "Test User",
            "roles": ["Procurement.Buyer"],
            "tid": "tenant-demo-holdings-0000-0000",
            "iss": "https://login.microsoftonline.com/demo-holdings/v2.0",
            "aud": "procurement-api-client-id",
        }


class IdentityRealAdapter:
    """Real Microsoft Entra ID OpenID Connect / MS Graph client (unconfigured in demo)."""

    @property
    def name(self) -> str:
        return "Microsoft Entra ID (real connector)"

    def get_user_by_email(self, email: str) -> EntraUser | None:
        raise NotConfiguredError(
            "Real Entra ID adapter is not configured. Set INTEGRATIONS_MODE=mock."
        )

    def get_user_by_oid(self, oid: str) -> EntraUser | None:
        raise NotConfiguredError(
            "Real Entra ID adapter is not configured. Set INTEGRATIONS_MODE=mock."
        )

    def map_email_to_oid(self, email: str) -> str | None:
        raise NotConfiguredError(
            "Real Entra ID adapter is not configured. Set INTEGRATIONS_MODE=mock."
        )

    def validate_token(self, token: str) -> dict[str, Any]:
        raise NotConfiguredError(
            "Real Entra ID adapter is not configured. Set INTEGRATIONS_MODE=mock."
        )
