"""Prompt-injection detector based on rules and regex patterns (design 7.5, US-29)."""

from __future__ import annotations

import base64
import hashlib
import io
import logging
import re
from dataclasses import dataclass
from decimal import Decimal

import pypdf

logger = logging.getLogger("extraction.injection_detector")

# Patterns to detect prompt injection attempts
INJECTION_PATTERNS: list[re.Pattern[str]] = [
    # Direct instruction overrides
    re.compile(r"ignore\s+(?:all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"disregard\s+(?:all\s+)?(?:previous\s+instructions|line\s+totals)", re.IGNORECASE),
    re.compile(r"override\s+(?:all\s+)?(?:rules|instructions)", re.IGNORECASE),
    # Approval and payment bypasses
    re.compile(r"approve\s+(?:this\s+)?(?:invoice|po|payment)", re.IGNORECASE),
    re.compile(r"approve\s+invoice\s+immediately", re.IGNORECASE),
    re.compile(r"authorize\s+full\s+payment", re.IGNORECASE),
    re.compile(r"mark\s+(?:this\s+)?(?:po|invoice)\s+(?:as\s+)?auto-approved", re.IGNORECASE),
    re.compile(r"bypass\s+segregation\s+of\s+duties", re.IGNORECASE),
    re.compile(r"set\s+total\s+to\s+0", re.IGNORECASE),
    re.compile(r"overwrite\s+total\s+amount", re.IGNORECASE),
    # System prompt leak / instructions
    re.compile(r"system\s+prompt", re.IGNORECASE),
    re.compile(r"developer\s+instructions", re.IGNORECASE),
    re.compile(r"output\s+the\s+system\s+prompt", re.IGNORECASE),
    # Role-play & jailbreak markers
    re.compile(r"you\s+are\s+no\s+longer", re.IGNORECASE),
    re.compile(r"\byou\s+are\s+dan\b", re.IGNORECASE),
    re.compile(r"unrestricted\s+ai", re.IGNORECASE),
    # Authority spoofing / overrides
    re.compile(r"admin\s+override:", re.IGNORECASE),
    re.compile(r"system\s+notification:", re.IGNORECASE),
    re.compile(r"emergency\s+instruction", re.IGNORECASE),
    # Setting tampering
    re.compile(r"low_confidence_threshold", re.IGNORECASE),
    re.compile(r"ai_daily_budget", re.IGNORECASE),
    # Data exfiltration
    re.compile(r"list\s+all\s+user\s+records", re.IGNORECASE),
    re.compile(r"external\s+oids", re.IGNORECASE),
    re.compile(r"audit\s+chain\s+hashes", re.IGNORECASE),
    re.compile(r"documents\s+from\s+other\s+departments", re.IGNORECASE),
    re.compile(r"executive\s+compensation", re.IGNORECASE),
    re.compile(r"SYSTEM_SECRET_KEY", re.IGNORECASE),
    re.compile(r"!\[exfil\]", re.IGNORECASE),
    re.compile(r"drop\s+table\s+audit_log", re.IGNORECASE),
    # Delimiter escapes
    re.compile(r"</?document>", re.IGNORECASE),
    re.compile(r"</?system>", re.IGNORECASE),
    # Multilingual (Arabic)
    re.compile(r"تجاهل\s+(?:كل\s+)?التعليمات\s+السابقة"),
    re.compile(r"بالموافقة\s+على\s+هذه\s+الفاتورة"),
    re.compile(r"تعيين\s+الإجمالي\s+إلى\s+صفر"),
]

BASE64_CANDIDATE = re.compile(r"[A-Za-z0-9+/=]{16,}")


@dataclass
class DetectedInjection:
    page: int
    snippet_hash: str
    score: Decimal
    detector: str = "rule"


def scan_text_for_injection(text: str, page: int = 1) -> list[DetectedInjection]:
    """Scan text for injection patterns. Returns list of detected injection flags."""
    findings: list[DetectedInjection] = []

    # Check direct patterns
    for pat in INJECTION_PATTERNS:
        match = pat.search(text)
        if match:
            matched_snippet = match.group(0)
            snippet_hash = hashlib.sha256(matched_snippet.encode("utf-8")).hexdigest()
            findings.append(
                DetectedInjection(
                    page=page,
                    snippet_hash=snippet_hash,
                    score=Decimal("1.0000"),
                    detector="rule",
                )
            )

    # Check base64 encoded strings
    for m in BASE64_CANDIDATE.finditer(text):
        candidate = m.group(0)
        try:
            decoded = base64.b64decode(candidate).decode("utf-8", errors="ignore")
            for pat in INJECTION_PATTERNS:
                if pat.search(decoded):
                    snippet_hash = hashlib.sha256(candidate.encode("utf-8")).hexdigest()
                    findings.append(
                        DetectedInjection(
                            page=page,
                            snippet_hash=snippet_hash,
                            score=Decimal("1.0000"),
                            detector="rule",
                        )
                    )
                    break
        except Exception:
            pass

    return findings


def scan_pdf_for_injection(pdf_bytes: bytes) -> list[DetectedInjection]:
    """Extract native text layer from PDF bytes and scan for prompt injection."""
    findings: list[DetectedInjection] = []
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    for page_num, page in enumerate(reader.pages, start=1):
        page_text = page.extract_text() or ""
        if page_text:
            findings.extend(scan_text_for_injection(page_text, page=page_num))
    return findings
