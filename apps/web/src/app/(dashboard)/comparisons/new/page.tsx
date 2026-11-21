"use client";

import React, { useState, useEffect, use } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { GitCompare, AlertCircle, CheckCircle2, Loader2, ArrowRight } from "lucide-react";
import { formatMoneyAED, formatGSTDate } from "@/lib/formatters";
import type { DocumentSummary } from "@/lib/documents/types";
import type { PurchaseRequest } from "@/lib/flow/types";

export default function NewComparisonPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialPrId = searchParams.get("pr_id") || "";

  const [prs, setPrs] = useState<PurchaseRequest[]>([]);
  const [selectedPrId, setSelectedPrId] = useState<string>(initialPrId);
  const [quotes, setQuotes] = useState<DocumentSummary[]>([]);
  const [selectedQuoteIds, setSelectedQuoteIds] = useState<string[]>([]);
  const [loadingPrs, setLoadingPrs] = useState(true);
  const [loadingQuotes, setLoadingQuotes] = useState(false);
  const [creating, setCreating] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Load PRs
  useEffect(() => {
    fetch("/api/v1/purchase-requests")
      .then((res) => (res.ok ? res.json() : []))
      .then((data: PurchaseRequest[]) => {
        setPrs(data);
        if (!selectedPrId && data.length > 0) {
          setSelectedPrId(data[0].id);
        }
      })
      .catch(() => {})
      .finally(() => setLoadingPrs(false));
  }, [selectedPrId]);

  // Load quotes for selected PR
  useEffect(() => {
    if (!selectedPrId) {
      setQuotes([]);
      setSelectedQuoteIds([]);
      return;
    }
    setLoadingQuotes(true);
    fetch(`/api/v1/documents?pr_id=${selectedPrId}&doc_type=quote`)
      .then((res) => (res.ok ? res.json() : []))
      .then((data: DocumentSummary[]) => {
        setQuotes(data);
        // By default, select all confirmed quotes
        const confirmed = data.filter((d) => d.status === "confirmed").map((d) => d.id);
        setSelectedQuoteIds(confirmed);
      })
      .catch(() => {})
      .finally(() => setLoadingQuotes(false));
  }, [selectedPrId]);

  const handleToggleQuote = (id: string) => {
    if (selectedQuoteIds.includes(id)) {
      setSelectedQuoteIds(selectedQuoteIds.filter((qid) => qid !== id));
    } else {
      setSelectedQuoteIds([...selectedQuoteIds, id]);
    }
  };

  const confirmedQuotesCount = quotes.filter((q) => q.status === "confirmed").length;
  const canCreate = selectedQuoteIds.length >= 2;

  const handleCreateComparison = async (e: React.FormEvent) => {
    e.preventDefault();
    if (selectedQuoteIds.length < 2) {
      setErrorMsg("At least two confirmed quotes are required to generate a comparison.");
      return;
    }

    try {
      setCreating(true);
      setErrorMsg(null);
      const res = await fetch("/api/v1/comparisons", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Origin: window.location.origin,
        },
        body: JSON.stringify({
          pr_id: selectedPrId,
          quote_document_ids: selectedQuoteIds,
        }),
      });

      if (!res.ok) {
        const problem = await res.json().catch(() => ({}));
        throw new Error(problem.detail || problem.title || `HTTP ${res.status}`);
      }

      const comp = await res.json();
      router.push(`/comparisons/${comp.id}`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to create comparison.";
      setErrorMsg(msg);
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="space-y-6 max-w-3xl">
      <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        <h1 className="text-xl font-bold text-slate-900 flex items-center gap-2">
          <GitCompare className="h-5 w-5 text-purple-600" />
          Create Quote Comparison
        </h1>
        <p className="mt-1 text-xs text-slate-500">
          Select a purchase request and choose at least two confirmed quotation documents to compare side by side.
        </p>
      </div>

      {errorMsg && (
        <div className="rounded-md border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700">
          {errorMsg}
        </div>
      )}

      <form onSubmit={handleCreateComparison} className="space-y-6">
        {/* Step 1: Select Purchase Request */}
        <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
          <label htmlFor="pr-select" className="block text-xs font-semibold text-slate-700 mb-2">
            1. Select Purchase Request *
          </label>
          <select
            id="pr-select"
            value={selectedPrId}
            onChange={(e) => setSelectedPrId(e.target.value)}
            disabled={loadingPrs}
            className="w-full rounded-md border border-slate-300 p-2 text-xs text-slate-900 focus:outline-none focus:ring-1 focus:ring-purple-500"
          >
            {prs.map((pr) => (
              <option key={pr.id} value={pr.id}>
                [{pr.number}] {pr.title} ({formatMoneyAED(pr.total_aed)})
              </option>
            ))}
          </select>
        </div>

        {/* Step 2: Select Quotation Documents */}
        <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-xs font-semibold text-slate-700">
              2. Select Confirmed Quotes (Selected: {selectedQuoteIds.length})
            </h2>
            <span className="text-[11px] text-slate-500 font-medium">
              Minimum 2 confirmed quotes required
            </span>
          </div>

          {loadingQuotes ? (
            <div className="py-6 text-center text-xs text-slate-500">Loading quotes for request...</div>
          ) : quotes.length === 0 ? (
            <div className="rounded-md border border-dashed border-slate-200 p-6 text-center text-xs text-slate-500">
              No quotation documents linked to this purchase request. Go to the request detail page to link quotes.
            </div>
          ) : (
            <div className="space-y-2">
              {quotes.map((q) => {
                const isConfirmed = q.status === "confirmed";
                const isChecked = selectedQuoteIds.includes(q.id);
                return (
                  <label
                    key={q.id}
                    className={`flex items-start gap-3 p-3 rounded-md border cursor-pointer transition-colors ${
                      isChecked
                        ? "bg-purple-50/70 border-purple-300"
                        : "hover:bg-slate-50 border-slate-200"
                    } ${!isConfirmed ? "opacity-60" : ""}`}
                  >
                    <input
                      type="checkbox"
                      data-testid={`quote-select-${q.id}`}
                      checked={isChecked}
                      disabled={!isConfirmed}
                      onChange={() => handleToggleQuote(q.id)}
                      className="mt-0.5 text-purple-600 rounded focus:ring-purple-500"
                    />
                    <div className="flex-1 text-xs">
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-slate-900">
                          Document ID: {q.id.slice(0, 8)}...
                        </span>
                        <span
                          className={`text-[10px] px-2 py-0.5 rounded font-bold uppercase ${
                            isConfirmed ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800"
                          }`}
                        >
                          {q.status}
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-500 mt-0.5">
                        Uploaded {formatGSTDate(q.created_at)}
                      </p>
                      {!isConfirmed && (
                        <p className="text-[11px] text-amber-700 mt-1">
                          Note: Must be verified and confirmed on the review screen before including in a comparison.
                        </p>
                      )}
                    </div>
                  </label>
                );
              })}
            </div>
          )}

          {!canCreate && (
            <div className="mt-4 flex items-center gap-2 rounded-md bg-amber-50 p-3 text-xs text-amber-800 border border-amber-200" data-testid="min-quotes-warning">
              <AlertCircle className="h-4 w-4 text-amber-600 shrink-0" />
              <span>
                Comparison cannot be created: fewer than two confirmed quotes selected ({selectedQuoteIds.length} / 2).
              </span>
            </div>
          )}
        </div>

        <div className="flex justify-end gap-3">
          <button
            type="button"
            onClick={() => router.back()}
            className="rounded-md border border-slate-300 px-4 py-2 text-xs font-medium text-slate-700 hover:bg-slate-50"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={!canCreate || creating}
            data-testid="create-comparison-btn"
            className="inline-flex items-center gap-2 rounded-md bg-purple-600 px-5 py-2 text-xs font-semibold text-white shadow-sm hover:bg-purple-700 disabled:opacity-50"
          >
            {creating ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                <span>Generating Matrix...</span>
              </>
            ) : (
              <>
                <span>Generate Comparison Matrix</span>
                <ArrowRight className="h-4 w-4" />
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
