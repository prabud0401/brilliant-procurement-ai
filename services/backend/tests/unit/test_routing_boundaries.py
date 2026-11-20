import uuid
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.approvals.routing import (
    TIER_1_MAX,
    TIER_2_MAX,
    build_approval_steps,
    determine_tier,
)
from app.core.models import User


@pytest.mark.unit
def test_determine_tier_boundaries() -> None:
    # 5,000.00 -> Tier 1
    assert determine_tier(Decimal("5000.00")) == 1
    assert determine_tier(Decimal("1000.00")) == 1
    assert determine_tier(TIER_1_MAX) == 1

    # 5,000.01 -> Tier 2
    assert determine_tier(Decimal("5000.01")) == 2
    assert determine_tier(Decimal("25000.00")) == 2
    assert determine_tier(Decimal("50000.00")) == 2
    assert determine_tier(TIER_2_MAX) == 2

    # 50,000.01 -> Tier 3
    assert determine_tier(Decimal("50000.01")) == 3
    assert determine_tier(Decimal("100000.00")) == 3


@pytest.mark.unit
def test_routing_tier_1_boundaries() -> None:
    creator_id = uuid.uuid4()
    buyer_id = uuid.uuid4()
    dept_id = uuid.uuid4()

    mock_db = MagicMock()

    buyer_user = User(
        id=buyer_id,
        email="buyer@test.example",
        display_name="Buyer",
        approval_limit_aed=Decimal("0.00"),
        active=True,
    )

    mock_db.query.return_value.join.return_value.filter.return_value.all.return_value = [buyer_user]

    # Test amount exactly 5,000.00 (Tier 1)
    steps, snapshot = build_approval_steps(
        db=mock_db,
        subject_type="pr",
        subject_id=uuid.uuid4(),
        total_aed=Decimal("5000.00"),
        department_id=dept_id,
        creator_id=creator_id,
    )

    assert snapshot["tier"] == 1
    assert len(steps) == 1
    assert steps[0].sequence == 1
    assert steps[0].tier == 1
    assert steps[0].assigned_to == buyer_id


@pytest.mark.unit
def test_routing_tier_2_boundaries() -> None:
    creator_id = uuid.uuid4()
    mgr_id = uuid.uuid4()
    dept_id = uuid.uuid4()

    mock_db = MagicMock()

    mgr_user = User(
        id=mgr_id,
        email="mgr@test.example",
        display_name="Manager",
        department_id=dept_id,
        approval_limit_aed=Decimal("50000.00"),
        active=True,
    )

    q = mock_db.query.return_value.join.return_value.filter.return_value
    q.filter.return_value.all.return_value = [mgr_user]

    # Test amount 5,000.01 (Tier 2)
    steps_5001, snapshot_5001 = build_approval_steps(
        db=mock_db,
        subject_type="pr",
        subject_id=uuid.uuid4(),
        total_aed=Decimal("5000.01"),
        department_id=dept_id,
        creator_id=creator_id,
    )
    assert snapshot_5001["tier"] == 2
    assert len(steps_5001) == 1
    assert steps_5001[0].tier == 2
    assert steps_5001[0].assigned_to == mgr_id

    # Test amount exactly 50,000.00 (Tier 2)
    steps_50k, snapshot_50k = build_approval_steps(
        db=mock_db,
        subject_type="pr",
        subject_id=uuid.uuid4(),
        total_aed=Decimal("50000.00"),
        department_id=dept_id,
        creator_id=creator_id,
    )
    assert snapshot_50k["tier"] == 2
    assert len(steps_50k) == 1
    assert steps_50k[0].tier == 2
    assert steps_50k[0].assigned_to == mgr_id


