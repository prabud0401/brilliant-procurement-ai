import json
from unittest.mock import MagicMock

import pytest
from fastapi import Request

from app.core.errors import (
    ProblemException,
    create_problem_response,
    problem_exception_handler,
)


@pytest.mark.unit
def test_create_problem_response_format() -> None:
    """Verify RFC 9457 application/problem+json fields and Content-Type."""
    resp = create_problem_response(
        status_code=409,
        code="FLAGS_OPEN",
        title="Document has unconfirmed fields",
        detail="3 flagged fields must be confirmed before this document can be used.",
        request_id="01JD7Q4N8V3K",
        errors=[{"field": "vat_amount", "message": "Validation failed: VAT is not 5%"}],
    )

    assert resp.status_code == 409
    assert resp.media_type == "application/problem+json"
    assert resp.headers["X-Request-ID"] == "01JD7Q4N8V3K"

    data = json.loads(bytes(resp.body).decode("utf-8"))
    assert data["type"] == "https://pda.example/errors/flags-open"
    assert data["title"] == "Document has unconfirmed fields"
    assert data["status"] == 409
    assert data["code"] == "FLAGS_OPEN"
    assert data["detail"] == "3 flagged fields must be confirmed before this document can be used."
    assert data["request_id"] == "01JD7Q4N8V3K"
    assert len(data["errors"]) == 1
    assert data["errors"][0]["field"] == "vat_amount"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_problem_exception_handler() -> None:
    request = MagicMock(spec=Request)
    request.state.request_id = "test-req-id"

    exc = ProblemException(
        status_code=403,
        code="SOD_BLOCKED",
        title="Segregation of Duties Blocked",
        detail="The creator of a purchase request cannot approve it.",
    )

    resp = await problem_exception_handler(request, exc)
    assert resp.status_code == 403
    data = json.loads(bytes(resp.body).decode("utf-8"))
    assert data["code"] == "SOD_BLOCKED"
    assert data["request_id"] == "test-req-id"
