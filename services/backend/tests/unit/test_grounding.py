"""Unit tests for citation grounding and verification per design 6.6 and US-17/18."""

from __future__ import annotations

import pytest

from app.ai.schemas import AnswerSentence, RetrievedChunk
from app.qa.grounding import verify_grounding


@pytest.fixture
def retrieved_sample_chunks() -> list[RetrievedChunk]:
    return [
        RetrievedChunk(
            id="chunk-1",
            document_id="doc-100",
            document_title="Quote Q-1042 (Gulf Line IT Trading)",
            page=1,
            chunk_no=1,
            text=(
                "Gulf Line IT Trading\n"
                "QUOTATION Number: Q-1042\n"
                "Date: 2026-11-03\n"
                "Payment Terms: Net 30\n"
                "Total: AED 28,875.00"
            ),
            score=0.035,
        ),
        RetrievedChunk(
            id="chunk-2",
            document_id="doc-200",
            document_title="Delivery Note DN-771",
            page=1,
            chunk_no=1,
            text=("Delivery Note DN-771\nDate: 2026-11-08\nDelivered: 6 units of Laptop 14in"),
            score=0.030,
        ),
    ]


@pytest.mark.unit
def test_grounding_valid_sentence_passes(retrieved_sample_chunks: list[RetrievedChunk]) -> None:
    sentence = AnswerSentence(
        text=(
            "Gulf Line IT Trading quoted Net 30 payment terms on Q-1042 "
            "with a total of AED 28,875.00 on 2026-11-03."
        ),
        chunk_ids=["chunk-1"],
    )
    grounded = verify_grounding([sentence], retrieved_sample_chunks)
    assert len(grounded) == 1
    assert grounded[0].text == sentence.text


@pytest.mark.unit
def test_grounding_unretrieved_chunk_id_dropped(
    retrieved_sample_chunks: list[RetrievedChunk],
) -> None:
    sentence = AnswerSentence(
        text="Payment terms are Net 30 on Q-1042.",
        chunk_ids=["chunk-unretrieved-999"],
    )
    grounded = verify_grounding([sentence], retrieved_sample_chunks)
    assert len(grounded) == 0


@pytest.mark.unit
def test_grounding_invented_number_dropped(
    retrieved_sample_chunks: list[RetrievedChunk],
) -> None:
    # Chunk text has 28,875.00, sentence claims invented 99,999.00
    sentence = AnswerSentence(
        text="The total amount on Q-1042 is AED 99,999.00.",
        chunk_ids=["chunk-1"],
    )
    grounded = verify_grounding([sentence], retrieved_sample_chunks)
    assert len(grounded) == 0


@pytest.mark.unit
def test_grounding_invented_date_dropped(
    retrieved_sample_chunks: list[RetrievedChunk],
) -> None:
    # Chunk text has 2026-11-03, sentence claims invented 2027-12-25
    sentence = AnswerSentence(
        text="Quote Q-1042 was issued on 2027-12-25.",
        chunk_ids=["chunk-1"],
    )
    grounded = verify_grounding([sentence], retrieved_sample_chunks)
    assert len(grounded) == 0


@pytest.mark.unit
def test_grounding_invented_vendor_dropped(
    retrieved_sample_chunks: list[RetrievedChunk],
) -> None:
    # Chunk 1 belongs to Gulf Line, but sentence attributes it to Falcon Office Supplies LLC
    sentence = AnswerSentence(
        text="Falcon Office Supplies LLC offered Net 30 payment terms on Q-1042.",
        chunk_ids=["chunk-1"],
    )
    grounded = verify_grounding([sentence], retrieved_sample_chunks)
    assert len(grounded) == 0


@pytest.mark.unit
def test_grounding_partial_failure_preserves_valid(
    retrieved_sample_chunks: list[RetrievedChunk],
) -> None:
    valid_sentence = AnswerSentence(
        text="Delivery note DN-771 shows 6 units delivered.",
        chunk_ids=["chunk-2"],
    )
    invalid_sentence = AnswerSentence(
        text="Invoice total was AED 50,000.00.",
        chunk_ids=["chunk-1"],
    )

    grounded = verify_grounding([valid_sentence, invalid_sentence], retrieved_sample_chunks)
    assert len(grounded) == 1
    assert grounded[0].text == valid_sentence.text
