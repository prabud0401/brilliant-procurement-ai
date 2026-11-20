"""Citation grounding checker per design 3.4, 6.6, and prompt R07."""

from __future__ import annotations

import re
from typing import Sequence

from app.ai.schemas import AnswerSentence, RetrievedChunk

DEFAULT_VENDORS = [
    "Falcon Office Supplies LLC",
    "Gulf Line IT Trading",
    "Oasis Facility Services",
    "Desert Build Materials",
    "Corniche Electrical Co.",
    "Sandstone Furniture LLC",
    "Falcon Office Supplies",
    "Gulf Line IT",
    "Oasis Facility",
    "Desert Build",
    "Corniche Electrical",
    "Sandstone Furniture",
    "Falcon",
    "Gulf Line",
    "Oasis",
    "Corniche",
    "Sandstone",
]

NUMBER_PATTERN = re.compile(r"\b\d+(?:,\d{3})*(?:\.\d+)?\b")
DATE_PATTERN = re.compile(r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}\b")


def verify_grounding(
    sentences: Sequence[AnswerSentence],
    retrieved_chunks: Sequence[RetrievedChunk],
    known_vendors: Sequence[str] | None = None,
) -> list[AnswerSentence]:
    """Check that every cited chunk was retrieved, and that numbers, dates,

    and vendor names in each sentence appear in the cited chunk text.
    Sentences that fail are dropped.
    """
    if not sentences or not retrieved_chunks:
        return []

    chunks_by_id = {str(c.id): c for c in retrieved_chunks}
    vendors = list(known_vendors or DEFAULT_VENDORS)

    grounded_sentences: list[AnswerSentence] = []

    for sentence in sentences:
        if not sentence.chunk_ids:
            # Must cite at least one retrieved chunk
            continue

        # 1. Every cited chunk must be in the retrieved set
        all_cited_chunks: list[RetrievedChunk] = []
        missing_citation = False
        for cid in sentence.chunk_ids:
            chunk = chunks_by_id.get(str(cid))
            if not chunk:
                missing_citation = True
                break
            all_cited_chunks.append(chunk)

        if missing_citation or not all_cited_chunks:
            continue

        cited_text = " ".join(c.text for c in all_cited_chunks)
        cited_text_lower = cited_text.lower()
        cited_words = set(re.findall(r"[a-zA-Z0-9_\-]+", cited_text_lower))

        # 2. Check Numbers
        sentence_numbers = NUMBER_PATTERN.findall(sentence.text)
        numbers_valid = True
        for num_str in sentence_numbers:
            num_clean = num_str.replace(",", "")
            # Check direct match in cited text
            if num_str in cited_text or num_clean in cited_text:
                continue
            # Check word match
            if num_clean.lower() in cited_words:
                continue
            # If float e.g. "1900.00", check int part "1900"
            if "." in num_clean:
                int_part = num_clean.split(".")[0]
                if int_part in cited_words or int_part in cited_text:
                    continue
            # If int e.g. "16", check if it appears as part of a date or line
            if re.search(r"\b" + re.escape(num_clean) + r"\b", cited_text):
                continue

            numbers_valid = False
            break

        if not numbers_valid:
            continue

        # 3. Check Dates
        sentence_dates = DATE_PATTERN.findall(sentence.text)
        dates_valid = True
        for d in sentence_dates:
            if d.lower() not in cited_text_lower:
                dates_valid = False
                break

        if not dates_valid:
            continue

        # 4. Check Vendor Names
        sentence_text_lower = sentence.text.lower()
        vendors_valid = True
        for v in vendors:
            v_lower = v.lower()
            # Only check if vendor is actually mentioned in the sentence
            if re.search(r"\b" + re.escape(v_lower) + r"\b", sentence_text_lower):
                if v_lower not in cited_text_lower:
                    vendors_valid = False
                    break

        if not vendors_valid:
            continue

        grounded_sentences.append(sentence)

    return grounded_sentences
