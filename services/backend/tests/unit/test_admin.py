import uuid
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.admin.schemas import (
    AdminUserUpdateRequest,
    RetentionSettingsUpdateRequest,
)
from app.admin.service import (
    get_retention_settings,
    list_integrations,
    update_retention_settings,
    update_user,
)
from app.core.errors import ProblemException
from app.core.models import Setting, User
from app.core.policy import Principal


def _make_principal(roles: list[str], user_id: uuid.UUID | None = None) -> Principal:
    return Principal(
        id=user_id or uuid.uuid4(),
        email="admin@demo.example",
        display_name="Admin",
        roles=roles,
        department_id=uuid.uuid4(),
        department_name="IT",
        approval_limit_aed=Decimal("0.00"),
    )


@pytest.mark.unit
def test_list_integrations_returns_expected_adapters() -> None:
    adapters = list_integrations()
    assert len(adapters) == 4

    adapter_names = {a.adapter: a for a in adapters}
    assert "odoo" in adapter_names
    assert adapter_names["odoo"].label == "Odoo (mock adapter)"
    assert adapter_names["odoo"].mode == "mock"

    assert "sharepoint" in adapter_names
    assert adapter_names["sharepoint"].label == "SharePoint (mock adapter)"

    assert "power_automate" in adapter_names
    assert adapter_names["power_automate"].label == "Power Automate (mock adapter)"

    assert "identity" in adapter_names
    assert adapter_names["identity"].label == "Microsoft Entra ID (mock adapter)"


@pytest.mark.unit
def test_update_user_invalid_role_raises_422() -> None:
    db = MagicMock()
    user_id = uuid.uuid4()
    actor = _make_principal(["admin"])

    mock_user = User(id=user_id, email="u@example.com", display_name="User", active=True)
    mock_user.roles = []
    db.query.return_value.filter.return_value.first.return_value = mock_user

    with pytest.raises(ProblemException) as exc:
        update_user(
            db,
            user_id,
            AdminUserUpdateRequest(roles=["superhero", "buyer"]),
            actor,
        )
    assert exc.value.status_code == 422
    assert exc.value.code == "INVALID_ROLE"


@pytest.mark.unit
def test_retention_settings_get_and_update() -> None:
    db = MagicMock()
    actor = _make_principal(["admin"])

    # Default retention if not set
    mock_setting = Setting(
        key="retention",
        value={"documents_retention_days": 45, "audit_retention_days": 400},
        version=1,
    )
    db.query.return_value.filter.return_value.first.return_value = mock_setting

    ret = get_retention_settings(db)
    assert ret.documents_retention_days == 45
    assert ret.audit_retention_days == 400

    # Update retention
    updated = update_retention_settings(
        db,
        RetentionSettingsUpdateRequest(documents_retention_days=60),
        actor,
    )
    assert updated.documents_retention_days == 60
    assert updated.audit_retention_days == 400
