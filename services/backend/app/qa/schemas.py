"""Pydantic request and response schemas for Q&A per design 5.4."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ScopeFilter(BaseModel):
    pr_id: uuid.UUID | None = None
    vendor_id: uuid.UUID | None = None
    document_id: uuid.UUID | None = None


class QuestionRequest(BaseModel):
    question: str = Field(..., max_length=500)
    scope: ScopeFilter | None = None


class Citation(BaseModel):
    document_id: uuid.UUID
    title: str
    page: int
    chunk_id: str


class AnswerItem(BaseModel):
    text: str
    citations: list[Citation] = Field(default_factory=list)


class QuestionResponse(BaseModel):
    answer: list[AnswerItem] = Field(default_factory=list)
    refused: bool = False
    refusal_reason: str | None = None


class QAHistoryItem(BaseModel):
    id: uuid.UUID
    question_redacted: str
    answer: str | None = None
    citations: Any = None
    refused: bool = False
    created_at: datetime