@pytest.mark.unit
def test_routing_tier_3_boundaries_two_managers() -> None:
    creator_id = uuid.uuid4()
    mgr1_id = uuid.uuid4()
    mgr2_id = uuid.uuid4()
    dept_id = uuid.uuid4()

    mock_db = MagicMock()

    mgr1_user = User(
        id=mgr1_id,
        email="mgr1@test.example",
        display_name="Dept Manager",
        department_id=dept_id,
        approval_limit_aed=Decimal("50000.00"),
        active=True,
    )
    mgr2_user = User(
        id=mgr2_id,
        email="mgr2@test.example",
        display_name="Higher Manager",
        department_id=uuid.uuid4(),
        approval_limit_aed=Decimal("250000.00"),
        active=True,
    )

    # For step 1
    mock_db.query.return_value.join.return_value.filter.return_value.all.return_value = [mgr1_user]
    # For step 2
    q2 = mock_db.query.return_value.join.return_value.filter.return_value
    q2.filter.return_value.all.return_value = [mgr2_user]

    # Test amount 50,000.01 (Tier 3)
    steps, snapshot = build_approval_steps(
        db=mock_db,
        subject_type="pr",
        subject_id=uuid.uuid4(),
        total_aed=Decimal("50000.01"),
        department_id=dept_id,
        creator_id=creator_id,
    )
    assert snapshot["tier"] == 3
    assert len(steps) == 2
    assert steps[0].sequence == 1
    assert steps[0].tier == 2
    assert steps[1].sequence == 2
    assert steps[1].tier == 3
    assert steps[1].assigned_to == mgr2_id


@pytest.mark.unit
def test_routing_tier_2_new_departments() -> None:
    """Verify Finance, HR, and Operations tier-2 requests route to each dept's manager."""
    creator_id = uuid.uuid4()
    dept_finance = uuid.uuid4()
    dept_hr = uuid.uuid4()
    dept_ops = uuid.uuid4()

    mgr_finance = User(
        id=uuid.uuid4(),
        email="manager.finance@demo-holdings.example",
        display_name="Hassan Demo-Manager",
        department_id=dept_finance,
        approval_limit_aed=Decimal("50000.00"),
        active=True,
    )
    mgr_hr = User(
        id=uuid.uuid4(),
        email="manager.hr@demo-holdings.example",
        display_name="Zayed Demo-Manager",
        department_id=dept_hr,
        approval_limit_aed=Decimal("50000.00"),
        active=True,
    )
    mgr_ops = User(
        id=uuid.uuid4(),
        email="manager.ops@demo-holdings.example",
        display_name="Reem Demo-Manager",
        department_id=dept_ops,
        approval_limit_aed=Decimal("50000.00"),
        active=True,
    )

    all_managers = [mgr_finance, mgr_hr, mgr_ops]

    for target_dept, expected_mgr in [
        (dept_finance, mgr_finance),
        (dept_hr, mgr_hr),
        (dept_ops, mgr_ops),
    ]:
        mock_db = MagicMock()
        q = mock_db.query.return_value.join.return_value.filter.return_value
        q.filter.return_value.all.return_value = list(all_managers)

        steps, snapshot = build_approval_steps(
            db=mock_db,
            subject_type="pr",
            subject_id=uuid.uuid4(),
            total_aed=Decimal("15000.00"),
            department_id=target_dept,
            creator_id=creator_id,
        )
        assert snapshot["tier"] == 2
        assert len(steps) == 1
        assert steps[0].tier == 2
        assert steps[0].assigned_to == expected_mgr.id


@pytest.mark.unit
def test_routing_manager_fallback_deterministic() -> None:
    """Verify fallback ordering is deterministic when no dept match exists."""
    from datetime import datetime, timezone

    from app.approvals.routing import find_eligible_manager

    creator_id = uuid.uuid4()
    t1 = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 1, 2, 0, 0, 0, tzinfo=timezone.utc)

    # Earlier-created manager (facilities) should win fallback over later-created managers
    mgr_fac = User(
        id=uuid.uuid4(),
        email="manager.facilities@demo-holdings.example",
        approval_limit_aed=Decimal("50000.00"),
        created_at=t1,
        active=True,
    )
    mgr_fin = User(
        id=uuid.uuid4(),
        email="manager.finance@demo-holdings.example",
        approval_limit_aed=Decimal("50000.00"),
        created_at=t2,
        active=True,
    )

    mock_db = MagicMock()
    # Regardless of permutation in returned list:
    q = mock_db.query.return_value.join.return_value.filter.return_value.filter.return_value
    q.all.return_value = [
        mgr_fin,
        mgr_fac,
    ]

    chosen = find_eligible_manager(
        mock_db, creator_id=creator_id, min_limit_aed=Decimal("10000.00")
    )
    assert chosen is not None
    assert chosen.id == mgr_fac.id
