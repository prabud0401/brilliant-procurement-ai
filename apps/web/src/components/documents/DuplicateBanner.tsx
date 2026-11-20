"use client";

import React, { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { Copy, AlertCircle, CheckCircle2, X } from "lucide-react";
import type { DocumentResponse } from "@/lib/documents/types";

export interface DuplicateBannerProps {
  doc: DocumentResponse;
  isBuyer: boolean;
  onCleared: () => void;
  onToast: (type: "success" | "error", title: string, message?: string) => void;
}

export const DuplicateBanner: React.FC<DuplicateBannerProps> = ({
  doc,
  isBuyer,
  onCleared,
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

  if (!doc.duplicate_of) return null;

  const isCleared = Boolean(doc.duplicate_cleared_reason);

  const handleClear = async (e: React.FormEvent) => {
    e.preventDefault();
    const cleanReason = reason.trim();
    if (cleanReason.length < 10) {
      setError("Clear duplicate reason must be at least 10 characters.");
      return;
    }

    try {
      setSubmitting(true);
      setError(null);

      const res = await fetch(`/api/v1/documents/${doc.id}/not-duplicate`, {
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
        "Duplicate Flag Cleared",
        "Document is cleared for confirmation and matching."
      );
      setDialogOpen(false);
      onCleared();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to clear duplicate flag.";
      setError(msg);
      onToast("error", "Action Failed", msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <div
        className={`mb-6 rounded-lg border p-4 ${
          isCleared
            ? "border-amber-200 bg-amber-50/60"
            : "border-orange-300 bg-orange-50"
        }`}
        role="alert"
        aria-live="polite"
      >
        <div className="flex items-start gap-3">
          <div
            className={`mt-0.5 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full ${
              isCleared ? "bg-amber-100 text-amber-700" : "bg-orange-100 text-orange-700"
            }`}
          >
            <Copy className="h-4 w-4" aria-hidden="true" />
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2
                className={`text-sm font-bold ${
                  isCleared ? "text-amber-900" : "text-orange-900"
                }`}
              >
                {isCleared
                  ? "Duplicate Warning Cleared"
                  : "Possible Duplicate Document Flagged (US-06)"}
              </h2>

              {isCleared ? (
                <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-semibold text-emerald-800 border border-emerald-200">
                  <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
                  Duplicate Cleared
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 rounded-full bg-orange-100 px-2.5 py-0.5 text-xs font-semibold text-orange-800 border border-orange-200">
                  Duplicate Review Required
                </span>
              )}
            </div>

            <p className="mt-1 text-xs text-slate-700 leading-relaxed">
              This document matches an existing document (
              <Link
                href={`/documents/${doc.duplicate_of}`}
                className="font-semibold text-blue-600 underline hover:text-blue-800"
                target="_blank"
              >
                {doc.duplicate_of}
              </Link>
              ). Per US-06, a Buyer must confirm it is not a duplicate before confirmation or matching.
            </p>

            {isCleared ? (
              <div className="mt-3 rounded border border-amber-200 bg-white/80 p-2.5 text-xs text-slate-800">
                <span className="font-semibold text-amber-900">Recorded Clearance Reason:</span>{" "}
                <span className="italic">{doc.duplicate_cleared_reason}</span>
              </div>
            ) : (
              isBuyer && (
                <div className="mt-3 flex items-center gap-3">
                  <button
                    type="button"
                    onClick={() => setDialogOpen(true)}
                    className="inline-flex items-center gap-1.5 rounded-md bg-orange-600 px-3.5 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-orange-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-orange-600"
                  >
                    Clear Duplicate Flag
                  </button>
                  <span className="text-xs text-slate-500">
                    State reason to confirm this document is distinct
                  </span>
                </div>
              )
            )}
          </div>
        </div>
      </div>

      {/* Clear Duplicate Dialog */}
      {dialogOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
          aria-labelledby="dup-dialog-title"
          aria-describedby="dup-dialog-desc"
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
              <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-orange-100 text-orange-600">
                <AlertCircle className="h-5 w-5" aria-hidden="true" />
              </div>
              <div>
                <h3 id="dup-dialog-title" className="text-base font-bold text-slate-900">
                  Clear Duplicate Flag
                </h3>
                <p id="dup-dialog-desc" className="mt-1 text-xs text-slate-600">
                  State why this document is not an accidental re-submission or duplicate payment request (minimum 10 characters).
                </p>
              </div>
            </div>

            <form onSubmit={handleClear} className="mt-4">
              {error && (
                <div className="mb-3 rounded border border-rose-200 bg-rose-50 p-2 text-xs text-rose-700">
                  {error}
                </div>
              )}

              <label htmlFor="dup-reason" className="block text-xs font-semibold text-slate-700 mb-1">
                Reason for Clearance <span className="text-orange-500">*</span>
              </label>
              <textarea
                id="dup-reason"
                ref={textareaRef}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                rows={3}
                placeholder="e.g., Verified with supplier; this is a separate revision with revised line items."
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
                  className="rounded-md bg-orange-600 px-4 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-orange-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {submitting ? "Submitting..." : "Confirm & Clear Flag"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
};
