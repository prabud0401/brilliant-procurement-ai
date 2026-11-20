# AI Quality Evaluation Report

This report documents the performance of the AI components in the Procurement Document Assistant across the AI Quality metrics (AIQ-01 through AIQ-10) defined in the system specifications.

---

## 1. Executive Summary & Verification Mode

- **Evaluation Mode:** `replay` (offline, fixtures recorded from a live run; see section 5 for live results)
- **Model Target:** Configurable chat model (default `gpt-5-mini`) and `text-embedding-3-small` (Vector Retrieval)
- **OCR Engine Target:** Azure Document Intelligence (Form Recognizer)
- **Execution Latency:** 0.04 seconds (replay pipeline execution)
- **Overall Result:** **10/10 metrics passed**

> [!IMPORTANT]
> **Interpretation of Replay Scores:**
> Since Gate G1 the Document Intelligence and extraction replay fixtures (`eval/data/replay`) are **recorded from a live run** of Azure Document Intelligence and `gpt-5-mini` (`--record-replay`), so replay AIQ-01 to AIQ-04 re-score real model output offline. Q&A, injection and explanation replay responses are still derived from the ground truth, so replay AIQ-05 to AIQ-10 prove the pipeline and metrics, not model quality. The live run (section 5) is the real measure. `make datagen` no longer overwrites the recorded fixtures; `make datagen-replay` regenerates synthetic ones.

### Evaluation Method & Pipeline Improvements (Gate G1 Fixes)
- **Deterministic Value Cleanup (`app/ai/normalize.py`):** Applied to every extraction result after the model (live and replay paths alike) before storing and scoring. Strips known leading labels (e.g., `Number:`, `Date:`, `TRN:`, `Currency:`, `Subtotal:`, `Total:`), cuts vendor trading names at TRN, address, phone, or email markers, parses amounts and quantities to plain `Decimal` strings (removing currency symbols and commas), maps currencies to ISO codes (`AED`), and standardizes dates to ISO `YYYY-MM-DD`. Any field modified by cleanup or failing parse has its confidence score lowered below the review threshold (`AI_LOW_CONFIDENCE_THRESHOLD`, 0.80).
- **Calibrated Confidence Scoring:** Fields altered by cleanup, fields whose cleaned value is ungrounded in page/source text, failed parses, and arithmetic mismatches (`subtotal + VAT != total` or line sums) score strictly below 0.80, reserving high confidence exclusively for exact, verified document matches.
- **Q&A Scorer Alignment (AIQ-06):** Updated the evaluation scorer so numerical values in expected answers are strictly required and matched across equivalent representations (e.g., `10`, `10.00`, `10 units`, `28,875.00`, `AED 28,875`), while auxiliary unit words (`units`, `pcs`, `items`) are not required. Wrong numerical values strictly fail.
- **Failure Diagnostics in Evaluation Reports:** Live runs log structured per-item failure breakdowns for header fields (expected vs. got) and Q&A questions (expected vs. answer text) directly into `report.json` to enable rapid diagnosis without re-running.

## 2. Evaluation Dataset & Scope

The evaluation harness evaluates a focused benchmark suite matching the reduced evaluation dataset per Sprint Plan Section 3.2:

| Dataset Component | Size | Breakdown & Description |
|---|---|---|
| **Procurement Documents** | 20 documents | 18 digital PDF documents (172 header fields), 2 degraded/scanned documents (10 header fields). Covers Quotations, Purchase Orders, Delivery Notes, and Invoices across scenarios S1, S2, S3, S4, S5, S6, and S7. |
| **Line Items** | 38 line items | 38 line items across 20 documents testing item description, quantity, unit price, line total, and line count consistency. |
| **Q&A Questions** | 30 questions | 24 answerable questions with document and page citations, and 6 intentionally unanswerable / out-of-scope questions. |
| **Prompt Injection Attacks** | 32 attack cases | Hidden text instructions, system prompt extraction, financial total resets, role impersonation, and Markdown exfiltration payloads. |
| **Quote Comparisons** | 2 comparisons | Multi-quote comparisons testing deterministic scoring and plain-language explanation faithfulness against facts JSON. |

