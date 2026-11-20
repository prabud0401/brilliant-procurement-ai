"use client";

import React, { useState, useEffect, useRef } from "react";
import { X, Check } from "lucide-react";

export interface FieldEditDialogProps {
  isOpen: boolean;
  fieldName: string;
  fieldLabel: string;
  currentValue: string;
  onClose: () => void;
  onSave: (newValue: string) => Promise<void>;
}

export const FieldEditDialog: React.FC<FieldEditDialogProps> = ({
  isOpen,
  fieldName,
  fieldLabel,
  currentValue,
  onClose,
  onSave,
}) => {
  const [value, setValue] = useState(currentValue);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isOpen) {
      setValue(currentValue);
      setError(null);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [isOpen, currentValue]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setSubmitting(true);
      setError(null);
      await onSave(value);
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to update field value.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="edit-dialog-title"
    >
      <div className="relative w-full max-w-md rounded-lg bg-white p-6 shadow-xl border border-slate-200">
        <button
          type="button"
          onClick={onClose}
          className="absolute right-4 top-4 text-slate-400 hover:text-slate-600"
          aria-label="Close dialog"
        >
          <X className="h-5 w-5" aria-hidden="true" />
        </button>

        <h3 id="edit-dialog-title" className="text-base font-bold text-slate-900">
          Correct Field: {fieldLabel}
        </h3>
        <p className="mt-1 text-xs text-slate-500">
          Update the extracted value against the original document page. The correction and before/after values are recorded in the audit trail.
        </p>

        {error && (
          <div className="mt-3 rounded border border-rose-200 bg-rose-50 p-2 text-xs text-rose-700">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-4 space-y-4">
          <div>
            <label className="block text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1">
              Extracted Value (Before)
            </label>
            <div className="rounded border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-mono text-slate-700">
              {currentValue || "<empty>"}
            </div>
          </div>

          <div>
            <label htmlFor="corrected-value" className="block text-xs font-semibold text-slate-700 mb-1">
              Corrected Value (After) <span className="text-blue-600">*</span>
            </label>
            <input
              id="corrected-value"
              ref={inputRef}
              type="text"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              required
            />
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={submitting}
              className="rounded-md border border-slate-300 bg-white px-3.5 py-1.5 text-xs font-medium text-slate-700 shadow-sm hover:bg-slate-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="inline-flex items-center gap-1.5 rounded-md bg-blue-600 px-4 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-blue-700 disabled:opacity-50"
            >
              <Check className="h-3.5 w-3.5" aria-hidden="true" />
              {submitting ? "Saving..." : "Save Correction"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
