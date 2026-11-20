"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  CheckCircle,
  XCircle,
  AlertTriangle,
  FileText,
  GitCompare,
  Building,
  User,
  ShieldCheck,
  Check,
  X,
  Loader2,
  Clock,
} from "lucide-react";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { formatMoneyAED, formatGSTDate } from "@/lib/formatters";
import type { ApprovalBundle } from "@/lib/flow/types";

export interface ApprovalDetailProps {
  bundle: ApprovalBundle;
  currentUserId: string;
  userRoles: string[];
  userLimit: number | string;
  onToast?: (type: "success" | "error" | "info" | "warning", title: string, message?: string) => void;
}

export const ApprovalDetail: React.FC<ApprovalDetailProps> = ({
  bundle,
  currentUserId,
  userRoles,
  userLimit,
  onToast,
}) => {
  const router = useRouter();
  const [deciding, setDeciding] = useState(false);
  const [rejectModalOpen, setRejectModalOpen] = useState(false);
  const [rejectComment, setRejectComment] = useState("");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [decidedStatus, setDecidedStatus] = useState<string | null>(null);

  const subject = bundle.subject;
  const isPO = bundle.subject_type === "po";
  const totalAmount = Number(subject.total || subject.total_aed || 0);
  const limitAmount = Number(userLimit || 0);

  // SoD check: creator cannot approve own request or PO
  const isCreator = subject.requester_id === currentUserId || subject.created_by === currentUserId;

  // Limit check: manager cannot approve above delegated financial limit
  // Note: Tier 1 buyer approval has limit = 0 in profile, handled by tier check on backend
  const isBuyerOnly = userRoles.includes("buyer") && !userRoles.includes("manager");
  const isAboveLimit = !isBuyerOnly && userRoles.includes("manager") && totalAmount > limitAmount;

  // Can user decide?
  const isPending = bundle.step_status === "pending" && !decidedStatus;
  const isAssigned = !bundle.assigned_to || bundle.assigned_to === currentUserId;
  const canDecide = isPending && isAssigned && !isCreator && !isAboveLimit;

  // Handler for decision
  const handleDecision = async (decision: "approve" | "reject", comment?: string) => {
    try {
      setDeciding(true);
      setErrorMsg(null);
      const res = await fetch(`/api/v1/approvals/${bundle.step_id}/decision`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Origin: window.location.origin,
        },
        body: JSON.stringify({
          decision,
          comment: comment?.trim() || undefined,
        }),
      });

      if (!res.ok) {
        const problem = await res.json().catch(() => ({}));
        throw new Error(problem.detail || problem.title || `HTTP ${res.status}`);
      }

      const data = await res.json();
      setDecidedStatus(decision === "approve" ? "approved" : "rejected");
      onToast?.(
        decision === "approve" ? "success" : "info",
        `Decision Recorded`,
        `Commitment has been ${decision}d.`
      );
      if (decision === "reject") {
        setRejectModalOpen(false);
      }
      router.refresh();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to record decision.";
      setErrorMsg(msg);
      onToast?.("error", "Decision Error", msg);
    } finally {
      setDeciding(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Banner & Decision Actions */}
      <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="flex items-center gap-3">
              <span className="font-mono text-sm font-bold text-blue-600">{subject.number}</span>
              <span className="rounded bg-blue-50 border border-blue-200 px-2.5 py-0.5 text-xs font-semibold text-blue-800">
                Tier {bundle.tier} Approval
              </span>
              <StatusBadge status={decidedStatus || bundle.step_status} />
            </div>
            <h1 className="mt-1 text-xl font-bold text-slate-900">
              One-Screen Approval Bundle: {subject.title || `Purchase Order ${subject.number}`}
            </h1>
            <p className="mt-1 text-xs text-slate-500">
              Approval Step {bundle.sequence} • Subject Type: {isPO ? "Purchase Order" : "Purchase Request"}
            </p>
          </div>

          {/* Action Buttons */}
          <div className="flex flex-wrap items-center gap-3">
            {canDecide && (
              <>
                <button
                  type="button"
                  onClick={() => handleDecision("approve")}
                  disabled={deciding}
                  data-testid="approve-btn"
                  className="inline-flex items-center gap-2 rounded-md bg-emerald-700 px-5 py-2 text-xs font-semibold text-white shadow-sm hover:bg-emerald-800 disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-700"
                >
                  <Check className="h-4 w-4" aria-hidden="true" />
                  <span>{deciding ? "Processing..." : "Approve Commitment"}</span>
                </button>
                <button
                  type="button"
                  onClick={() => setRejectModalOpen(true)}
                  disabled={deciding}
                  data-testid="reject-btn"
                  className="inline-flex items-center gap-2 rounded-md border border-rose-300 bg-white px-5 py-2 text-xs font-semibold text-rose-700 shadow-sm hover:bg-rose-50 disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-rose-600"
                >
                  <X className="h-4 w-4" aria-hidden="true" />
                  <span>Reject</span>
                </button>
              </>
            )}

            {decidedStatus && (
              <span className="inline-flex items-center gap-1.5 rounded-md bg-slate-100 px-4 py-2 text-xs font-semibold text-slate-700">
                <CheckCircle className="h-4 w-4 text-emerald-600" aria-hidden="true" />
                <span>Decision Submitted ({decidedStatus})</span>
              </span>
            )}
          </div>
        </div>

        {/* SoD Block Notice (US-23) */}
        {isCreator && (
          <div className="mt-4 rounded-md border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900 flex items-start gap-2.5" data-testid="sod-warning-banner">
            <AlertTriangle className="h-4 w-4 text-amber-600 shrink-0 mt-0.5" aria-hidden="true" />
            <div>
              <strong className="font-semibold">Segregation of Duties Enforced (US-23):</strong>
              <p className="mt-0.5 text-amber-800">
                You created this commitment. Under strict company governance, creators are blocked from approving their own spending.
              </p>
            </div>
          </div>
        )}

        {/* Financial Limit Notice */}
        {isAboveLimit && (
          <div className="mt-4 rounded-md border border-rose-200 bg-rose-50 p-3 text-xs text-rose-900 flex items-start gap-2.5" data-testid="limit-warning-banner">
            <AlertTriangle className="h-4 w-4 text-rose-600 shrink-0 mt-0.5" aria-hidden="true" />
            <div>
              <strong className="font-semibold">Approval Limit Exceeded:</strong>
              <p className="mt-0.5 text-rose-800">
                Total amount {formatMoneyAED(totalAmount)} exceeds your delegated manager approval limit of {formatMoneyAED(limitAmount)}.
              </p>
            </div>
          </div>
        )}

        {/* Error message from Problem Details */}
        {errorMsg && (
          <div className="mt-4 rounded-md border border-rose-200 bg-rose-50 p-3 text-xs text-rose-800">
            {errorMsg}
          </div>
        )}
      </div>

      {/* Facts Summary Card */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 space-y-6">
          {/* Commitment Summary */}
          <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
            <h2 className="text-base font-semibold text-slate-900 mb-4 flex items-center gap-2">
              <Building className="h-4 w-4 text-slate-500" aria-hidden="true" />
              Commitment Facts
            </h2>

            <dl className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
              <div className="border rounded-md p-3 bg-slate-50">
                <dt className="text-slate-500 font-medium">Department</dt>
                <dd className="mt-1 font-semibold text-slate-900">
                  {subject.department_name || "Department"}
                </dd>
              </div>
              <div className="border rounded-md p-3 bg-slate-50">
                <dt className="text-slate-500 font-medium">Requester / Creator</dt>
                <dd className="mt-1 font-semibold text-slate-900">
                  {subject.requester_name || "Employee"}
                </dd>
              </div>
              <div className="border rounded-md p-3 bg-blue-50/70 border-blue-200">
                <dt className="text-blue-700 font-medium">Total Amount (AED)</dt>
                <dd className="mt-1 font-bold text-sm text-blue-900" data-testid="approval-total-amount">
                  {formatMoneyAED(totalAmount)}
                </dd>
              </div>
            </dl>

            {/* Line Items Table */}
            <div className="mt-6">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">
                Commitment Line Items
              </h3>
              <div className="overflow-x-auto border rounded-md">
                <table className="min-w-full divide-y divide-slate-200 text-xs">
                  <thead className="bg-slate-50 text-[11px] font-semibold text-slate-700">
                    <tr>
                      <th scope="col" className="px-3 py-2 text-left">Description</th>
                      <th scope="col" className="px-3 py-2 text-right">Qty</th>
                      <th scope="col" className="px-3 py-2 text-left">UOM</th>
                      <th scope="col" className="px-3 py-2 text-right">Unit Price</th>
                      <th scope="col" className="px-3 py-2 text-right">Total (AED)</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {subject.lines?.map((line, idx) => {
                      const price = line.unit_price || line.est_unit_price || 0;
                      const lineTotal = line.line_total || Number(line.qty) * Number(price);
                      return (
                        <tr key={idx}>
                          <td className="px-3 py-2 font-medium text-slate-900">{line.description}</td>
                          <td className="px-3 py-2 text-right text-slate-700">{line.qty}</td>
                          <td className="px-3 py-2 text-slate-500">{line.uom}</td>
                          <td className="px-3 py-2 text-right text-slate-700">{formatMoneyAED(price)}</td>
                          <td className="px-3 py-2 text-right font-medium text-slate-900">
                            {formatMoneyAED(lineTotal)}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          {/* Sourcing Comparison Facts (if comparison exists) */}
          {bundle.comparison && (
            <div className="rounded-lg border border-purple-200 bg-white p-6 shadow-sm">
              <h2 className="text-base font-semibold text-slate-900 mb-2 flex items-center gap-2">
                <GitCompare className="h-4 w-4 text-purple-600" aria-hidden="true" />
                Sourcing & Recommendation Facts
              </h2>
              <p className="text-xs text-slate-500 mb-4">
                Comparison result and scoring evaluated prior to purchase order creation.
              </p>

              {bundle.comparison.explanation && (
                <div className="rounded-md bg-purple-50/70 border border-purple-200 p-3 text-xs text-purple-950 mb-4">
                  <strong className="font-semibold block mb-1">AI Recommendation Summary:</strong>
                  {bundle.comparison.explanation}
                </div>
              )}

              {bundle.comparison.override_reason && (
                <div className="rounded-md bg-rose-50 border border-rose-200 p-3 text-xs text-rose-900 mb-4" data-testid="approval-override-reason">
                  <strong className="font-semibold block mb-1">Buyer Override Justification:</strong>
                  {bundle.comparison.override_reason}
                </div>
              )}

              <div className="text-xs flex gap-4 text-slate-600">
                <Link
                  href={`/comparisons/${bundle.comparison.id}`}
                  className="font-semibold text-blue-600 hover:underline inline-flex items-center gap-1"
                >
                  View Full Sourcing Comparison Matrix →
                </Link>
              </div>
            </div>
          )}
        </div>

        {/* Right Sidebar: Earlier Decisions & Policy Rules */}
        <div className="space-y-6">
          {/* Earlier Approval Steps */}
          <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
            <h2 className="text-sm font-semibold text-slate-900 mb-4 flex items-center gap-2">
              <Clock className="h-4 w-4 text-slate-500" aria-hidden="true" />
              Approval History & Steps
            </h2>

            {!bundle.earlier_decisions || bundle.earlier_decisions.length === 0 ? (
              <p className="text-xs text-slate-500">This is the initial approval tier for this request.</p>
            ) : (
              <div className="space-y-3">
                {bundle.earlier_decisions.map((step) => (
                  <div key={step.step_id} className="border rounded-md p-3 text-xs bg-slate-50">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-slate-900">Step {step.sequence} (Tier {step.tier})</span>
                      <StatusBadge status={step.status} />
                    </div>
                    <p className="mt-1 text-slate-600">
                      Decided by: <strong>{step.decided_by_name || "Approver"}</strong>
                    </p>
                    {step.decided_at && (
                      <p className="text-[11px] text-slate-400">{formatGSTDate(step.decided_at)}</p>
                    )}
                    {step.comment && (
                      <p className="mt-1.5 rounded bg-white p-2 border border-slate-200 text-slate-700 italic">
                        &ldquo;{step.comment}&rdquo;
                      </p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Governance & Compliance */}
          <div className="rounded-lg border border-slate-200 bg-slate-50/70 p-6 text-xs text-slate-600 space-y-2">
            <h3 className="font-bold text-slate-900 flex items-center gap-1.5">
              <ShieldCheck className="h-4 w-4 text-blue-600" aria-hidden="true" />
              Governance Verification
            </h3>
            <p>• Segregation of Duties: Verified creator cannot self-approve.</p>
            <p>• Tiers: Routed according to Demo Holdings procurement policy.</p>
            <p>• Audit: Every decision is recorded into the hash-chained audit trail.</p>
          </div>
        </div>
      </div>

      {/* Reject Reason Dialog */}
      {rejectModalOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
          aria-labelledby="reject-dialog-title"
        >
          <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl border border-slate-200">
            <h3 id="reject-dialog-title" className="text-base font-bold text-slate-900 mb-1 flex items-center gap-2">
              <XCircle className="h-5 w-5 text-rose-600" aria-hidden="true" />
              Reject Commitment (Reason Required)
            </h3>
            <p className="text-xs text-slate-500 mb-4">
              Please enter a justification explaining why this purchase request or order is being rejected.
            </p>

            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleDecision("reject", rejectComment);
              }}
              className="space-y-4"
            >
              <div>
                <label htmlFor="reject-comment-input" className="block text-xs font-medium text-slate-700 mb-1">
                  Rejection Reason *
                </label>
                <textarea
                  id="reject-comment-input"
                  value={rejectComment}
                  onChange={(e) => setRejectComment(e.target.value)}
                  required
                  rows={3}
                  placeholder="Enter rejection comments..."
                  data-testid="reject-comment-input"
                  className="w-full rounded border border-slate-300 p-2 text-xs text-slate-900 focus:outline-none focus:ring-1 focus:ring-rose-500"
                />
              </div>

              <div className="flex justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setRejectModalOpen(false)}
                  className="rounded-md border border-slate-300 px-3.5 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={deciding || !rejectComment.trim()}
                  data-testid="confirm-reject-btn"
                  className="rounded-md bg-rose-600 px-4 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-rose-700 disabled:opacity-50"
                >
                  {deciding ? "Rejecting..." : "Confirm Rejection"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
