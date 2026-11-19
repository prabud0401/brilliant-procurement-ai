"""Integration contract tests for Microsoft Entra ID identity adapter."""

from __future__ import annotations

import pytest

from app.integrations.base import NotConfiguredError
from app.integrations.identity import (
    IdentityAdapter,
    IdentityMockAdapter,
    IdentityRealAdapter,
)


@pytest.mark.integration
def test_identity_mock_adapter_contract() -> None:
    adapter = IdentityMockAdapter()
    assert isinstance(adapter, IdentityAdapter)
    assert adapter.name == "Microsoft Entra ID (mock adapter)"

    # Test seeded user lookups
    buyer = adapter.get_user_by_email("buyer@demo-holdings.fake")
    assert buyer is not None
    assert buyer.oid == "22222222-2222-2222-2222-222222222222"
    assert "Procurement.Buyer" in buyer.roles

    # Test map email to oid
    oid = adapter.map_email_to_oid("manager.it@demo-holdings.fake")
    assert oid == "33333333-3333-3333-3333-333333333332"

    # Test lookup by OID
    admin = adapter.get_user_by_oid("44444444-4444-4444-4444-444444444444")
    assert admin is not None
    assert admin.email == "admin@demo-holdings.fake"

    # Test token validation
    claims = adapter.validate_token("mock:buyer@demo-holdings.fake")
    assert claims["oid"] == buyer.oid
    assert "Procurement.Buyer" in claims["roles"]
    assert claims["email"] == "buyer@demo-holdings.fake"


@pytest.mark.integration
def test_identity_real_adapter_raises_not_configured() -> None:
    real_adapter = IdentityRealAdapter()
    assert isinstance(real_adapter, IdentityAdapter)
    assert real_adapter.name == "Microsoft Entra ID (real connector)"

    with pytest.raises(NotConfiguredError):
        real_adapter.get_user_by_email("user@example.com")

    with pytest.raises(NotConfiguredError):
        real_adapter.get_user_by_oid("00000000-0000-0000-0000-000000000000")

    with pytest.raises(NotConfiguredError):
        real_adapter.map_email_to_oid("user@example.com")

    with pytest.raises(NotConfiguredError):
        real_adapter.validate_token("token-xyz")
