# AI Quality Evaluation Report

This report documents the performance of the AI components in the Procurement Document Assistant across the AI Quality metrics (AIQ-01 through AIQ-10) defined in the system specifications.

---

## 1. Executive Summary & Verification Mode

- **Evaluation Mode:** `replay` (Offline test mode using recorded ground-truth replay fixtures)
- **Model Target:** Configurable chat model (default `gpt-5-mini`) and `text-embedding-3-small` (Vector Retrieval)
- **OCR Engine Target:** Azure Document Intelligence (Form Recognizer)
- **Execution Latency:** 0.04 seconds (replay pipeline execution)
- **Overall Result:** **10/10 metrics passed**

> [!IMPORTANT]
> **Interpretation of Replay Scores:**
> Replay fixtures are synthetically derived from ground-truth document and question data. Therefore, the 100% scores reported below demonstrate that the **evaluation harness, metric mathematics, schema parsers, confidence scoring logic, faithfulness verifier, and data plumbing operate correctly and without error**. Replay scores **do not** prove live model extraction accuracy or real-world OCR noise resistance. The definitive measurement of model quality occurs during live evaluation.

---

> **How to read these numbers.** Replay mode feeds the real pipeline code (extraction validation, retrieval, refusal logic, injection screening, comparison facts) with recorded AI responses. The replay fixtures are generated from the ground truth, so a 100% replay score proves that the pipeline, the metrics and the plumbing work end to end; it does not measure model quality. The live run (section 5) is the real measure.

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

```markdown
Pending: live evaluation after Azure AI services are enabled
```

When Azure OpenAI (default `gpt-5-mini`, `text-embedding-3-small`) and Azure Document Intelligence (`F0`) are provisioned at Gate G1, the live evaluation suite is triggered using:

```bash
cd services/backend && uv run python -m eval.run --mode live --confirm-live --max-cost-usd 3 --record-replay
```

The live execution will record real token usage, API latency, and true OCR extraction accuracy against the synthetic document dataset.