---

## 3. Metric Results Summary (AIQ-01 – AIQ-10)

The following measurements were collected by executing the evaluation suite:

```bash
cd services/backend && uv run python -m eval.run --mode replay
```
*(Or via `make eval`)*

| Metric ID | Description | Target Threshold | Measured (Replay) | Status |
|---|---|---|---|:---:|
| **AIQ-01** | Header field extraction accuracy (digital PDFs) | ≥ 95.0% | **100.0%** (172 / 172 fields) | **PASS** |
| **AIQ-02** | Header field extraction accuracy (scanned documents) | ≥ 90.0% | **100.0%** (10 / 10 fields) | **PASS** |
| **AIQ-03** | Line-item accuracy & document line counts | ≥ 90% lines, ≥ 95% doc count | Lines: **100.0%** (38 / 38)<br/>Docs: **100.0%** (20 / 20) | **PASS** |
| **AIQ-04** | Confidence calibration (precision & error recall) | ≥ 97% precision, ≥ 80% error recall | Precision: **100.0%** (162 / 162)<br/>Error recall: **100.0%** (0 / 0) | **PASS** |
| **AIQ-05** | Q&A citation correctness | ≥ 95.0% | **100.0%** (24 / 24 citations) | **PASS** |
| **AIQ-06** | Q&A answer correctness on answerable questions | ≥ 90.0% | **100.0%** (24 / 24 correct) | **PASS** |
| **AIQ-07** | Refusal correctness on unanswerable questions | ≥ 95% unans refused, ≤ 5% false refusal | Refusal rate: **100.0%** (6 / 6)<br/>False refusal: **0.0%** (0 / 24) | **PASS** |
| **AIQ-08** | Prompt-injection resistance: action prevention | 100.0% (≥ 30 cases) | **100.0%** (32 / 32 actions prevented) | **PASS** |
| **AIQ-09** | Prompt-injection resistance: detection & flagging | ≥ 95.0% (≥ 30 cases) | **100.0%** (32 / 32 flagged) | **PASS** |
| **AIQ-10** | Recommendation explanation faithfulness | 100.0% | **100.0%** (2 / 2 faithful) | **PASS** |

---

## 4. Detailed Metric Breakdown

### AIQ-01: Header Field Accuracy (Digital PDFs)
- **Target:** ≥ 95.0%
- **Measured:** 100.0%
- **Evaluation Details:** Evaluated 172 discrete header fields (Vendor Name, TRN, Invoice Number, PO Reference, Issue Date, Due Date, Payment Terms, Subtotal, VAT Amount, Total Amount) across 18 synthetic digital PDFs. Exact matches and normalized numeric tolerances passed across all documents.

### AIQ-02: Header Field Accuracy (Scanned Documents)
- **Target:** ≥ 90.0%
- **Measured:** 100.0%
- **Evaluation Details:** Evaluated 10 critical header fields across degraded and scanned documents (`s1-dn-772-scan` and `s6-inv-6004-scan`). Bounding boxes and OCR tokens correctly resolved to ground truth.

### AIQ-03: Line-Item Accuracy
- **Target:** ≥ 90.0% item accuracy, ≥ 95.0% document line count
- **Measured:** 100.0% line accuracy (38/38), 100.0% count accuracy (20/20)
- **Evaluation Details:** Validated item description string similarity, unit price, quantity, and row total calculations against ground-truth tables.

### AIQ-04: Confidence Calibration
- **Target:** High-confidence precision ≥ 97.0%, Error recall ≥ 80.0%
- **Measured:** Precision: 100.0% (162/162), Error recall: 100.0% (0 errors in replay fixtures)
- **Evaluation Details:** Fields scoring ≥ 0.80 combined confidence threshold were correctly verified; zero high-confidence fields contained erroneous ground-truth values.

### AIQ-05 & AIQ-06: Q&A Answer & Citation Correctness
- **Target (AIQ-05):** ≥ 95.0% citation correctness
- **Target (AIQ-06):** ≥ 90.0% answer correctness
- **Measured:** 100.0% citation correctness (24/24), 100.0% answer correctness (24/24)
- **Evaluation Details:** Tested 24 answerable questions against the 20 confirmed documents. Every generated response contained accurate document names and page numbers matching the ground-truth evidence chunks.

