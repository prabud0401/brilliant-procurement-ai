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
    model: str  # "gpt-4o-mini"
    prompt_version: str  # "v1"
    metrics: list[MetricResult]
    documents_evaluated: int
    questions_evaluated: int
    injection_cases_evaluated: int
    cost_estimate_usd: float | None = None
    duration_seconds: float = 0.0

    @property
    def passed_metrics(self) -> int:
        return sum(1 for m in self.metrics if m.passed)

    @property
    def total_metrics(self) -> int:
        return len(self.metrics)

    @property
    def all_passed(self) -> bool:
        return all(m.passed for m in self.metrics)

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
            },
            "metrics": [m.to_dict() for m in self.metrics],
            "dataset": {
                "documents_count": self.documents_evaluated,
                "questions_count": self.questions_evaluated,
                "injection_cases_count": self.injection_cases_evaluated,
            },
        }

    def to_markdown(self) -> str:
        status_banner = "PASSED" if self.all_passed else "FAILED"
        lines = [
            f"# AI Quality Evaluation Report — {status_banner}",
            "",
            f"- **Timestamp:** {self.timestamp}",
            f"- **Mode:** `{self.mode}` (Provider: `{self.provider}`)",
            f"- **Model:** `{self.model}` (Prompt Version: `{self.prompt_version}`)",
            f"- **Duration:** {self.duration_seconds:.2f}s",
            f"- **Status:** {self.passed_metrics}/{self.total_metrics} metrics passed",
        ]

        if self.cost_estimate_usd is not None:
            lines.append(f"- **Estimated AI Cost:** ${self.cost_estimate_usd:.4f} USD")

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
