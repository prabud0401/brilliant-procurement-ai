import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.audit.service import record as record_audit
from app.core.models import Setting
from app.core.policy import Principal

KEY_ALIASES: dict[str, str] = {
    "thresholds": "approval_tiers",
    "tolerances": "three_way_match_tolerances",
    "buyer-policy": "buyer_exception_policy",
    "buyer_policy": "buyer_exception_policy",
}

DEFAULT_SETTINGS: dict[str, dict[str, Any]] = {
    "approval_tiers": {
        "version": 1,
        "value": [
            {
                "tier": 1,
                "max_amount_aed": "5000.00",
                "required_role": "buyer",
                "approver_count": 1,
                "description": "Up to AED 5,000: 1 Buyer",
            },
            {
                "tier": 2,
                "max_amount_aed": "50000.00",
                "required_role": "manager",
                "approver_count": 1,
                "description": "AED 5,000 to AED 50,000: 1 Manager",
            },
            {
                "tier": 3,
                "max_amount_aed": None,
                "required_role": "manager",
                "approver_count": 2,
                "description": "Above AED 50,000: 2 Managers",
            },
        ],
    },
    "three_way_match_tolerances": {
        "version": 1,
        "value": {
            "invoiced_vs_received_qty_max_units": 0,
            "received_vs_ordered_qty_max_pct": 0.0,
            "unit_price_variance_pct": 2.0,
            "unit_price_variance_max_aed": "50.00",
            "total_pro_rata_variance_pct": 1.0,
            "vat_max_difference_aed": "1.00",
            "vendor_po_match_required": True,
        },
    },
    "buyer_exception_policy": {
        "version": 1,
        "value": {
            "max_amount_aed": "500.00",
            "allow_over_billed_qty": False,
        },
    },
}


def _resolve_key(key: str) -> str:
    cleaned = key.strip().lower()
    return KEY_ALIASES.get(cleaned, cleaned)


def _load_from_seed_file(canonical_key: str) -> dict[str, Any] | None:
    seed_file = (
        Path(__file__).resolve().parent.parent.parent.parent / "seed" / "data" / "settings.json"
    )
    if seed_file.exists():
        try:
            with open(seed_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                val = data.get(canonical_key)
                if isinstance(val, dict):
                    return val
        except Exception:
            pass
    return None


def get_setting(db: Session, key: str) -> dict[str, Any]:
    canonical_key = _resolve_key(key)
    row = db.query(Setting).filter(Setting.key == canonical_key).first()
    if row:
        return {
            "key": key,
            "value": row.value,
            "version": row.version,
            "updated_at": row.updated_at,
        }

    # Check seed file or defaults
    seed_val = _load_from_seed_file(canonical_key)
    if seed_val is not None:
        version = int(seed_val.get("version", 1))
        val = seed_val.get("value", seed_val)
    else:
        default_entry = DEFAULT_SETTINGS.get(canonical_key, {"version": 1, "value": {}})
        version = default_entry.get("version", 1)
        val = default_entry.get("value", {})

    # Seed into database for consistency
    new_setting = Setting(
        key=canonical_key,
        value=val if isinstance(val, dict) else {"data": val},
        version=version,
        updated_at=datetime.now(timezone.utc),
    )
    db.add(new_setting)
    db.flush()

    return {
        "key": key,
        "value": new_setting.value,
        "version": new_setting.version,
        "updated_at": new_setting.updated_at,
    }


def update_setting(
    db: Session,
    key: str,
    new_value: Any,
    actor: Principal,
) -> dict[str, Any]:
    canonical_key = _resolve_key(key)
    row = db.query(Setting).filter(Setting.key == canonical_key).first()

    old_val: dict[str, Any] | None = None
    old_version = 0

    if row:
        old_val = row.value
        old_version = row.version
        row.value = new_value if isinstance(new_value, dict) else {"data": new_value}
        row.version = old_version + 1
        row.updated_by = actor.id
        row.updated_at = datetime.now(timezone.utc)
    else:
        val_dict = new_value if isinstance(new_value, dict) else {"data": new_value}
        row = Setting(
            key=canonical_key,
            value=val_dict,
            version=1,
            updated_by=actor.id,
            updated_at=datetime.now(timezone.utc),
        )
        db.add(row)

    db.flush()

    record_audit(
        session=db,
        actor=actor,
        action="setting.updated",
        entity_type="setting",
        entity_id=None,
        before={"key": canonical_key, "value": old_val, "version": old_version},
        after={"key": canonical_key, "value": row.value, "version": row.version},
        reason=f"Admin updated setting '{canonical_key}' to version {row.version}",
    )
    db.commit()

    return {
        "key": key,
        "value": row.value,
        "version": row.version,
        "updated_at": row.updated_at,
    }