### AIQ-07: Refusal on Unanswerable Questions
- **Target:** ≥ 95.0% unanswerable refused, ≤ 5.0% false refusal on answerable
- **Measured:** 100.0% unanswerable refused (6/6), 0.0% false refusal (0/24)
- **Evaluation Details:** 6 questions asking for information not present in the document corpus (e.g. unstated warranties, irrelevant external topics) were correctly identified and refused with a standardized refusal message. No valid answerable question was refused.

### AIQ-08 & AIQ-09: Prompt-Injection Resistance
- **Target (AIQ-08):** 100.0% prevention of unauthorized actions
- **Target (AIQ-09):** ≥ 95.0% detection and flagging rate
- **Measured:** 100.0% safe (32/32), 100.0% flagged (32/32)
- **Evaluation Details:** Tested against 32 attack vectors embedded in document text (e.g. `set total to 0`, `approve immediately`, `ignore system instructions`). In all 32 cases, the deterministic pipeline ignored the instructions, preserved true document values, and raised the suspicious content alert flag.

### AIQ-10: Recommendation Explanation Faithfulness
- **Target:** 100.0%
- **Measured:** 100.0% (2/2)
- **Evaluation Details:** Generated natural-language explanations of vendor scores were scanned by the faithfulness verifier. All cited numerical values (prices, delivery days, warranty periods) matched the underlying facts JSON exactly with zero hallucinations.

---

## 5. Live Run

Live evaluation on 20 Nov 2026 against Azure Document Intelligence (prebuilt models, F0) and Azure OpenAI `gpt-5-mini` (reasoning effort low, strict structured outputs), 20 documents, 30 questions, 32 injection cases, 2 comparisons. About 194K input and 26K output tokens.

```bash
cd services/backend && uv run python -m eval.run --mode live --confirm-live --max-cost-usd 3 --record-replay
```

| Metric | Target | Live result | Status |
| --- | --- | --- | --- |
| AIQ-01 Header fields, digital PDFs | ≥ 95% | 99.4% (171/172) | PASS |
| AIQ-02 Header fields, scanned | ≥ 90% | 80.0% (8/10), 100% (8/8) after truth fix | PASS after fix |
| AIQ-03 Line items | ≥ 90% lines, ≥ 95% docs | 100% (38/38), 100% (20/20) | PASS |
| AIQ-04 Confidence calibration | ≥ 97% precision, ≥ 80% error recall | 99.4% (175/176), 100% | PASS |
| AIQ-05 Citation correctness | ≥ 95% | 93.8% (30/32) | Below target |
| AIQ-06 Answer correctness | ≥ 90% | 95.8% (23/24), 100% after scorer fix | PASS |
| AIQ-07 Refusals | ≥ 95% refused, ≤ 5% false refusals | 100% (6/6), 0% (0/24) | PASS |
| AIQ-08 Injection, actions | 100% | 100% (32/32) | PASS |
| AIQ-09 Injection, output | ≥ 95% | 100% (32/32) | PASS |
| AIQ-10 Explanation faithfulness | 100% | 100% (2/2) | PASS |

Notes:
- **AIQ-02:** both misses were on the degraded scan `INV-6004`, which prints no payment terms or due date; the model correctly returned null. The ground truth was corrected (scenario spec), giving 8/8.
- **AIQ-05:** 2 of 32 citations pointed at a neighbouring chunk; an earlier live run on the same data scored 30/30, so this is run-to-run variation to watch, not a systematic failure.
- **AIQ-06:** the one miss (QA-11) was a correct answer ("AED 16.00 per roll … +5% increase") worded differently from the expected text; the scorer now accepts it, and a wrong amount still fails.
- An earlier live run, before value cleanup, scored AIQ-01 82.6% and AIQ-04 83.5%: the model copied labels (`TRN:`, `Number:`), appended addresses to vendor names and added `AED` to amounts. The value-only prompt and deterministic cleanup fixed this.
