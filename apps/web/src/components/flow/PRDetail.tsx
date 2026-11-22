"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ShoppingCart,
  Send,
  GitCompare,
  FileText,
  Clock,
  UserCheck,
  AlertCircle,
  CheckCircle2,
  Plus,
} from "lucide-react";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { formatMoneyAED, formatGSTDate, formatDocumentTitle } from "@/lib/formatters";
import type { PurchaseRequest } from "@/lib/flow/types";
import type { DocumentSummary } from "@/lib/documents/types";

export interface PRDetailProps {
  pr: PurchaseRequest;
  userRoles: string[];
  userId: string;
  onToast?: (type: "success" | "error" | "info" | "warning", title: string, message?: string) => void;
}

export const PRDetail: React.FC<PRDetailProps> = ({ pr: initialPr, userRoles, userId, onToast }) => {
  const router = useRouter();
  const [pr, setPr] = useState<PurchaseRequest>(initialPr);
  const [submitting, setSubmitting] = useState(false);
  const [quotes, setQuotes] = useState<DocumentSummary[]>([]);
  const [availableQuotes, setAvailableQuotes] = useState<DocumentSummary[]>([]);
  const [linkModalOpen, setLinkModalOpen] = useState(false);
  const [linkingDocId, setLinkingDocId] = useState<string>("");
  const [linking, setLinking] = useState(false);

  const isCreator = pr.requester_id === userId;
  const isDraft = pr.status === "draft";
  const canSubmit = isDraft && (isCreator || userRoles.includes("buyer"));
  const isBuyer = userRoles.includes("buyer");

  const loadLinkedQuotes = useCallback(() => {
    fetch(`/api/v1/documents?pr_id=${pr.id}&doc_type=quote`)
      .then((res) => (res.ok ? res.json() : []))
      .then((data: DocumentSummary[]) => setQuotes(data))
      .catch(() => {});
  }, [pr.id]);

  useEffect(() => {
    loadLinkedQuotes();
  }, [loadLinkedQuotes]);

  const loadAvailableQuotes = () => {
    fetch(`/api/v1/documents?doc_type=quote&status=confirmed`)
      .then((res) => (res.ok ? res.json() : []))
      .then((data: DocumentSummary[]) => {
        // Exclude already linked to this PR
        setAvailableQuotes(data.filter((d) => d.pr_id !== pr.id));
      })
      .catch(() => {});
  };

  const handleOpenLinkModal = () => {
    loadAvailableQuotes();
    setLinkModalOpen(true);
  };

  const handleLinkQuote = async () => {
    if (!linkingDocId) return;
    try {
      setLinking(true);
      // Link quote document to this PR
      const res = await fetch(`/api/v1/documents/${linkingDocId}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Origin: window.location.origin,
        },
        body: JSON.stringify({ pr_id: pr.id }),
      });
      if (!res.ok) {
        throw new Error("Failed to link quote.");
      }
      onToast?.("success", "Quotation Linked", "Quotation document linked to this purchase request.");
      setLinkModalOpen(false);
      setLinkingDocId("");
      loadLinkedQuotes();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Error linking quote.";
      onToast?.("error", "Error", msg);
    } finally {
      setLinking(false);
    }
  };

  const handleSubmitPR = async () => {
    try {
      setSubmitting(true);
      const res = await fetch(`/api/v1/purchase-requests/${pr.id}/submit`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Origin: window.location.origin,
        },
      });

      if (!res.ok) {
        const problem = await res.json().catch(() => ({}));
        throw new Error(problem.detail || problem.title || `HTTP ${res.status}`);
      }

      const updated = await res.json();
      setPr(updated);
      onToast?.("success", "Submitted for Approval", `Request ${updated.number} submitted into approval routing.`);
      router.refresh();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to submit request.";
      onToast?.("error", "Submission Error", msg);
    } finally {
      setSubmitting(false);
    }
  };

  const confirmedQuotes = quotes.filter((q) => q.status === "confirmed");
  const hasEnoughQuotes = confirmedQuotes.length >= 2;

  return (
    <div className="space-y-6">
      {/* Top Header Card */}
      <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="flex items-center gap-3">
              <span className="font-mono text-sm font-bold text-blue-600">{pr.number}</span>
              <StatusBadge status={pr.status} />
            </div>
            <h1 className="mt-1 text-xl font-bold text-slate-900">{pr.title}</h1>
            <p className="mt-1 text-xs text-slate-500">
              Created {formatGSTDate(pr.created_at)}
              {pr.submitted_at && ` • Submitted ${formatGSTDate(pr.submitted_at)}`}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {canSubmit && (
              <button
                type="button"
                onClick={handleSubmitPR}
                disabled={submitting}
                data-testid="submit-pr-btn"
                className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-blue-700 disabled:opacity-50"
              >
                <Send className="h-4 w-4" />
                <span>{submitting ? "Submitting..." : "Submit for Approval"}</span>
              </button>
            )}

            {isBuyer && (
              <Link
                href={`/comparisons/new?pr_id=${pr.id}`}
                className={`inline-flex items-center gap-2 rounded-md px-4 py-2 text-xs font-semibold shadow-sm ${
                  hasEnoughQuotes
                    ? "bg-purple-600 text-white hover:bg-purple-700"
                    : "bg-slate-100 text-slate-400 cursor-not-allowed pointer-events-none"
                }`}
                data-testid="compare-quotes-link"
              >
                <GitCompare className="h-4 w-4" />
                <span>Compare Quotes</span>
              </Link>
            )}
          </div>
        </div>

        {/* Current Routing Status */}
        {pr.status === "submitted" && (
          <div className="mt-4 rounded-md border border-blue-200 bg-blue-50/70 p-3 text-xs text-blue-800 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Clock className="h-4 w-4 text-blue-600" />
              <span>
                Status: Pending Approval • Waiting on:{" "}
                <strong className="font-semibold text-blue-900">
                  {pr.current_approver || "Assigned Approver"}
                </strong>
              </span>
            </div>
            <span className="text-[11px] text-blue-700">Tier rules applied</span>
          </div>
        )}

        {pr.status === "approved" && (
          <div className="mt-4 rounded-md border border-emerald-200 bg-emerald-50 p-3 text-xs text-emerald-800 flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-emerald-600" />
            <span>This request has been fully approved by the department manager.</span>
          </div>
        )}
      </div>

      {/* Approval History Section */}
      {pr.approval_steps && pr.approval_steps.length > 0 && (
        <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm" data-testid="approval-history-section">
          <h2 className="text-base font-semibold text-slate-900 mb-4 flex items-center gap-2">
            <UserCheck className="h-4 w-4 text-emerald-600" />
            Approval History ({pr.approval_steps.length})
          </h2>
          <div className="space-y-3">
            {pr.approval_steps.map((step) => (
              <div
                key={step.id || step.sequence}
                className="flex items-center justify-between rounded-md border border-slate-200 p-3 hover:bg-slate-50/50"
                data-testid={`approval-step-${step.sequence}`}
              >
                <div className="flex items-center gap-3">
                  <div className="flex h-7 w-7 items-center justify-center rounded-full bg-slate-100 text-xs font-bold text-slate-700">
                    {step.sequence}
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-semibold text-slate-900" data-testid="approver-name">
                        {step.approver_name || step.decided_by_name || "Assigned Approver"}
                      </span>
                      {step.department_name && (
                        <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-600">
                          {step.department_name}
                        </span>
                      )}
                    </div>
                    {step.comment && (
                      <p className="mt-0.5 text-[11px] text-slate-600 italic">
                        &ldquo;{step.comment}&rdquo;
                      </p>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <StatusBadge status={step.status} size="sm" />
                  {step.decided_at ? (
                    <span className="text-xs text-slate-500 font-mono" data-testid="decided-at">
                      {formatGSTDate(step.decided_at)}
                    </span>
                  ) : (
                    <span className="text-xs text-slate-400 italic">Pending</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Requested Items Table */}
      <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-base font-semibold text-slate-900 mb-4 flex items-center gap-2">
          <ShoppingCart className="h-4 w-4 text-slate-500" />
          Line Items ({pr.lines?.length || 0})
        </h2>

        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-xs">
            <thead className="bg-slate-50 text-[11px] font-semibold uppercase text-slate-500">
              <tr>
                <th className="px-3 py-2 text-left">Item Description</th>
                <th className="px-3 py-2 text-right">Qty</th>
                <th className="px-3 py-2 text-left">UOM</th>
                <th className="px-3 py-2 text-right">Est. Unit Price</th>
                <th className="px-3 py-2 text-right">Total (AED)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {pr.lines?.map((line, idx) => {
                const total = (Number(line.qty) || 0) * (Number(line.est_unit_price) || 0);
                return (
                  <tr key={line.id || idx}>
                    <td className="px-3 py-2.5 font-medium text-slate-900">{line.description}</td>
                    <td className="px-3 py-2.5 text-right text-slate-700">{line.qty}</td>
                    <td className="px-3 py-2.5 text-slate-600">{line.uom}</td>
                    <td className="px-3 py-2.5 text-right text-slate-700">
                      {formatMoneyAED(line.est_unit_price)}
                    </td>
                    <td className="px-3 py-2.5 text-right font-medium text-slate-900">
                      {formatMoneyAED(total)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
            <tfoot>
              <tr className="border-t-2 border-slate-200 bg-slate-50 font-bold text-slate-900">
                <td colSpan={4} className="px-3 py-3 text-right">
                  Total Request Value:
                </td>
                <td className="px-3 py-3 text-right text-sm text-blue-700" data-testid="pr-total-val">
                  {formatMoneyAED(pr.total_aed)}
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>

      {/* Linked Quotations Section (US-08) */}
      <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-base font-semibold text-slate-900 flex items-center gap-2">
              <FileText className="h-4 w-4 text-purple-600" />
              Linked Quotations ({quotes.length})
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              At least two confirmed quotes are required to generate an automated side-by-side comparison.
            </p>
          </div>

          {isBuyer && (
            <button
              type="button"
              onClick={handleOpenLinkModal}
              className="inline-flex items-center gap-1.5 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 shadow-sm hover:bg-slate-50"
            >
              <Plus className="h-3.5 w-3.5" />
              Link Quote Document
            </button>
          )}
        </div>

        {quotes.length === 0 ? (
          <div className="rounded-md border border-dashed border-slate-200 bg-slate-50 p-6 text-center text-xs text-slate-500">
            No quotation documents linked to this purchase request yet.
          </div>
        ) : (
          <div className="space-y-2">
            {quotes.map((q) => {
              const title = formatDocumentTitle(q, "Quotation Document");
              return (
                <div
                  key={q.id}
                  className="flex items-center justify-between rounded-md border border-slate-200 p-3 hover:bg-slate-50/50"
                >
                  <div className="flex items-center gap-3">
                    <FileText className="h-4 w-4 text-purple-600 flex-shrink-0" />
                    <div>
                      <Link
                        href={`/documents/${q.id}`}
                        className="text-xs font-semibold text-blue-600 hover:underline"
                        title={title}
                      >
                        {title}
                      </Link>
                      <p className="text-[11px] text-slate-500">
                        Uploaded {formatGSTDate(q.created_at)}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <StatusBadge status={q.status} />
                    <Link
                      href={`/documents/${q.id}`}
                      className="rounded border border-slate-200 px-2.5 py-1 text-[11px] font-medium text-slate-600 hover:bg-slate-100"
                    >
                      View Extraction
                    </Link>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {!hasEnoughQuotes && (
          <div className="mt-4 flex items-center gap-2 rounded-md bg-amber-50 p-3 text-xs text-amber-800 border border-amber-200">
            <AlertCircle className="h-4 w-4 text-amber-600 shrink-0" />
            <span>
              Comparison cannot be created: currently {confirmedQuotes.length} confirmed quote(s) linked.
              Link at least 2 confirmed quotations to unlock quote comparison.
            </span>
          </div>
        )}
      </div>

      {/* Link Quote Modal */}
      {linkModalOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
        >
          <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl border border-slate-200">
            <h3 className="text-base font-bold text-slate-900 mb-2">Link Confirmed Quotation</h3>
            <p className="text-xs text-slate-500 mb-4">
              Select an uploaded and confirmed quote document to link to this purchase request.
            </p>

            {availableQuotes.length === 0 ? (
              <p className="text-xs text-slate-500 py-4 text-center">
                No unlinked confirmed quotations found. Please upload and confirm quote documents in the Documents tab first.
              </p>
            ) : (
              <div className="max-h-60 overflow-y-auto space-y-2 border rounded-md p-2">
                {availableQuotes.map((aq) => (
                  <label
                    key={aq.id}
                    className={`flex items-start gap-3 p-2 rounded cursor-pointer ${
                      linkingDocId === aq.id ? "bg-purple-50 border border-purple-200" : "hover:bg-slate-50"
                    }`}
                  >
                    <input
                      type="radio"
                      name="quote_doc"
                      value={aq.id}
                      checked={linkingDocId === aq.id}
                      onChange={() => setLinkingDocId(aq.id)}
                      className="mt-1 h-4 w-4 text-purple-600"
                    />
                    <div className="flex-1 text-xs">
                      <span className="font-semibold text-slate-900">
                        {formatDocumentTitle(aq, "Quotation Document")}
                      </span>
                      <p className="text-[11px] text-slate-500">
                        Uploaded {formatGSTDate(aq.created_at)}
                      </p>
                    </div>
                  </label>
                ))}
              </div>
            )}

            <div className="mt-6 flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setLinkModalOpen(false)}
                className="rounded-md border border-slate-300 px-3.5 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleLinkQuote}
                disabled={!linkingDocId || linking}
                className="rounded-md bg-purple-600 px-4 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-purple-700 disabled:opacity-50"
              >
                {linking ? "Linking..." : "Link Quotation"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
