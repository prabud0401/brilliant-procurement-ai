import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.core.models import ApprovalStep, Outbox, User, UserRole
from app.settings_api.service import get_setting

TIER_1_MAX = Decimal("5000.00")
TIER_2_MAX = Decimal("50000.00")


def extract_tier_limits(source: dict[str, Any] | None) -> tuple[Decimal, Decimal]:
    tier_1_max = Decimal("5000.00")
    tier_2_max = Decimal("50000.00")
    if not source:
        return tier_1_max, tier_2_max

    if "tier_1_max" in source and source["tier_1_max"] is not None:
        try:
            tier_1_max = Decimal(str(source["tier_1_max"]))
        except Exception:
            pass
    if "tier_2_max" in source and source["tier_2_max"] is not None:
        try:
            tier_2_max = Decimal(str(source["tier_2_max"]))
        except Exception:
            pass

    tiers = source.get("tier_thresholds") or source.get("value") or source.get("tiers")
    if isinstance(tiers, list):
        for t in tiers:
            if isinstance(t, dict):
                tier_num = t.get("tier")
                max_amt = t.get("max_amount_aed")
                if tier_num == 1 and max_amt is not None:
                    try:
                        tier_1_max = Decimal(str(max_amt))
                    except Exception:
                        pass
                elif tier_num == 2 and max_amt is not None:
                    try:
                        tier_2_max = Decimal(str(max_amt))
                    except Exception:
                        pass
    return tier_1_max, tier_2_max


def determine_tier(
    total_aed: Decimal,
    tier_1_max: Decimal = Decimal("5000.00"),
    tier_2_max: Decimal = Decimal("50000.00"),
) -> int:
    if total_aed <= tier_1_max:
        return 1
    if total_aed <= tier_2_max:
        return 2
    return 3


def find_eligible_buyer(
    db: Session,
    creator_id: uuid.UUID,
    preferred_dept_id: uuid.UUID | None = None,
) -> User | None:
    buyers = (
        db.query(User)
        .join(UserRole, User.id == UserRole.user_id)
        .filter(
            UserRole.role == "buyer",
            User.active.is_(True),
            User.id != creator_id,
        )
        .all()
    )
    if not buyers:
        return None
    try:
        buyers.sort(key=lambda u: getattr(u, "email", ""))
    except Exception:
        pass
    return buyers[0]


def find_eligible_manager(
    db: Session,
    creator_id: uuid.UUID,
    min_limit_aed: Decimal | None = None,
    preferred_dept_id: uuid.UUID | None = None,
    exclude_user_ids: list[uuid.UUID] | None = None,
) -> User | None:
    excluded = set(exclude_user_ids or [])
    excluded.add(creator_id)

    query = (
        db.query(User)
        .join(UserRole, User.id == UserRole.user_id)
        .filter(
            UserRole.role == "manager",
            User.active.is_(True),
            User.id.notin_(excluded),
        )
    )
    if min_limit_aed is not None:
        query = query.filter(User.approval_limit_aed >= min_limit_aed)

    managers = query.all()
    if not managers:
        return None

    if preferred_dept_id:
        for m in managers:
            if m.department_id == preferred_dept_id:
                return m

    # Sort by approval_limit_aed ascending to pick the closest sufficient limit.
    # Secondary order by created_at then email ensures fallback determinism is preserved.
    def _manager_sort_key(m: User) -> tuple[Decimal, str, str]:
        limit = getattr(m, "approval_limit_aed", Decimal("0.00")) or Decimal("0.00")
        created_at = getattr(m, "created_at", None)
        if isinstance(created_at, datetime):
            c_str = created_at.isoformat()
        else:
            c_str = "9999-12-31"
        email = getattr(m, "email", "") or ""
        return (limit, c_str, email)

    managers.sort(key=_manager_sort_key)
    return managers[0]


