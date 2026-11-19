import uuid
from decimal import Decimal

import pytest

from app.core.policy import (
    CAPABILITY_MATRIX,
    Principal,
    Role,
    ScopeRule,
    get_effective_scope,
)

EXPECTED_MATRIX = {
    "document.upload_extract": {
        Role.REQUESTER: ScopeRule.OWN,
        Role.BUYER: ScopeRule.ALL,
        Role.MANAGER: ScopeRule.NONE,
        Role.ADMIN: ScopeRule.NONE,
    },
    "document.view": {
        Role.REQUESTER: ScopeRule.OWN,
        Role.BUYER: ScopeRule.ALL,
        Role.MANAGER: ScopeRule.DEPT,
        Role.ADMIN: ScopeRule.METADATA,
    },
    "document.review": {
        Role.REQUESTER: ScopeRule.NONE,
        Role.BUYER: ScopeRule.ALL,
        Role.MANAGER: ScopeRule.NONE,
        Role.ADMIN: ScopeRule.NONE,
    },
    "integration.sharepoint": {
        Role.REQUESTER: ScopeRule.NONE,
        Role.BUYER: ScopeRule.ALL,
        Role.MANAGER: ScopeRule.NONE,
        Role.ADMIN: ScopeRule.NONE,
    },
    "pr.create_edit": {
        Role.REQUESTER: ScopeRule.ALL,
        Role.BUYER: ScopeRule.ALL,
        Role.MANAGER: ScopeRule.ALL,
        Role.ADMIN: ScopeRule.NONE,
    },
    "pr.submit": {
        Role.REQUESTER: ScopeRule.OWN,
        Role.BUYER: ScopeRule.ALL,
        Role.MANAGER: ScopeRule.NONE,
        Role.ADMIN: ScopeRule.NONE,
    },
    "comparison.write": {
        Role.REQUESTER: ScopeRule.NONE,
        Role.BUYER: ScopeRule.ALL,
        Role.MANAGER: ScopeRule.NONE,
        Role.ADMIN: ScopeRule.NONE,
    },
    "comparison.view": {
        Role.REQUESTER: ScopeRule.OWN,
        Role.BUYER: ScopeRule.ALL,
        Role.MANAGER: ScopeRule.DEPT,
        Role.ADMIN: ScopeRule.NONE,
    },
    "po.create": {
        Role.REQUESTER: ScopeRule.NONE,
        Role.BUYER: ScopeRule.ALL,
        Role.MANAGER: ScopeRule.NONE,
        Role.ADMIN: ScopeRule.NONE,
    },
    "approval.decide": {
        Role.REQUESTER: ScopeRule.NONE,
        Role.BUYER: ScopeRule.TIER_1_NOT_OWN,
        Role.MANAGER: ScopeRule.WITHIN_LIMIT_NOT_OWN,
        Role.ADMIN: ScopeRule.NONE,
    },
    "match.resolve": {
        Role.REQUESTER: ScopeRule.NONE,
        Role.BUYER: ScopeRule.POLICY,
        Role.MANAGER: ScopeRule.ESCALATED,
        Role.ADMIN: ScopeRule.NONE,
    },
    "qa.ask": {
        Role.REQUESTER: ScopeRule.OWN,
        Role.BUYER: ScopeRule.ALL,
        Role.MANAGER: ScopeRule.DEPT,
        Role.ADMIN: ScopeRule.NONE,
    },
    "audit.view": {
        Role.REQUESTER: ScopeRule.OWN,
        Role.BUYER: ScopeRule.ALL,
        Role.MANAGER: ScopeRule.DEPT,
        Role.ADMIN: ScopeRule.ALL,
    },
    "audit.export": {
        Role.REQUESTER: ScopeRule.NONE,
        Role.BUYER: ScopeRule.NONE,
        Role.MANAGER: ScopeRule.NONE,
        Role.ADMIN: ScopeRule.ALL,
    },
    "admin.manage": {
        Role.REQUESTER: ScopeRule.NONE,
        Role.BUYER: ScopeRule.NONE,
        Role.MANAGER: ScopeRule.NONE,
        Role.ADMIN: ScopeRule.ALL,
    },
}


@pytest.mark.unit
def test_all_capabilities_present_and_match_design_7_2() -> None:
    """Verify that every capability in Design 7.2 has an entry for all 4 roles."""
    assert set(CAPABILITY_MATRIX.keys()) == set(EXPECTED_MATRIX.keys())

    for cap, role_rules in EXPECTED_MATRIX.items():
        assert cap in CAPABILITY_MATRIX, f"Missing capability {cap}"
        for role in [Role.REQUESTER, Role.BUYER, Role.MANAGER, Role.ADMIN]:
            assert role in CAPABILITY_MATRIX[cap], f"Missing role {role} for capability {cap}"
            actual = CAPABILITY_MATRIX[cap][role]
            expected = role_rules[role]
            assert actual == expected, (
                f"Mismatch for {cap} and {role}: expected {expected}, got {actual}"
            )


@pytest.mark.unit
def test_admin_has_no_business_permissions() -> None:
    """Admin role has no business permissions unless also granted a business role (Design 7.2)."""
    admin_principal = Principal(
        id=uuid.uuid4(),
        email="admin@example.com",
        display_name="Admin",
        roles=["admin"],
        department_id=None,
        department_name=None,
        approval_limit_aed=Decimal("0.00"),
    )

    business_caps = [
        "document.upload_extract",
        "document.review",
        "integration.sharepoint",
        "pr.create_edit",
        "pr.submit",
        "comparison.write",
        "comparison.view",
        "po.create",
        "approval.decide",
        "match.resolve",
        "qa.ask",
    ]

    for cap in business_caps:
        scope = get_effective_scope(admin_principal, cap)
        assert scope == ScopeRule.NONE, (
            f"Admin should not have business capability {cap}, got {scope}"
        )

    # Admin should have audit and admin permissions
    assert get_effective_scope(admin_principal, "audit.view") == ScopeRule.ALL
    assert get_effective_scope(admin_principal, "audit.export") == ScopeRule.ALL
    assert get_effective_scope(admin_principal, "admin.manage") == ScopeRule.ALL


@pytest.mark.unit
def test_multi_role_principal_takes_highest_scope() -> None:
    """User with both Requester and Buyer roles receives Buyer scope on document review."""
    multi_principal = Principal(
        id=uuid.uuid4(),
        email="combo@example.com",
        display_name="Combo",
        roles=["requester", "buyer"],
        department_id=None,
        department_name=None,
        approval_limit_aed=Decimal("0.00"),
    )

    assert get_effective_scope(multi_principal, "document.review") == ScopeRule.ALL
    assert get_effective_scope(multi_principal, "document.upload_extract") == ScopeRule.ALL
