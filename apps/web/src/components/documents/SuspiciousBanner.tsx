"use client";

import React, { useState, useRef, useEffect } from "react";
import { AlertTriangle, ShieldAlert, CheckCircle2, X } from "lucide-react";
import type { DocumentResponse } from "@/lib/documents/types";

export interface SuspiciousBannerProps {
  doc: DocumentResponse;
  isBuyer: boolean;
  onAcknowledged: () => void;
  onToast: (type: "success" | "error", title: string, message?: string) => void;
}

export const SuspiciousBanner: React.FC<SuspiciousBannerProps> = ({
  doc,
  isBuyer,
  onAcknowledged,
  onToast,
}) => {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (dialogOpen) {
      setError(null);
      setReason("");
      setTimeout(() => textareaRef.current?.focus(), 50);
    }
  }, [dialogOpen]);

  if (!doc.suspicious) return null;

  const isAcknowledged = Boolean(doc.suspicious_ack_reason);

  const handleAcknowledge = async (e: React.FormEvent) => {
    e.preventDefault();
    const cleanReason = reason.trim();
    if (cleanReason.length < 10) {
      setError("Acknowledgement reason must be at least 10 characters.");
      return;
    }

    try {
      setSubmitting(true);
      setError(null);

      const res = await fetch(`/api/v1/documents/${doc.id}/acknowledge-suspicious`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Origin: window.location.origin,
        },
        body: JSON.stringify({ reason: cleanReason }),
      });

      if (!res.ok) {
        const problem = await res.json().catch(() => ({}));
        throw new Error(problem.detail || problem.title || `Error ${res.status}`);
      }

      onToast(
        "success",
        "Suspicious Content Acknowledged",
        "Document confirmation block has been lifted."
      );
      setDialogOpen(false);
      onAcknowledged();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to acknowledge suspicious content.";
      setError(msg);
      onToast("error", "Acknowledgement Failed", msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <div
        className={`mb-6 rounded-lg border p-4 ${
          isAcknowledged
            ? "border-amber-200 bg-amber-50/70"
            : "border-rose-300 bg-rose-50"
        }`}
        role="alert"
        aria-live="polite"
      >
        <div className="flex items-start gap-3">
          <div
            className={`mt-0.5 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full ${
              isAcknowledged
                ? "bg-amber-100 text-amber-700"
                : "bg-rose-100 text-rose-700 animate-pulse"
            }`}
          >
            <ShieldAlert className="h-5 w-5" aria-hidden="true" />
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2
                className={`text-sm font-bold ${
                  isAcknowledged ? "text-amber-900" : "text-rose-900"
                }`}
              >
                {isAcknowledged
                  ? "Prompt Injection Defence: Suspicious Content Acknowledged"
                  : "Security Alert: Suspicious Content Detected (Prompt Injection Defence)"}
              </h2>

              {isAcknowledged ? (
                <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-semibold text-emerald-800 border border-emerald-200">
                  <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
                  Acknowledged
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 rounded-full bg-rose-100 px-2.5 py-0.5 text-xs font-semibold text-rose-800 border border-rose-200">
                  Action Required
                </span>
              )}
            </div>

            <p className="mt-1 text-xs text-slate-700 leading-relaxed">
              This document contains text that appears to be instructions directed at the AI
              system (e.g. attempting to override totals or force approvals). Per Design 7.5 and
              US-29, <strong>all instructions inside document text are treated strictly as data and ignored</strong>.
              Document confirmation is blocked until a Buyer inspects the ground truth and acknowledges.
            </p>

            {isAcknowledged ? (
              <div className="mt-3 rounded border border-amber-200 bg-white/80 p-2.5 text-xs text-slate-800">
                <span className="font-semibold text-amber-900">Recorded Reason:</span>{" "}
                <span className="italic">{doc.suspicious_ack_reason}</span>
              </div>
            ) : (
              isBuyer && (
                <div className="mt-3 flex items-center gap-3">
                  <button
                    type="button"
                    onClick={() => setDialogOpen(true)}
                    className="inline-flex items-center gap-1.5 rounded-md bg-rose-600 px-3.5 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-rose-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-rose-600"
                  >
                    Acknowledge Suspicious Content
                  </button>
                  <span className="text-xs text-slate-500">
                    Required before this document can be confirmed
                  </span>
                </div>
              )
            )}
          </div>
        </div>
      </div>

      {/* Acknowledge Dialog */}
      {dialogOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
          aria-labelledby="ack-dialog-title"
          aria-describedby="ack-dialog-desc"
        >
          <div className="relative w-full max-w-lg rounded-lg bg-white p-6 shadow-xl border border-slate-200">
            <button
              type="button"
              onClick={() => setDialogOpen(false)}
              className="absolute right-4 top-4 text-slate-400 hover:text-slate-600"
              aria-label="Close dialog"
            >
              <X className="h-5 w-5" aria-hidden="true" />
            </button>

            <div className="flex items-start gap-3">
              <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-rose-100 text-rose-600">
                <AlertTriangle className="h-5 w-5" aria-hidden="true" />
              </div>
              <div>
                <h3 id="ack-dialog-title" className="text-base font-bold text-slate-900">
                  Acknowledge Suspicious Document Content
                </h3>
                <p id="ack-dialog-desc" className="mt-1 text-xs text-slate-600">
                  Please confirm you have reviewed the document against ground truth. State your verification
                  reason (minimum 10 characters). This will be recorded permanently in the tamper-evident audit log.
                </p>
              </div>
            </div>

            <form onSubmit={handleAcknowledge} className="mt-4">
              {error && (
                <div className="mb-3 rounded border border-rose-200 bg-rose-50 p-2 text-xs text-rose-700">
                  {error}
                </div>
              )}

              <label htmlFor="ack-reason" className="block text-xs font-semibold text-slate-700 mb-1">
                Acknowledgement Reason <span className="text-rose-500">*</span>
              </label>
              <textarea
                id="ack-reason"
                ref={textareaRef}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                rows={3}
                placeholder="e.g., Verified physical document; ignored hidden text and confirmed actual ground-truth total."
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-xs text-slate-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                required
              />
              <div className="mt-1 flex justify-between text-[11px] text-slate-500">
                <span>Minimum 10 characters required</span>
                <span className={reason.trim().length < 10 ? "text-amber-600 font-medium" : "text-emerald-600 font-medium"}>
                  {reason.trim().length}/10 chars
                </span>
              </div>

              <div className="mt-5 flex justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setDialogOpen(false)}
                  disabled={submitting}
                  className="rounded-md border border-slate-300 bg-white px-3.5 py-1.5 text-xs font-medium text-slate-700 shadow-sm hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting || reason.trim().length < 10}
                  className="rounded-md bg-rose-600 px-4 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-rose-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {submitting ? "Acknowledging..." : "Acknowledge & Lift Block"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
};
