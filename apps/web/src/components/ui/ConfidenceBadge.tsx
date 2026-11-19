import React from "react";

export interface ConfidenceBadgeProps {
  confidence: number | null | undefined; // 0.0 to 1.0
  threshold?: number; // default 0.80
  showPercentage?: boolean;
  size?: "sm" | "md";
  className?: string;
}

/**
 * Confidence score badge according to Design 6.3:
 * - score >= 0.80: High confidence (Green)
 * - 0.60 <= score < 0.80: Medium confidence / Needs review (Amber)
 * - score < 0.60: Low confidence / Needs review (Red)
 */
export const ConfidenceBadge: React.FC<ConfidenceBadgeProps> = ({
  confidence,
  threshold = 0.8,
  showPercentage = true,
  size = "md",
  className = "",
}) => {
  if (confidence === null || confidence === undefined || isNaN(confidence)) {
    return (
      <span
        className={`inline-flex items-center gap-1 rounded border border-slate-200 bg-slate-50 px-2 py-0.5 text-xs text-slate-500 ${className}`}
        aria-label="Confidence: Unknown"
      >
        —
      </span>
    );
  }

  const score = Math.max(0, Math.min(1, confidence));
  const percent = Math.round(score * 100);
  const isHigh = score >= threshold;
  const isMedium = score >= 0.6 && score < threshold;

  let colorClasses = "bg-rose-50 text-rose-700 border-rose-200";
  let label = "Low";
  let dotColor = "bg-rose-500";

  if (isHigh) {
    colorClasses = "bg-emerald-50 text-emerald-700 border-emerald-200";
    label = "High";
    dotColor = "bg-emerald-500";
  } else if (isMedium) {
    colorClasses = "bg-amber-50 text-amber-800 border-amber-200";
    label = "Needs Review";
    dotColor = "bg-amber-500";
  } else {
    label = "Needs Review";
  }

  const sizeClasses =
    size === "sm" ? "px-1.5 py-0.5 text-xs" : "px-2.5 py-1 text-xs font-medium";

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border ${colorClasses} ${sizeClasses} ${className}`}
      title={`Confidence score: ${percent}% (${score.toFixed(2)})`}
      aria-label={`Confidence: ${percent}%, ${label}`}
      role="status"
    >
      <span className={`h-1.5 w-1.5 rounded-full ${dotColor}`} aria-hidden="true" />
      <span>{showPercentage ? `${percent}%` : label}</span>
      {!isHigh && showPercentage && (
        <span className="text-[10px] font-normal uppercase tracking-wider text-amber-700 opacity-90">
          (Review)
        </span>
      )}
    </span>
  );
};
