"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  ArrowUpRight,
  Check,
  X,
  Clock,
  Filter,
  CheckCircle2,
  XCircle,
  ShieldAlert,
} from "lucide-react";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { formatMoneyAED, formatGSTDate } from "@/lib/formatters";
import type { MatchException } from "@/lib/flow/types";

export interface ExceptionQueueProps {
  userRoles: string[];
  onToast?: (type: "success" | "error" | "info" | "warning", title: string, message?: string) => void;
}

export const ExceptionQueue: React.FC<ExceptionQueueProps> = ({ userRoles, onToast }) => {
  const [exceptions, setExceptions] = useState<MatchException[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>("unresolved");

  // Action Dialog state
  const [activeException, setActiveException] = useState<MatchException | null>(null);
  const [actionType, setActionType] = useState<"accept" | "escalate" | "reject" | null>(null);
  const [reasonInput, setReasonInput] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const isBuyer = userRoles.includes("buyer");
  const isManager = userRoles.includes("manager");

  const activeReqIdRef = useRef(0);

  const loadExceptions = useCallback(() => {
    const reqId = ++activeReqIdRef.current;
    setLoading(true);
    const query = statusFilter !== "all" ? `?status=${statusFilter}` : "";
    fetch(`/api/v1/exceptions${query}`)
      .then((res) => (res.ok ? res.json() : []))
      .then((data: MatchException[]) => {
        if (reqId === activeReqIdRef.current) {
          setExceptions(data);
        }
      })
      .catch(() => {
        if (reqId === activeReqIdRef.current) {
          onToast?.("error", "Error", "Failed to load match exceptions.");
        }
      })
      .finally(() => {
        if (reqId === activeReqIdRef.current) {
          setLoading(false);
        }
      });
  }, [statusFilter, onToast]);

  useEffect(() => {
    loadExceptions();
  }, [loadExceptions]);

  const openActionModal = (exc: MatchException, type: "accept" | "escalate" | "reject") => {
    setActiveException(exc);
    setActionType(type);
    setReasonInput("");
    setErrorMsg(null);
  };

  const handleResolveException = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeException || !actionType) return;
    if (!reasonInput.trim() || reasonInput.trim().length < 3) {
      setErrorMsg("A resolution reason of at least 3 characters is required.");
      return;
    }

    try {
      setSubmitting(true);
      setErrorMsg(null);
      const res = await fetch(`/api/v1/exceptions/${activeException.id}/resolve`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Origin: window.location.origin,
        },
        body: JSON.stringify({
          action: actionType,
          reason: reasonInput.trim(),
        }),
      });

      if (!res.ok) {
        const problem = await res.json().catch(() => ({}));
        throw new Error(problem.detail || problem.title || `HTTP ${res.status}`);
      }

      onToast?.(
        actionType === "reject" ? "warning" : "success",
        `Exception ${actionType === "escalate" ? "Escalated" : "Resolved"}`,
        `Exception marked as ${actionType}ed.`
      );
      setActiveException(null);
      setActionType(null);
      loadExceptions();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to resolve exception.";
      setErrorMsg(msg);
      onToast?.("error", "Resolution Error", msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header & Controls */}
      <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-xl font-bold text-slate-900 flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-amber-600" />
              Three-Way Match Exception Queue
            </h1>
            <p className="mt-1 text-xs text-slate-500">
              Exceptions identified during three-way invoice reconciliation. Buyer can accept within AED 500 policy (excluding over-billing) or escalate to Manager.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <label htmlFor="filter-status-queue" className="text-xs font-semibold text-slate-600">
              Filter:
            </label>
            <select
              id="filter-status-queue"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-xs text-slate-900 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value="unresolved">Needs Action (Open & Escalated)</option>
              <option value="open">Open Exceptions</option>
              <option value="escalated">Escalated to Manager</option>
              <option value="accepted">Accepted</option>
              <option value="rejected">Rejected</option>
              <option value="all">All Statuses</option>
            </select>
          </div>
        </div>
      </div>

      {/* Exceptions List */}
      <div className="rounded-lg border border-slate-200 bg-white shadow-sm overflow-hidden">
        {loading ? (
          <div className="py-12 text-center text-xs text-slate-500">Loading exceptions...</div>
        ) : exceptions.length === 0 ? (
          <div className="py-12 text-center text-xs text-slate-500">
            No exceptions found in this queue.
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {exceptions.map((exc) => {
              const isOverBilledQty = exc.kind === "qty_variance";
              const isOverBuyerLimit = Number(exc.amount_impact_aed) > 500;
              const buyerAcceptBlocked = isOverBilledQty || isOverBuyerLimit;

              const buyerAcceptDisabledReason = isOverBilledQty
                ? "Over-billed quantity cannot be accepted by Buyer per policy. Must be escalated to Manager."
                : isOverBuyerLimit
                ? "Amount impact exceeds Buyer AED 500 tolerance policy. Must be escalated to Manager."
                : null;

              return (
                <div key={exc.id} className="p-5 hover:bg-slate-50/50 transition-colors" data-testid={`exception-row-${exc.id}`}>
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-[11px] font-semibold uppercase px-2 py-0.5 rounded bg-slate-100 text-slate-700">
                          {exc.kind.replace("_", " ")}
                        </span>
                        <StatusBadge status={exc.status} />
                        <span className="text-xs font-bold text-slate-900">
                          Variance Impact: {formatMoneyAED(exc.amount_impact_aed)}
                        </span>
                      </div>
                      <h2 className="mt-1.5 text-sm font-semibold text-slate-900" data-testid="exception-reason-text">
                        {exc.reason}
                      </h2>
                      <p className="mt-1 text-xs text-slate-500">
                        Match ID:{" "}
                        <Link href={`/matches/${exc.match_id}`} className="text-blue-600 hover:underline">
                          {exc.match_id.slice(0, 8)}...
                        </Link>
                        {" • "}
                        Logged {formatGSTDate(exc.created_at)}
                      </p>

                      {exc.resolution_reason && (
                        <div className="mt-2 text-xs rounded bg-slate-50 p-2 border border-slate-200 text-slate-700">
                          <strong className="font-semibold text-slate-900">Resolution Note:</strong> &ldquo;{exc.resolution_reason}&rdquo;
                        </div>
                      )}
                    </div>

                    {/* Action Buttons */}
                    <div className="flex flex-wrap items-center gap-2">
                      {/* Buyer Actions */}
                      {isBuyer && exc.status === "open" && (
                        <>
                          <button
                            type="button"
                            onClick={() => openActionModal(exc, "accept")}
                            disabled={buyerAcceptBlocked}
                            title={buyerAcceptDisabledReason || "Accept exception within policy"}
                            data-testid="buyer-accept-exception-btn"
                            className="inline-flex items-center gap-1.5 rounded-md bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-emerald-700 disabled:bg-slate-200 disabled:text-slate-400 disabled:cursor-not-allowed"
                          >
                            <Check className="h-3.5 w-3.5" />
                            <span>Accept</span>
                          </button>

                          <button
                            type="button"
                            onClick={() => openActionModal(exc, "escalate")}
                            data-testid="buyer-escalate-exception-btn"
                            className="inline-flex items-center gap-1.5 rounded-md border border-purple-300 bg-purple-50 px-3 py-1.5 text-xs font-semibold text-purple-700 shadow-sm hover:bg-purple-100"
                          >
                            <ArrowUpRight className="h-3.5 w-3.5" />
                            <span>Escalate to Manager</span>
                          </button>
                        </>
                      )}

                      {/* Manager Actions on Escalated Exceptions */}
                      {isManager && exc.status === "escalated" && (
                        <>
                          <button
                            type="button"
                            onClick={() => openActionModal(exc, "accept")}
                            data-testid="manager-accept-exception-btn"
                            className="inline-flex items-center gap-1.5 rounded-md bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-emerald-700"
                          >
                            <Check className="h-3.5 w-3.5" />
                            <span>Accept (Manager)</span>
                          </button>

                          <button
                            type="button"
                            onClick={() => openActionModal(exc, "reject")}
                            data-testid="manager-reject-exception-btn"
                            className="inline-flex items-center gap-1.5 rounded-md border border-rose-300 bg-rose-50 px-3 py-1.5 text-xs font-semibold text-rose-700 shadow-sm hover:bg-rose-100"
                          >
                            <X className="h-3.5 w-3.5" />
                            <span>Reject & Block Payment</span>
                          </button>
                        </>
                      )}
                    </div>
                  </div>

                  {/* Policy restriction note for buyer */}
                  {isBuyer && exc.status === "open" && buyerAcceptDisabledReason && (
                    <div className="mt-2 text-[11px] text-amber-700 flex items-center gap-1" data-testid="buyer-disabled-notice">
                      <ShieldAlert className="h-3.5 w-3.5 shrink-0" />
                      <span>{buyerAcceptDisabledReason}</span>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Resolution Dialog */}
      {activeException && actionType && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
        >
          <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl border border-slate-200">
            <h3 className="text-base font-bold text-slate-900 mb-1">
              {actionType === "accept"
                ? "Accept Exception"
                : actionType === "escalate"
                ? "Escalate to Department Manager"
                : "Reject Exception"}
            </h3>
            <p className="text-xs text-slate-500 mb-3">
              {activeException.reason} • Impact: {formatMoneyAED(activeException.amount_impact_aed)}
            </p>

            {errorMsg && (
              <div className="mb-3 rounded border border-rose-200 bg-rose-50 p-2 text-xs text-rose-700">
                {errorMsg}
              </div>
            )}

            <form onSubmit={handleResolveException} className="space-y-4 text-xs">
              <div>
                <label htmlFor="resolution-reason-input" className="block font-medium text-slate-700 mb-1">
                  Resolution Justification / Audit Reason *
                </label>
                <textarea
                  id="resolution-reason-input"
                  value={reasonInput}
                  onChange={(e) => setReasonInput(e.target.value)}
                  rows={3}
                  required
                  placeholder={`Enter reason for ${actionType}ing this exception...`}
                  data-testid="exception-resolve-reason-input"
                  className="w-full rounded border border-slate-300 p-2 text-slate-900 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>

              <div className="flex justify-end gap-3">
                <button
                  type="button"
                  onClick={() => {
                    setActiveException(null);
                    setActionType(null);
                  }}
                  className="rounded-md border border-slate-300 px-3.5 py-1.5 font-medium text-slate-700 hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting || !reasonInput.trim()}
                  data-testid="confirm-resolve-exception-btn"
                  className="rounded-md bg-blue-600 px-4 py-1.5 font-semibold text-white shadow-sm hover:bg-blue-700 disabled:opacity-50"
                >
                  {submitting ? "Submitting..." : "Submit Resolution"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
