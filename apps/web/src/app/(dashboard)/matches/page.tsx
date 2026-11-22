"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Layers, Play, AlertTriangle, FileText, CheckCircle2, Loader2 } from "lucide-react";
import { ExceptionQueue } from "@/components/flow/ExceptionQueue";
import { Toast, type ToastState } from "@/components/ui/Toast";
import { formatDocumentTitle } from "@/lib/formatters";
import type { DocumentSummary } from "@/lib/documents/types";
import type { UserPrincipal } from "@/lib/types";

export default function MatchesPage() {
  const router = useRouter();
  const [user, setUser] = useState<UserPrincipal | null>(null);
  const [invoices, setInvoices] = useState<DocumentSummary[]>([]);
  const [selectedInvoiceId, setSelectedInvoiceId] = useState<string>("");
  const [runningMatch, setRunningMatch] = useState(false);
  const [toast, setToast] = useState<ToastState | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/v1/me")
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => setUser(data))
      .catch(() => {});

    fetch("/api/v1/documents?doc_type=invoice&status=confirmed&suspicious=false")
      .then((res) => (res.ok ? res.json() : []))
      .then((data: DocumentSummary[]) => {
        const eligible = data.filter((d) => d.status === "confirmed" && !d.suspicious);
        setInvoices(eligible);
        if (eligible.length > 0) {
          setSelectedInvoiceId(eligible[0].id);
        } else {
          setSelectedInvoiceId("");
        }
      })
      .catch(() => {});
  }, []);

  const handleRunMatch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedInvoiceId) return;

    try {
      setRunningMatch(true);
      setErrorMsg(null);
      const res = await fetch("/api/v1/matches", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Origin: window.location.origin,
        },
        body: JSON.stringify({ invoice_document_id: selectedInvoiceId }),
      });

      if (!res.ok) {
        const problem = await res.json().catch(() => ({}));
        throw new Error(problem.detail || problem.title || `HTTP ${res.status}`);
      }

      const match = await res.json();
      setToast({
        type: "success",
        title: "Match Evaluated",
        message: `Match status: ${match.overall_status}.`,
      });
      router.push(`/matches/${match.id}`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to run three-way match.";
      setErrorMsg(msg);
      setToast({ type: "error", title: "Match Error", message: msg });
    } finally {
      setRunningMatch(false);
    }
  };

  const isBuyer = user?.roles.includes("buyer");

  return (
    <div className="space-y-8">
      {toast && (
        <Toast
          type={toast.type}
          title={toast.title}
          message={toast.message}
          onClose={() => setToast(null)}
        />
      )}

      {/* Top Banner & Match Execution Section */}
      <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-xl font-bold text-slate-900 flex items-center gap-2">
              <Layers className="h-5 w-5 text-blue-600" />
              Three-Way Match Automation
            </h1>
            <p className="mt-1 text-xs text-slate-500">
              Deterministic reconciliation of supplier tax invoices against approved purchase orders and delivery notes.
            </p>
          </div>
        </div>

        {/* Run Match Form (Buyer) */}
        {isBuyer && (
          <div className="mt-6 pt-6 border-t border-slate-100">
            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">
              Run Three-Way Match on Confirmed Invoice
            </h2>

            {errorMsg && (
              <div className="mb-3 rounded border border-rose-200 bg-rose-50 p-2.5 text-xs text-rose-700">
                {errorMsg}
              </div>
            )}

            <form onSubmit={handleRunMatch} className="flex flex-col sm:flex-row items-center gap-3">
              <select
                aria-label="Select Invoice Document"
                value={selectedInvoiceId}
                onChange={(e) => setSelectedInvoiceId(e.target.value)}
                data-testid="invoice-select"
                className="w-full sm:w-96 rounded-md border border-slate-300 p-2 text-xs text-slate-900 focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                {invoices.length === 0 ? (
                  <option value="">No confirmed invoices available</option>
                ) : (
                  invoices.map((inv) => (
                    <option key={inv.id} value={inv.id}>
                      {formatDocumentTitle(inv, "Invoice")}
                    </option>
                  ))
                )}
              </select>

              <button
                type="submit"
                disabled={runningMatch || !selectedInvoiceId}
                data-testid="run-match-btn"
                className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-blue-700 disabled:opacity-50 shrink-0"
              >
                {runningMatch ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span>Evaluating Match...</span>
                  </>
                ) : (
                  <>
                    <Play className="h-4 w-4" />
                    <span>Run Match</span>
                  </>
                )}
              </button>
            </form>
          </div>
        )}
      </div>

      {/* Exception Queue */}
      {user && (
        <ExceptionQueue
          userRoles={user.roles}
          onToast={(type, title, message) => setToast({ type, title, message })}
        />
      )}
    </div>
  );
}
