"use client";

import React, { useState, useEffect } from "react";
import { Building2, X, Check, Loader2 } from "lucide-react";
import { fetchVendors, type Vendor } from "@/lib/constants/vendors";

export interface VendorSelectDialogProps {
  isOpen: boolean;
  currentVendorId: string | null;
  onClose: () => void;
  onSave: (vendorId: string | null, newVendor: boolean) => Promise<void>;
}

export const VendorSelectDialog: React.FC<VendorSelectDialogProps> = ({
  isOpen,
  currentVendorId,
  onClose,
  onSave,
}) => {
  const [vendors, setVendors] = useState<Vendor[]>([]);
  const [loadingVendors, setLoadingVendors] = useState<boolean>(false);
  const [selectedId, setSelectedId] = useState<string | null>(currentVendorId);
  const [isNewVendor, setIsNewVendor] = useState<boolean>(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      setSelectedId(currentVendorId);
      setIsNewVendor(false);
      setLoadingVendors(true);
      fetchVendors()
        .then((data) => setVendors(data))
        .catch((err) => setError(err instanceof Error ? err.message : "Failed to load vendors"))
        .finally(() => setLoadingVendors(false));
    }
  }, [isOpen, currentVendorId]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setSubmitting(true);
      setError(null);
      await onSave(isNewVendor ? null : selectedId, isNewVendor);
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to link vendor.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="vendor-dialog-title"
    >
      <div className="relative w-full max-w-lg rounded-lg bg-white p-6 shadow-xl border border-slate-200">
        <button
          type="button"
          onClick={onClose}
          className="absolute right-4 top-4 text-slate-400 hover:text-slate-600"
          aria-label="Close dialog"
        >
          <X className="h-5 w-5" aria-hidden="true" />
        </button>

        <div className="flex items-center gap-3 mb-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-100 text-blue-700">
            <Building2 className="h-5 w-5" aria-hidden="true" />
          </div>
          <div>
            <h3 id="vendor-dialog-title" className="text-base font-bold text-slate-900">
              Link Odoo Vendor Record (US-05)
            </h3>
            <p className="text-xs text-slate-500">
              Select an official vendor from the Odoo master data list or flag as new.
            </p>
          </div>
        </div>

        {error && (
          <div className="mb-4 rounded border border-rose-200 bg-rose-50 p-2.5 text-xs text-rose-700">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="max-h-72 overflow-y-auto space-y-2 border rounded-md p-2 divide-y divide-slate-100">
            {loadingVendors ? (
              <div className="flex items-center justify-center py-8 text-xs text-slate-500 gap-2">
                <Loader2 className="h-4 w-4 animate-spin text-blue-600" />
                <span>Loading Odoo vendors...</span>
              </div>
            ) : (
              vendors.map((vendor: Vendor) => {
                const isChecked = !isNewVendor && selectedId === vendor.id;
                return (
                  <label
                    key={vendor.id}
                    className={`flex items-start gap-3 p-2.5 rounded cursor-pointer transition-colors ${
                      isChecked ? "bg-blue-50/70 border border-blue-200" : "hover:bg-slate-50"
                    }`}
                  >
                    <input
                      type="radio"
                      name="vendor"
                      value={vendor.id}
                      checked={isChecked}
                      onChange={() => {
                        setSelectedId(vendor.id);
                        setIsNewVendor(false);
                      }}
                      className="mt-1 h-4 w-4 text-blue-600 border-slate-300 focus:ring-blue-500"
                    />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-900">{vendor.name}</span>
                        {vendor.trn && (
                          <span className="text-[10px] font-mono text-slate-500">TRN: {vendor.trn}</span>
                        )}
                      </div>
                      {vendor.address && (
                        <p className="text-[11px] text-slate-500 truncate mt-0.5">{vendor.address}</p>
                      )}
                      <div className="mt-1 flex gap-3 text-[10px] text-slate-600">
                        <span>Terms: {vendor.payment_terms_days} days</span>
                        {vendor.lead_time_days && <span>Lead time: {vendor.lead_time_days} days</span>}
                        {vendor.category && <span className="font-medium text-blue-700">{vendor.category}</span>}
                      </div>
                    </div>
                  </label>
                );
              })
            )}

            {/* Option for New Vendor */}
            <label
              className={`flex items-start gap-3 p-2.5 rounded cursor-pointer transition-colors ${
                isNewVendor ? "bg-amber-50/70 border border-amber-200" : "hover:bg-slate-50"
              }`}
            >
              <input
                type="radio"
                name="vendor"
                value="new"
                checked={isNewVendor}
                onChange={() => {
                  setIsNewVendor(true);
                  setSelectedId(null);
                }}
                className="mt-1 h-4 w-4 text-amber-600 border-slate-300 focus:ring-amber-500"
              />
              <div className="flex-1">
                <span className="text-xs font-semibold text-amber-900">New Vendor (Not in Odoo)</span>
                <p className="text-[11px] text-amber-700 mt-0.5">
                  Flags this vendor as new. Note: PO creation will require onboarding this vendor into Odoo first.
                </p>
              </div>
            </label>
          </div>

          <div className="mt-6 flex justify-end gap-3">
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
              disabled={submitting || (!selectedId && !isNewVendor)}
              className="inline-flex items-center gap-1.5 rounded-md bg-blue-600 px-4 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-blue-700 disabled:opacity-50"
            >
              <Check className="h-3.5 w-3.5" aria-hidden="true" />
              {submitting ? "Saving..." : "Save Vendor Link"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
