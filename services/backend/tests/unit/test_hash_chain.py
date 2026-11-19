import hashlib
import uuid
from datetime import datetime, timezone

import pytest

from app.audit.service import canonical_row_json


@pytest.mark.unit
def test_canonical_json_determinism() -> None:
    """Verify that canonical JSON output is deterministic regardless of key ordering."""
    now = datetime(2026, 11, 19, 12, 0, 0, tzinfo=timezone.utc)
    user_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    before_dict_1 = {"total": 100, "status": "draft"}
    before_dict_2 = {"status": "draft", "total": 100}

    after_dict_1 = {"total": 120, "items": [{"name": "A"}, {"name": "B"}]}
    after_dict_2 = {"items": [{"name": "A"}, {"name": "B"}], "total": 120}

    bytes_1 = canonical_row_json(
        occurred_at=now,
        actor_id=user_id,
        actor_roles=["buyer", "requester"],
        action="document.uploaded",
        entity_type="document",
        entity_id=doc_id,
        before=before_dict_1,
        after=after_dict_1,
        reason="test upload",
        ai_model="mock-model",
        prompt_version="v1.0",
        request_id="req-12345",
    )

    bytes_2 = canonical_row_json(
        occurred_at=now,
        actor_id=user_id,
        actor_roles=["requester", "buyer"],  # Reversed roles order
        action="document.uploaded",
        entity_type="document",
        entity_id=doc_id,
        before=before_dict_2,
        after=after_dict_2,
        reason="test upload",
        ai_model="mock-model",
        prompt_version="v1.0",
        request_id="req-12345",
    )

    assert bytes_1 == bytes_2
    assert hashlib.sha256(bytes_1).digest() == hashlib.sha256(bytes_2).digest()


@pytest.mark.unit
def test_hash_chain_calculation() -> None:
    """Verify chaining sha256(prev_hash || canonical_json)."""
    now = datetime(2026, 11, 19, 12, 0, 0, tzinfo=timezone.utc)
    canonical = canonical_row_json(
        occurred_at=now,
        actor_id=None,
        actor_roles=None,
        action="system.bootstrapped",
        entity_type="system",
        entity_id=None,
        before=None,
        after=None,
        reason=None,
        ai_model=None,
        prompt_version=None,
        request_id="req-init",
    )

    prev_hash = b""
    hash_1 = hashlib.sha256(prev_hash + canonical).digest()
    assert len(hash_1) == 32

    # Second row chained
    hash_2 = hashlib.sha256(hash_1 + canonical).digest()
    assert len(hash_2) == 32
    assert hash_2 != hash_1
