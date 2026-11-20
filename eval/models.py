"""Data models for AI Quality Evaluation reports and metrics."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class MetricResult:
    """Evaluation result for an individual AI Quality metric."""

    id: str  # e.g. "AIQ-01"
    name: str  # e.g. "Header field accuracy, digital PDFs"
    target_description: str  # e.g. ">= 95%"
    target_value: float  # e.g. 0.95
    actual_value: float  # e.g. 0.985
    formatted_value: str  # e.g. "98.5%"
    passed: bool
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EvaluationReport:
    """Complete evaluation report containing all AIQ metrics and execution summary."""

    timestamp: str
    mode: str  # "replay" | "live"
    provider: str  # "replay" | "live"
    model: str  # e.g. "gpt-5-mini"
    prompt_version: str  # "v1"
    metrics: list[MetricResult]
    documents_evaluated: int
    questions_evaluated: int
    injection_cases_evaluated: int
    cost_estimate_usd: float | None = None
    actual_cost_usd: float | None = None
    tokens_in: int = 0
    tokens_out: int = 0
    duration_seconds: float = 0.0
    aborted: bool = False
    abort_reason: str | None = None
    failure_details: dict[str, Any] | None = None

    @property
    def passed_metrics(self) -> int:
        return sum(1 for m in self.metrics if m.passed)

    @property
    def total_metrics(self) -> int:
        return len(self.metrics)

    @property
    def all_passed(self) -> bool:
        return not self.aborted and (len(self.metrics) > 0 and all(m.passed for m in self.metrics))

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "mode": self.mode,
            "provider": self.provider,
            "model": self.model,
            "prompt_version": self.prompt_version,
            "summary": {
                "total_metrics": self.total_metrics,
                "passed_metrics": self.passed_metrics,
                "failed_metrics": self.total_metrics - self.passed_metrics,
                "all_passed": self.all_passed,
                "duration_seconds": round(self.duration_seconds, 2),
                "cost_estimate_usd": self.cost_estimate_usd,
                "actual_cost_usd": self.actual_cost_usd,
                "tokens_in": self.tokens_in,
                "tokens_out": self.tokens_out,
                "total_tokens": self.tokens_in + self.tokens_out,
                "aborted": self.aborted,
                "abort_reason": self.abort_reason,
            },
            "metrics": [m.to_dict() for m in self.metrics],
            "dataset": {
                "documents_count": self.documents_evaluated,
                "questions_count": self.questions_evaluated,
                "injection_cases_count": self.injection_cases_evaluated,
            },
            "failure_details": self.failure_details,
        }

    def to_markdown(self) -> str:
        status_banner = "ABORTED" if self.aborted else ("PASSED" if self.all_passed else "FAILED")
        lines = [
            f"# AI Quality Evaluation Report — {status_banner}",
            "",
            f"- **Timestamp:** {self.timestamp}",
            f"- **Mode:** `{self.mode}` (Provider: `{self.provider}`)",
            f"- **Model:** `{self.model}` (Prompt Version: `{self.prompt_version}`)",
            f"- **Duration:** {self.duration_seconds:.2f}s",
            f"- **Status:** {self.passed_metrics}/{self.total_metrics} metrics passed",
        ]

        if self.aborted:
            lines.append(f"- **Abort Reason:** {self.abort_reason}")

        if self.cost_estimate_usd is not None:
            lines.append(f"- **Estimated AI Cost:** ${self.cost_estimate_usd:.4f} USD")

        if self.actual_cost_usd is not None:
            lines.append(
                f"- **Actual AI Spend:** ${self.actual_cost_usd:.4f} USD "
                f"(Tokens In: {self.tokens_in}, Tokens Out: {self.tokens_out}, "
                f"Total Tokens: {self.tokens_in + self.tokens_out})"
            )

        lines.extend(
            [
                "",
                "## Summary Table (AIQ-01 – AIQ-10)",
                "",
                "| ID | Metric | Target | Actual | Status |",
                "|---|---|---|---|:---:|",
            ]
        )

        for m in self.metrics:
            badge = "PASS" if m.passed else "**FAIL**"
            lines.append(
                f"| {m.id} | {m.name} | {m.target_description} | {m.formatted_value} | {badge} |"
            )

        lines.extend(["", "## Detailed Metric Breakdowns", ""])

        for m in self.metrics:
            badge = "PASSED" if m.passed else "FAILED"
            lines.append(f"### {m.id}: {m.name} [{badge}]")
            lines.append(f"- **Target:** {m.target_description}")
            lines.append(f"- **Measured:** {m.formatted_value}")
            if m.details:
                for k, v in m.details.items():
                    if isinstance(v, (int, float, str, bool)):
                        lines.append(f"- **{k}:** {v}")
                    elif isinstance(v, dict):
                        lines.append(f"- **{k}:**")
                        for sub_k, sub_v in v.items():
                            lines.append(f"  - {sub_k}: {sub_v}")
                    elif isinstance(v, list) and v and isinstance(v[0], str):
                        lines.append(f"- **{k}:** {', '.join(v[:10])}")
            lines.append("")

        return "\n".join(lines)