def build_approval_steps(
    db: Session,
    subject_type: str,
    subject_id: uuid.UUID,
    total_aed: Decimal,
    department_id: uuid.UUID,
    creator_id: uuid.UUID,
) -> tuple[list[ApprovalStep], dict[str, Any]]:
    tier_setting = get_setting(db, "thresholds")
    tier_1_max, tier_2_max = extract_tier_limits(tier_setting)
    tier = determine_tier(total_aed, tier_1_max=tier_1_max, tier_2_max=tier_2_max)

    rule_snapshot: dict[str, Any] = {
        "tier_setting_version": tier_setting.get("version", 1),
        "tier_thresholds": tier_setting.get("value"),
        "tier_1_max": str(tier_1_max),
        "tier_2_max": str(tier_2_max),
        "total_aed": str(total_aed),
        "tier": tier,
        "steps_created": [],
    }

    steps: list[ApprovalStep] = []

    if tier == 1:
        # Tier 1: 1 Buyer (not creator) or 1 Manager
        buyer = find_eligible_buyer(db, creator_id=creator_id)
        assigned_user = buyer
        if not assigned_user:
            assigned_user = find_eligible_manager(
                db, creator_id=creator_id, min_limit_aed=total_aed
            )

        step = ApprovalStep(
            subject_type=subject_type,
            subject_id=subject_id,
            sequence=1,
            tier=1,
            assigned_to=assigned_user.id if assigned_user else None,
            status="pending",
            created_by=creator_id,
        )
        steps.append(step)

    elif tier == 2:
        # Tier 2: 1 Department Manager within limit (not creator)
        dept_mgr = find_eligible_manager(
            db,
            creator_id=creator_id,
            min_limit_aed=total_aed,
            preferred_dept_id=department_id,
        )
        if not dept_mgr:
            # Next eligible approver logic
            dept_mgr = find_eligible_manager(
                db,
                creator_id=creator_id,
                min_limit_aed=total_aed,
            )

        step = ApprovalStep(
            subject_type=subject_type,
            subject_id=subject_id,
            sequence=1,
            tier=2,
            assigned_to=dept_mgr.id if dept_mgr else None,
            status="pending",
            created_by=creator_id,
        )
        steps.append(step)

    else:
        # Tier 3: Two Managers in sequence (Dept Manager, then 2nd Manager with limit >= total)
        # Step 1: Department Manager (tier 2)
        mgr1 = find_eligible_manager(
            db,
            creator_id=creator_id,
            preferred_dept_id=department_id,
        )
        if not mgr1:
            mgr1 = find_eligible_manager(db, creator_id=creator_id)

        step1 = ApprovalStep(
            subject_type=subject_type,
            subject_id=subject_id,
            sequence=1,
            tier=2,
            assigned_to=mgr1.id if mgr1 else None,
            status="pending",
            created_by=creator_id,
        )
        steps.append(step1)

        # Step 2: Second Manager with sufficient limit (tier 3)
        exclude_ids = [mgr1.id] if mgr1 else []
        mgr2 = find_eligible_manager(
            db,
            creator_id=creator_id,
            min_limit_aed=total_aed,
            exclude_user_ids=exclude_ids,
        )

        step2 = ApprovalStep(
            subject_type=subject_type,
            subject_id=subject_id,
            sequence=2,
            tier=3,
            assigned_to=mgr2.id if mgr2 else None,
            status="pending",
            created_by=creator_id,
        )
        steps.append(step2)

    has_unassigned = any(s.assigned_to is None for s in steps)
    if has_unassigned:
        rule_snapshot["no_eligible_approver"] = True
        # Alert Admin via outbox
        outbox_event = Outbox(
            event_type="approval.no_eligible_approver",
            payload={
                "subject_type": subject_type,
                "subject_id": str(subject_id),
                "total_aed": str(total_aed),
                "tier": tier,
            },
            idempotency_key=str(uuid.uuid4()),
            status="pending",
        )
        db.add(outbox_event)

    for s in steps:
        db.add(s)
        rule_snapshot["steps_created"].append(
            {
                "sequence": s.sequence,
                "tier": s.tier,
                "assigned_to": str(s.assigned_to) if s.assigned_to else None,
            }
        )

    return steps, rule_snapshot
