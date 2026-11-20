"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  GitCompare,
  Sparkles,
  Award,
  AlertTriangle,
  CheckCircle,
  FileText,
  Sliders,
  ArrowRight,
  ShieldAlert,
  Loader2,
  Check,
  Edit2,
} from "lucide-react";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { formatMoneyAED, formatGSTDate } from "@/lib/formatters";
import type { Comparison, ComparisonQuote, ComparisonPairing } from "@/lib/flow/types";

export interface ComparisonViewProps {
  comparison: Comparison;
  prTitle?: string;
  prNumber?: string;
  userRoles: string[];
  onToast?: (type: "success" | "error" | "info" | "warning", title: string, message?: string) => void;
}

export const ComparisonView: React.FC<ComparisonViewProps> = ({
  comparison: initialComp,
  prTitle,
  prNumber,
  userRoles,
  onToast,
}) => {
  const router = useRouter();
  const [comp, setComp] = useState<Comparison>(initialComp);

  // Weights state (cost=60, delivery=20, payment=10, completeness=10)
  const [weights, setWeights] = useState({
    cost: comp.weights?.cost ?? 60,
    delivery: comp.weights?.delivery ?? 20,
    payment: comp.weights?.payment ?? 10,
    completeness: comp.weights?.completeness ?? 10,
  });
  const [savingWeights, setSavingWeights] = useState(false);
  const [generatingRec, setGeneratingRec] = useState(false);

  // Decision dialog state
  const [decisionModalOpen, setDecisionModalOpen] = useState(false);
  const [selectedVendorId, setSelectedVendorId] = useState<string>(
    comp.chosen_vendor_id || comp.recommended_vendor_id || ""
  );
  const [overrideReason, setOverrideReason] = useState<string>(comp.override_reason || "");
  const [submittingDecision, setSubmittingDecision] = useState(false);
  const [decisionError, setDecisionError] = useState<string | null>(null);

  // PO creation state
  const [creatingPO, setCreatingPO] = useState(false);

  const isBuyer = userRoles.includes("buyer");
  const weightsTotal = weights.cost + weights.delivery + weights.payment + weights.completeness;
  const weightsValid = weightsTotal === 100;

  const isRecommended = selectedVendorId === comp.recommended_vendor_id;
  const overrideRequired = !isRecommended && Boolean(comp.recommended_vendor_id);
  const overrideValid = !overrideRequired || (overrideReason.trim().length >= 10);

  // Update Weights
  const handleSaveWeights = async () => {
    if (!weightsValid) return;
    try {
      setSavingWeights(true);
      const res = await fetch(`/api/v1/comparisons/${comp.id}/weights`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Origin: window.location.origin,
        },
        body: JSON.stringify(weights),
      });
      if (!res.ok) {
        const problem = await res.json().catch(() => ({}));
        throw new Error(problem.detail || "Failed to update weights.");
      }
      const updated = await res.json();
      setComp(updated);
      onToast?.("success", "Weights Updated", "Scoring recalculated with updated weights.");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Error updating weights.";
      onToast?.("error", "Error", msg);
    } finally {
      setSavingWeights(false);
    }
  };

  // Generate / Refresh Recommendation
  const handleGenerateRecommendation = async () => {
    try {
      setGeneratingRec(true);
      const res = await fetch(`/api/v1/comparisons/${comp.id}/recommendation`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Origin: window.location.origin,
        },
      });
      if (!res.ok) {
        const problem = await res.json().catch(() => ({}));
        throw new Error(problem.detail || "Failed to generate recommendation.");
      }
      const rec = await res.json();
      // Fetch full comparison refresh
      const refreshedRes = await fetch(`/api/v1/comparisons/${comp.id}`);
      if (refreshedRes.ok) {
        const fullComp = await refreshedRes.json();
        setComp(fullComp);
        if (fullComp.recommended_vendor_id) {
          setSelectedVendorId(fullComp.recommended_vendor_id);
        }
      }
      onToast?.("success", "Recommendation Ready", `Recommended vendor: ${rec.winner_name}`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Error generating recommendation.";
      onToast?.("error", "Error", msg);
    } finally {
      setGeneratingRec(false);
    }
  };

  // Record Vendor Decision
  const handleSaveDecision = async (e: React.FormEvent) => {
    e.preventDefault();
    if (overrideRequired && overrideReason.trim().length < 10) {
      setDecisionError("US-10: An override reason of at least 10 characters is required when choosing a vendor other than the recommendation.");
      return;
    }

    try {
      setSubmittingDecision(true);
      setDecisionError(null);
      const res = await fetch(`/api/v1/comparisons/${comp.id}/decision`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Origin: window.location.origin,
        },
        body: JSON.stringify({
          vendor_id: selectedVendorId,
          override_reason: overrideRequired ? overrideReason.trim() : undefined,
        }),
      });

      if (!res.ok) {
        const problem = await res.json().catch(() => ({}));
        throw new Error(problem.detail || problem.title || `HTTP ${res.status}`);
      }

      const updated = await res.json();
      setComp(updated);
      setDecisionModalOpen(false);
      onToast?.("success", "Vendor Decision Recorded", "Winning vendor selected. You can now generate the purchase order.");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to record decision.";
      setDecisionError(msg);
      onToast?.("error", "Error", msg);
    } finally {
      setSubmittingDecision(false);
    }
  };

  // Create Purchase Order from Decided Comparison
  const handleCreatePO = async () => {
    try {
      setCreatingPO(true);
      const res = await fetch("/api/v1/purchase-orders", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Origin: window.location.origin,
        },
        body: JSON.stringify({ comparison_id: comp.id }),
      });

      if (!res.ok) {
        const problem = await res.json().catch(() => ({}));
        throw new Error(problem.detail || problem.title || `HTTP ${res.status}`);
      }

      const po = await res.json();
      onToast?.("success", "Purchase Order Created", `PO ${po.number} drafted successfully.`);
      router.push(`/purchase-orders/${po.id}`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to create PO.";
      onToast?.("error", "PO Creation Error", msg);
    } finally {
      setCreatingPO(false);
    }
  };

  const quotes = comp.quotes || [];
  const vendorScores = comp.scores?.vendors || {};

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="flex items-center gap-3">
              <span className="font-mono text-xs uppercase bg-purple-100 text-purple-700 px-2 py-0.5 rounded font-bold">
                Quote Comparison
              </span>
              <StatusBadge status={comp.status} />
            </div>
            <h1 className="mt-1 text-xl font-bold text-slate-900">
              Comparison for {prNumber || "Purchase Request"}
            </h1>
            <p className="mt-1 text-xs text-slate-500">
              {prTitle ? `${prTitle} • ` : ""}
              Created {formatGSTDate(comp.created_at)}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {isBuyer && (
              <>
                <button
                  type="button"
                  onClick={handleGenerateRecommendation}
                  disabled={generatingRec}
                  data-testid="generate-rec-btn"
                  className="inline-flex items-center gap-2 rounded-md bg-purple-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-purple-700 disabled:opacity-50"
                >
                  <Sparkles className="h-4 w-4" />
                  <span>{generatingRec ? "Calculating..." : "Compute Recommendation"}</span>
                </button>

                <button
                  type="button"
                  onClick={() => setDecisionModalOpen(true)}
                  data-testid="vendor-decision-btn"
                  className="inline-flex items-center gap-2 rounded-md border border-purple-300 bg-purple-50 px-4 py-2 text-xs font-semibold text-purple-700 hover:bg-purple-100"
                >
                  <Award className="h-4 w-4" />
                  <span>{comp.chosen_vendor_id ? "Change Vendor Choice" : "Select Winning Vendor"}</span>
                </button>
              </>
            )}

            {comp.status === "decided" && isBuyer && (
              <button
                type="button"
                onClick={handleCreatePO}
                disabled={creatingPO}
                data-testid="create-po-from-comp-btn"
                className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-blue-700 disabled:opacity-50"
              >
                <ArrowRight className="h-4 w-4" />
                <span>{creatingPO ? "Drafting PO..." : "Create PO Draft"}</span>
              </button>
            )}
          </div>
        </div>

        {/* Warnings / Gaps Banner (US-12) */}
        {comp.flags && comp.flags.length > 0 && (
          <div className="mt-4 rounded-md border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900 flex items-start gap-2">
            <AlertTriangle className="h-4 w-4 text-amber-600 shrink-0 mt-0.5" />
            <div>
              <strong className="font-semibold">Comparison Flags & Gaps Detected (US-12):</strong>
              <ul className="mt-1 list-disc list-inside space-y-0.5 text-amber-800">
                {comp.flags.map((flag, idx) => (
                  <li key={idx}>{flag}</li>
                ))}
              </ul>
            </div>
          </div>
        )}
      </div>

      {/* AI Recommendation Banner (US-09) */}
      {comp.recommended_vendor_id && (
        <div className="rounded-lg border border-purple-200 bg-gradient-to-r from-purple-50 to-indigo-50 p-6 shadow-sm" data-testid="recommendation-banner">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-purple-600 text-white shadow-sm">
                <Award className="h-6 w-6" />
              </div>
              <div>
                <span className="text-[11px] font-bold uppercase tracking-wider text-purple-700">
                  Recommended Vendor Selection (US-09)
                </span>
                <h2 className="text-lg font-bold text-slate-900" data-testid="recommended-vendor-name">
                  {quotes.find((q) => q.vendor_id === comp.recommended_vendor_id)?.vendor_name ||
                    "Top Scored Vendor"}
                </h2>
              </div>
            </div>

            {comp.scores?.is_close && (
              <span className="rounded-full bg-amber-100 border border-amber-300 px-2.5 py-0.5 text-[11px] font-semibold text-amber-800">
                Close Call (&lt; 2.0 pts margin)
              </span>
            )}
          </div>

          {comp.explanation && (
            <div className="mt-4 rounded-md bg-white/80 border border-purple-100 p-4 text-xs text-slate-700 leading-relaxed" data-testid="recommendation-explanation">
              <p className="font-medium text-slate-900 mb-1">Recommendation Explanation:</p>
              {comp.explanation}
            </div>
          )}

          {/* Override Indicator (US-10) */}
          {comp.chosen_vendor_id && comp.chosen_vendor_id !== comp.recommended_vendor_id && (
            <div className="mt-4 rounded-md border border-rose-200 bg-rose-50 p-3 text-xs text-rose-800" data-testid="override-indicator">
              <strong className="font-semibold flex items-center gap-1.5">
                <ShieldAlert className="h-4 w-4 text-rose-600" />
                Buyer Override Active (US-10)
              </strong>
              <p className="mt-1">
                Chosen vendor differs from the AI recommendation.
                <br />
                <span className="font-mono text-slate-700">Reason: &ldquo;{comp.override_reason}&rdquo;</span>
              </p>
            </div>
          )}
        </div>
      )}

      {/* Side-by-Side Comparison Matrix (US-08) */}
      <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-base font-semibold text-slate-900 mb-4 flex items-center gap-2">
          <GitCompare className="h-4 w-4 text-slate-500" />
          Side-by-Side Comparison Matrix (US-08)
        </h2>

        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-xs">
            <thead className="bg-slate-50 text-[11px] font-semibold text-slate-700">
              <tr>
                <th className="px-4 py-3 text-left w-64">Criteria & Quotations</th>
                {quotes.map((q) => {
                  const isWinner = q.vendor_id === comp.recommended_vendor_id;
                  const isChosen = q.vendor_id === comp.chosen_vendor_id;
                  return (
                    <th
                      key={q.document_id}
                      className={`px-4 py-3 text-left min-w-[220px] ${
                        isWinner ? "bg-purple-50/70 border-x border-purple-200" : ""
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-slate-900 truncate">
                          {q.vendor_name || `Vendor (${q.document_id.slice(0, 8)})`}
                        </span>
                        {isWinner && (
                          <span className="text-[10px] bg-purple-600 text-white px-1.5 py-0.5 rounded font-semibold">
                            Recommended
                          </span>
                        )}
                        {isChosen && (
                          <span className="text-[10px] bg-emerald-600 text-white px-1.5 py-0.5 rounded font-semibold ml-1">
                            Chosen
                          </span>
                        )}
                      </div>
                      <div className="text-[10px] font-normal text-slate-500 mt-0.5">
                        <Link href={`/documents/${q.document_id}`} className="text-blue-600 hover:underline">
                          View Quote PDF
                        </Link>
                      </div>
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              <tr>
                <td className="px-4 py-2.5 font-semibold text-slate-800">Quoted Total (AED)</td>
                {quotes.map((q) => (
                  <td key={q.document_id} className="px-4 py-2.5 font-bold text-slate-900">
                    {formatMoneyAED(q.total_aed)}
                  </td>
                ))}
              </tr>
              <tr>
                <td className="px-4 py-2.5 font-semibold text-slate-800">Lead Time</td>
                {quotes.map((q) => (
                  <td key={q.document_id} className="px-4 py-2.5 text-slate-700">
                    {q.lead_time_days ? `${q.lead_time_days} days` : "Not specified"}
                  </td>
                ))}
              </tr>
              <tr>
                <td className="px-4 py-2.5 font-semibold text-slate-800">Payment Terms</td>
                {quotes.map((q) => (
                  <td key={q.document_id} className="px-4 py-2.5 text-slate-700">
                    {q.payment_terms_days ? `${q.payment_terms_days} days net` : "Not specified"}
                  </td>
                ))}
              </tr>
              <tr>
                <td className="px-4 py-2.5 font-semibold text-slate-800">Status & Validity</td>
                {quotes.map((q) => (
                  <td key={q.document_id} className="px-4 py-2.5">
                    {q.is_expired ? (
                      <span className="text-rose-600 font-semibold text-[11px]">Expired</span>
                    ) : (
                      <span className="text-emerald-700 text-[11px]">Valid</span>
                    )}
                  </td>
                ))}
              </tr>

              {/* Scores Breakdown if available */}
              {Object.keys(vendorScores).length > 0 && (
                <>
                  <tr className="bg-slate-50/80 font-bold text-slate-900">
                    <td colSpan={quotes.length + 1} className="px-4 py-2 uppercase text-[10px] tracking-wider text-slate-500">
                      Scores Breakdown (0–100)
                    </td>
                  </tr>
                  <tr>
                    <td className="px-4 py-2 font-medium text-slate-700">Cost Score (60%)</td>
                    {quotes.map((q) => {
                      const sc = q.vendor_id ? vendorScores[q.vendor_id] : null;
                      return (
                        <td key={q.document_id} className="px-4 py-2 font-mono text-slate-800">
                          {sc?.cost_score !== undefined ? `${sc.cost_score} / 100` : "—"}
                        </td>
                      );
                    })}
                  </tr>
                  <tr>
                    <td className="px-4 py-2 font-medium text-slate-700">Delivery Score (20%)</td>
                    {quotes.map((q) => {
                      const sc = q.vendor_id ? vendorScores[q.vendor_id] : null;
                      return (
                        <td key={q.document_id} className="px-4 py-2 font-mono text-slate-800">
                          {sc?.delivery_score !== undefined ? `${sc.delivery_score} / 100` : "—"}
                        </td>
                      );
                    })}
                  </tr>
                  <tr>
                    <td className="px-4 py-2 font-medium text-slate-700">Payment Terms Score (10%)</td>
                    {quotes.map((q) => {
                      const sc = q.vendor_id ? vendorScores[q.vendor_id] : null;
                      return (
                        <td key={q.document_id} className="px-4 py-2 font-mono text-slate-800">
                          {sc?.payment_score !== undefined ? `${sc.payment_score} / 100` : "—"}
                        </td>
                      );
                    })}
                  </tr>
                  <tr>
                    <td className="px-4 py-2 font-medium text-slate-700">Completeness Score (10%)</td>
                    {quotes.map((q) => {
                      const sc = q.vendor_id ? vendorScores[q.vendor_id] : null;
                      return (
                        <td key={q.document_id} className="px-4 py-2 font-mono text-slate-800">
                          {sc?.completeness_score !== undefined ? `${sc.completeness_score} / 100` : "—"}
                        </td>
                      );
                    })}
                  </tr>
                  <tr className="border-t border-purple-200 bg-purple-50/50 font-bold">
                    <td className="px-4 py-2.5 text-purple-900">Total Weighted Score</td>
                    {quotes.map((q) => {
                      const sc = q.vendor_id ? vendorScores[q.vendor_id] : null;
                      return (
                        <td key={q.document_id} className="px-4 py-2.5 font-mono text-sm text-purple-900">
                          {sc?.final_score !== undefined ? `${sc.final_score}` : "—"}
                        </td>
                      );
                    })}
                  </tr>
                </>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Adjust Weights Section (US-11) */}
      {isBuyer && (
        <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-base font-semibold text-slate-900 flex items-center gap-2">
                <Sliders className="h-4 w-4 text-blue-600" />
                Scoring Weights Configuration (US-11)
              </h2>
              <p className="text-xs text-slate-500 mt-0.5">
                Buyer can adjust weights for Cost, Delivery, Payment, and Completeness. Must total exactly 100%.
              </p>
            </div>

            <div className="flex items-center gap-3">
              <span
                className={`text-xs font-bold px-2.5 py-1 rounded-md ${
                  weightsValid
                    ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                    : "bg-rose-50 text-rose-700 border border-rose-200"
                }`}
                data-testid="weights-total"
              >
                Total: {weightsTotal}%
              </span>
              <button
                type="button"
                onClick={handleSaveWeights}
                disabled={!weightsValid || savingWeights}
                data-testid="save-weights-btn"
                className="inline-flex items-center gap-1.5 rounded-md bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-blue-700 disabled:opacity-50"
              >
                {savingWeights ? "Updating..." : "Recalculate Scores"}
              </button>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-4 gap-4 text-xs">
            <div>
              <label htmlFor="weight-cost" className="block font-medium text-slate-700 mb-1">Cost Weight (%)</label>
              <input
                id="weight-cost"
                type="number"
                min="0"
                max="100"
                value={weights.cost}
                onChange={(e) => setWeights({ ...weights, cost: parseInt(e.target.value) || 0 })}
                className="w-full rounded border border-slate-300 px-2.5 py-1.5 text-slate-900"
              />
            </div>
            <div>
              <label htmlFor="weight-delivery" className="block font-medium text-slate-700 mb-1">Delivery Lead Time (%)</label>
              <input
                id="weight-delivery"
                type="number"
                min="0"
                max="100"
                value={weights.delivery}
                onChange={(e) => setWeights({ ...weights, delivery: parseInt(e.target.value) || 0 })}
                className="w-full rounded border border-slate-300 px-2.5 py-1.5 text-slate-900"
              />
            </div>
            <div>
              <label htmlFor="weight-payment" className="block font-medium text-slate-700 mb-1">Payment Terms (%)</label>
              <input
                id="weight-payment"
                type="number"
                min="0"
                max="100"
                value={weights.payment}
                onChange={(e) => setWeights({ ...weights, payment: parseInt(e.target.value) || 0 })}
                className="w-full rounded border border-slate-300 px-2.5 py-1.5 text-slate-900"
              />
            </div>
            <div>
              <label htmlFor="weight-completeness" className="block font-medium text-slate-700 mb-1">Completeness (%)</label>
              <input
                id="weight-completeness"
                type="number"
                min="0"
                max="100"
                value={weights.completeness}
                onChange={(e) =>
                  setWeights({ ...weights, completeness: parseInt(e.target.value) || 0 })
                }
                className="w-full rounded border border-slate-300 px-2.5 py-1.5 text-slate-900"
              />
            </div>
          </div>
        </div>
      )}

      {/* Decision Dialog Modal (US-10) */}
      {decisionModalOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
        >
          <div className="w-full max-w-lg rounded-lg bg-white p-6 shadow-xl border border-slate-200">
            <h3 className="text-base font-bold text-slate-900 mb-1 flex items-center gap-2">
              <Award className="h-5 w-5 text-purple-600" />
              Vendor Selection Decision (US-10)
            </h3>
            <p className="text-xs text-slate-500 mb-4">
              Select the supplier to award the purchase order. Choosing any vendor other than the system recommendation requires a recorded override reason.
            </p>

            {decisionError && (
              <div className="mb-4 rounded border border-rose-200 bg-rose-50 p-2.5 text-xs text-rose-700">
                {decisionError}
              </div>
            )}

            <form onSubmit={handleSaveDecision} className="space-y-4 text-xs">
              <div>
                <label className="block font-medium text-slate-700 mb-2">Select Awardee Vendor:</label>
                <div className="space-y-2 max-h-56 overflow-y-auto border rounded-md p-2">
                  {quotes.map((q) => {
                    const isRec = q.vendor_id === comp.recommended_vendor_id;
                    const isSelected = selectedVendorId === q.vendor_id;
                    return (
                      <label
                        key={q.document_id}
                        className={`flex items-start gap-3 p-2.5 rounded cursor-pointer border ${
                          isSelected
                            ? "bg-purple-50/70 border-purple-300"
                            : "hover:bg-slate-50 border-transparent"
                        }`}
                      >
                        <input
                          type="radio"
                          name="awardee"
                          value={q.vendor_id || ""}
                          checked={isSelected}
                          onChange={() => setSelectedVendorId(q.vendor_id || "")}
                          className="mt-0.5 text-purple-600"
                        />
                        <div className="flex-1">
                          <div className="flex items-center justify-between">
                            <span className="font-semibold text-slate-900">
                              {q.vendor_name || "Vendor"}
                            </span>
                            {isRec && (
                              <span className="bg-purple-100 text-purple-700 text-[10px] px-1.5 py-0.5 rounded font-bold">
                                Recommended
                              </span>
                            )}
                          </div>
                          <div className="text-[11px] text-slate-500 flex gap-3 mt-0.5">
                            <span>Total: {formatMoneyAED(q.total_aed)}</span>
                            <span>Lead: {q.lead_time_days || "—"} days</span>
                          </div>
                        </div>
                      </label>
                    );
                  })}
                </div>
              </div>

              {overrideRequired && (
                <div className="rounded-md border border-amber-200 bg-amber-50/70 p-3">
                  <label htmlFor="override-reason-input" className="block font-semibold text-amber-900 mb-1">
                    Override Justification Reason * (US-10)
                  </label>
                  <p className="text-[11px] text-amber-700 mb-2">
                    You have chosen a supplier other than the AI recommended vendor. Please enter a justification of at least 10 characters.
                  </p>
                  <textarea
                    id="override-reason-input"
                    value={overrideReason}
                    onChange={(e) => setOverrideReason(e.target.value)}
                    rows={3}
                    placeholder="Enter reason for overriding recommendation (min 10 characters)..."
                    required
                    data-testid="override-reason-input"
                    className="w-full rounded border border-amber-300 bg-white p-2 text-xs text-slate-900 focus:outline-none focus:ring-1 focus:ring-purple-500"
                  />
                  <div className="mt-1 flex justify-between text-[10px] text-amber-800">
                    <span>{overrideReason.length} / 10 characters minimum</span>
                    {overrideReason.trim().length >= 10 && <span className="text-emerald-700 font-semibold">Requirement met</span>}
                  </div>
                </div>
              )}

              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setDecisionModalOpen(false)}
                  className="rounded-md border border-slate-300 px-3.5 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submittingDecision || !selectedVendorId || !overrideValid}
                  data-testid="confirm-decision-btn"
                  className="rounded-md bg-purple-600 px-4 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-purple-700 disabled:opacity-50"
                >
                  {submittingDecision ? "Saving..." : "Confirm Decision"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
