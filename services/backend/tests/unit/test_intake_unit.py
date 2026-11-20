"""Unit tests for email intake: metadata, allowlist, key hashing, and rate limiting."""

from __future__ import annotations

import io
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.core.config import settings
from app.core.errors import ProblemException
from app.core.policy import CAPABILITY_MATRIX, Principal, ScopeRule, get_effective_scope
from app.intake.keygen import generate_key_and_hash
from app.intake.keygen import main as keygen_main
from app.intake.metadata import (
    EmailMetadata,
    extract_clean_email,
    is_sender_allowed,
    parse_received_at,
)
from app.intake.rate_limit import check_intake_rate_limit, reset_intake_rate_limits
from app.intake.security import hash_intake_key, verify_intake_key


@pytest.mark.unit
def test_email_metadata_mapping() -> None:
    dt = datetime(2026, 11, 20, 10, 30, 0, tzinfo=timezone.utc)
    meta = EmailMetadata(
        sender="vendor.billing@supplier.example",
        subject="Invoice #INV-2026-001",
        received_at=dt,
        message_id="<msg-id-12345@supplier.example>",
    )

    source_url = meta.to_source_url()
    assert isinstance(source_url, str)
    assert "vendor.billing@supplier.example" in source_url
    assert "Invoice #INV-2026-001" in source_url

    reconstructed = EmailMetadata.from_source_url(source_url)
    assert reconstructed.sender == meta.sender
    assert reconstructed.subject == meta.subject
    assert reconstructed.received_at == meta.received_at
    assert reconstructed.message_id == meta.message_id


@pytest.mark.unit
def test_parse_received_at() -> None:
    # 1. ISO string with Z
    dt1 = parse_received_at("2026-11-20T10:15:30Z")
    assert dt1.tzinfo == timezone.utc
    assert dt1.hour == 10
    assert dt1.minute == 15

    # 2. ISO string with numeric offset
    dt2 = parse_received_at("2026-11-20T14:15:30+04:00")
    assert dt2.tzinfo is not None
    assert dt2.astimezone(timezone.utc).hour == 10

    # 3. Naive ISO string -> treated as UTC
    dt3 = parse_received_at("2026-11-20T08:00:00")
    assert dt3.tzinfo == timezone.utc

    # 4. Datetime object
    now = datetime.now(timezone.utc)
    assert parse_received_at(now) == now

    # 5. Invalid string raises ProblemException 400
    with pytest.raises(ProblemException) as exc_info:
        parse_received_at("invalid-timestamp-value")
    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "INVALID_RECEIVED_AT"


@pytest.mark.unit
def test_extract_clean_email() -> None:
    assert extract_clean_email("plain@example.com") == "plain@example.com"
    assert extract_clean_email("John Doe <john.doe@example.com>") == "john.doe@example.com"
    assert extract_clean_email("  SALES@VENDOR.COM  ") == "sales@vendor.com"


@pytest.mark.unit
def test_sender_allowlist() -> None:
    # 1. Empty or None allows all
    assert is_sender_allowed("any@supplier.example", "") is True
    assert is_sender_allowed("any@supplier.example", None) is True
    assert is_sender_allowed("any@supplier.example", []) is True

    # 2. Comma-separated string allowlist
    allowlist_str = "billing@vendor1.example, invoices@vendor2.example"
    assert is_sender_allowed("billing@vendor1.example", allowlist_str) is True
    assert is_sender_allowed("Billing Team <BILLING@vendor1.example>", allowlist_str) is True
    assert is_sender_allowed("invoices@vendor2.example", allowlist_str) is True
    assert is_sender_allowed("intruder@attacker.example", allowlist_str) is False

    # 3. List of strings allowlist
    allowlist_list = ["approved@supplier.example"]
    assert is_sender_allowed("approved@supplier.example", allowlist_list) is True
    assert is_sender_allowed("unapproved@supplier.example", allowlist_list) is False


@pytest.mark.unit
def test_key_hashing_and_verification() -> None:
    key, key_hash = generate_key_and_hash()
    assert len(key) >= 32
    assert key_hash.startswith("$argon2")

    # Positive verification
    assert verify_intake_key(key, key_hash) is True

    # Test hash_intake_key
    h2 = hash_intake_key(key)
    assert verify_intake_key(key, h2) is True

    # Negative verifications
    assert verify_intake_key("wrong_key_value", key_hash) is False
    assert verify_intake_key("", key_hash) is False
    assert verify_intake_key(key, "") is False

    # SHA-256 fallback format verification
    import hashlib

    sha_hash = hashlib.sha256(b"my-secret-test-key").hexdigest()
    assert verify_intake_key("my-secret-test-key", sha_hash) is True
    assert verify_intake_key("my-secret-test-key", f"sha256:{sha_hash}") is True
    assert verify_intake_key("wrong-secret-key", sha_hash) is False


@pytest.mark.unit
def test_intake_rate_limiting(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_intake_rate_limits()
    monkeypatch.setattr(settings, "INTAKE_RATE_LIMIT_PER_MINUTE", 3)

    sender_a = "vendor_a@supplier.example"
    sender_b = "vendor_b@supplier.example"

    # 3 requests for sender A should pass
    check_intake_rate_limit(sender_a)
    check_intake_rate_limit(sender_a)
    check_intake_rate_limit(sender_a)

    # 4th request for sender A should raise 429
    with pytest.raises(ProblemException) as exc_info:
        check_intake_rate_limit(sender_a)
    assert exc_info.value.status_code == 429
    assert exc_info.value.code == "RATE_LIMIT_EXCEEDED"

    # Sender B should not be affected by sender A limit
    check_intake_rate_limit(sender_b)

    # Reset clears history
    reset_intake_rate_limits()
    check_intake_rate_limit(sender_a)


@pytest.mark.unit
def test_keygen_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    buf = io.StringIO()
    monkeypatch.setattr("sys.stdout", buf)
    keygen_main()
    output = buf.getvalue()

    assert "Generated Intake API Key:" in output
    assert "Key:  " in output
    assert "Hash: $argon2" in output


@pytest.mark.unit
def test_intake_role_in_policy_matrix() -> None:
    """Verify Role.INTAKE has ScopeRule.NONE for all business and admin capabilities."""
    intake_principal = Principal(
        id=uuid.uuid4(),
        email="intake@demo-holdings.example",
        display_name="Intake Service Account",
        roles=["intake"],
        department_id=None,
        department_name=None,
        approval_limit_aed=Decimal("0.00"),
    )

    for cap in CAPABILITY_MATRIX:
        scope = get_effective_scope(intake_principal, cap)
        assert scope == ScopeRule.NONE, (
            f"Intake principal should have ScopeRule.NONE for capability '{cap}', got {scope}"
        )
