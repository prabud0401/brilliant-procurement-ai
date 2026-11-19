import React from "react";

export type StatusType =
  | "draft"
  | "pending"
  | "approved"
  | "rejected"
  | "queued"
  | "processing"
  | "needs_review"
  | "confirmed"
  | "failed"
  | "matched"
  | "within_tolerance"
  | "exception"
  | "open"
  | "escalated"
  | "accepted"
  | "waiting"
  | "active"
  | "inactive"
  | string;

interface StatusConfig {
  label: string;
  bgColor: string;
  textColor: string;
  dotColor: string;
}

const STATUS_CONFIGS: Record<string, StatusConfig> = {
  // Green / Success
  approved: {
    label: "Approved",
    bgColor: "bg-emerald-50 border-emerald-200",
    textColor: "text-emerald-700",
    dotColor: "bg-emerald-500",
  },
  confirmed: {
    label: "Confirmed",
    bgColor: "bg-emerald-50 border-emerald-200",
    textColor: "text-emerald-700",
    dotColor: "bg-emerald-500",
  },
  matched: {
    label: "Matched",
    bgColor: "bg-emerald-50 border-emerald-200",
    textColor: "text-emerald-700",
    dotColor: "bg-emerald-500",
  },
  accepted: {
    label: "Accepted",
    bgColor: "bg-emerald-50 border-emerald-200",
    textColor: "text-emerald-700",
    dotColor: "bg-emerald-500",
  },
  active: {
    label: "Active",
    bgColor: "bg-emerald-50 border-emerald-200",
    textColor: "text-emerald-700",
    dotColor: "bg-emerald-500",
  },

  // Amber / Warning / In-progress
  pending: {
    label: "Pending",
    bgColor: "bg-amber-50 border-amber-200",
    textColor: "text-amber-700",
    dotColor: "bg-amber-500",
  },
  needs_review: {
    label: "Needs Review",
    bgColor: "bg-amber-50 border-amber-200",
    textColor: "text-amber-800",
    dotColor: "bg-amber-500",
  },
  within_tolerance: {
    label: "Within Tolerance",
    bgColor: "bg-amber-50 border-amber-200",
    textColor: "text-amber-700",
    dotColor: "bg-amber-500",
  },
  queued: {
    label: "Queued",
    bgColor: "bg-sky-50 border-sky-200",
    textColor: "text-sky-700",
    dotColor: "bg-sky-500",
  },
  processing: {
    label: "Processing",
    bgColor: "bg-indigo-50 border-indigo-200",
    textColor: "text-indigo-700",
    dotColor: "bg-indigo-500 animate-pulse",
  },
  escalated: {
    label: "Escalated",
    bgColor: "bg-orange-50 border-orange-200",
    textColor: "text-orange-800",
    dotColor: "bg-orange-500",
  },
  waiting: {
    label: "Waiting",
    bgColor: "bg-amber-50 border-amber-200",
    textColor: "text-amber-700",
    dotColor: "bg-amber-500",
  },

  // Red / Danger / Exception
  rejected: {
    label: "Rejected",
    bgColor: "bg-rose-50 border-rose-200",
    textColor: "text-rose-700",
    dotColor: "bg-rose-500",
  },
  failed: {
    label: "Failed",
    bgColor: "bg-rose-50 border-rose-200",
    textColor: "text-rose-700",
    dotColor: "bg-rose-500",
  },
  exception: {
    label: "Exception",
    bgColor: "bg-rose-50 border-rose-200",
    textColor: "text-rose-700",
    dotColor: "bg-rose-500",
  },

  // Gray / Neutral
  draft: {
    label: "Draft",
    bgColor: "bg-slate-50 border-slate-200",
    textColor: "text-slate-600",
    dotColor: "bg-slate-400",
  },
  open: {
    label: "Open",
    bgColor: "bg-blue-50 border-blue-200",
    textColor: "text-blue-700",
    dotColor: "bg-blue-500",
  },
  inactive: {
    label: "Inactive",
    bgColor: "bg-slate-100 border-slate-300",
    textColor: "text-slate-500",
    dotColor: "bg-slate-400",
  },
};

export interface StatusBadgeProps {
  status: StatusType;
  customLabel?: string;
  size?: "sm" | "md";
  className?: string;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({
  status,
  customLabel,
  size = "md",
  className = "",
}) => {
  const normalizedKey = status.toLowerCase().replace(/\s+/g, "_");
  const config = STATUS_CONFIGS[normalizedKey] || {
    label: customLabel || status,
    bgColor: "bg-slate-50 border-slate-200",
    textColor: "text-slate-700",
    dotColor: "bg-slate-400",
  };

  const label = customLabel || config.label;
  const sizeClasses =
    size === "sm" ? "px-2 py-0.5 text-xs" : "px-2.5 py-1 text-xs font-medium";

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border ${config.bgColor} ${config.textColor} ${sizeClasses} ${className}`}
      role="status"
      aria-label={`Status: ${label}`}
    >
      <span
        className={`h-1.5 w-1.5 rounded-full ${config.dotColor}`}
        aria-hidden="true"
      />
      <span>{label}</span>
    </span>
  );
};
