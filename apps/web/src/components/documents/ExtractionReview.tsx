"use client";

import React, { useState } from "react";
import {
  Building2,
  Check,
  CheckCircle2,
  Edit2,
  AlertTriangle,
  FileCheck,
  HelpCircle,
  Eye,
  Info,
} from "lucide-react";
import { ConfidenceBadge } from "@/components/ui/ConfidenceBadge";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { FieldEditDialog } from "./FieldEditDialog";
import { VendorSelectDialog } from "./VendorSelectDialog";
import { formatCurrency } from "@/lib/formatters";
import { getOpenItems, formatFieldName, type OpenItem } from "@/lib/documents/open-items";
import { getVendorById, type SeededVendor } from "@/lib/constants/vendors";
import type {
  DocumentResponse,
  ExtractionResponse,
  ExtractedField,
  ExtractedLine,
  HighlightTarget,
} from "@/lib/documents/types";

export interface ExtractionReviewProps {
  document: DocumentResponse;
  extraction: ExtractionResponse;
  userRoles: string[];
  selectedHighlight: HighlightTarget | null;
  onSelectHighlight: (target: HighlightTarget | null) => void;
  onRefresh: () => Promise<void>;
  onToast: (type: "success" | "error" | "info" | "warning", title: string, message?: string) => void;
}

export const ExtractionReview: React.FC<ExtractionReviewProps> = ({
  document,
  extraction,
  userRoles,
  selectedHighlight,
  onSelectHighlight,
  onRefresh,
  onToast,
}) => {
  const isBuyer = userRoles.includes("buyer");
  const isAdmin = userRoles.includes("admin") && !isBuyer;
  const isReadOnly = !isBuyer;

  // Dialog state for field editing
  const [editingField, setEditingField] = useState<ExtractedField | null>(null);
  const [editingLine, setEditingLine] = useState<ExtractedLine | null>(null);
  const [vendorDialogOpen, setVendorDialogOpen] = useState(false);
  const [confirmingDoc, setConfirmingDoc] = useState(false);
  const [confirmError, setConfirmError] = useState<string | null>(null);

  const fields = extraction.fields || [];
  const lines = extraction.lines || [];

  const openSummary = getOpenItems(document, fields, lines);
  const isConfirmed = document.status === "confirmed";

  // Linked vendor details
  const linkedVendor: SeededVendor | undefined = getVendorById(document.vendor_id);

  // Field Correction Handlers
  const handleSaveFieldCorrection = async (newValue: string) => {
    if (!editingField) return;
    try {
      const res = await fetch(`/api/v1/documents/${document.id}/fields/${editingField.id}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Origin: window.location.origin,
        },
        body: JSON.stringify({ value: newValue }),
      });

      if (!res.ok) {
        const problem = await res.json().catch(() => ({}));
        throw new Error(problem.detail || problem.title || `Error ${res.status}`);
      }

      onToast(
        "success",
        "Field Corrected",
        `${formatFieldName(editingField.name)} updated to "${newValue}". Saved in audit trail.`
      );
      await onRefresh();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to update field.";
      onToast("error", "Update Failed", msg);
      throw err;
    }
  };

  const handleConfirmField = async (field: ExtractedField) => {
    try {
      const res = await fetch(`/api/v1/documents/${document.id}/fields/${field.id}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Origin: window.location.origin,
        },
        body: JSON.stringify({ confirm: true }),
      });

      if (!res.ok) {
        const problem = await res.json().catch(() => ({}));
        throw new Error(problem.detail || problem.title || `Error ${res.status}`);
      }

      onToast("success", "Field Confirmed", `${formatFieldName(field.name)} confirmed.`);
      await onRefresh();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to confirm field.";
      onToast("error", "Confirm Failed", msg);
    }
  };

  // Line Item Correction Handlers
  const handleConfirmLine = async (line: ExtractedLine) => {
    try {
      const res = await fetch(`/api/v1/documents/${document.id}/lines/${line.id}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Origin: window.location.origin,
        },
        body: JSON.stringify({ confirm: true }),
      });

      if (!res.ok) {
        const problem = await res.json().catch(() => ({}));
        throw new Error(problem.detail || problem.title || `Error ${res.status}`);
      }

      onToast("success", "Line Item Confirmed", `Line #${line.line_no} confirmed.`);
      await onRefresh();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to confirm line item.";
      onToast("error", "Confirm Failed", msg);
    }
  };

  // Vendor Linking Handler
  const handleSaveVendor = async (vendorId: string | null, newVendor: boolean) => {
    try {
      const res = await fetch(`/api/v1/documents/${document.id}/vendor`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Origin: window.location.origin,
        },
        body: JSON.stringify({ vendor_id: vendorId, new_vendor: newVendor }),
      });

      if (!res.ok) {
        const problem = await res.json().catch(() => ({}));
        throw new Error(problem.detail || problem.title || `Error ${res.status}`);
      }

      onToast(
        "success",
        "Vendor Updated",
        newVendor ? "Document flagged with New Vendor." : "Vendor linked to Odoo master record."
      );
      await onRefresh();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to link vendor.";
      onToast("error", "Vendor Linking Failed", msg);
      throw err;
    }
  };

  // Final Document Confirmation Handler (US-03)
  const handleConfirmDocument = async () => {
    if (openSummary.isOpen) {
      setConfirmError(`Cannot confirm: Document has ${openSummary.count} open item(s).`);
      return;
    }

    try {
      setConfirmingDoc(true);
      setConfirmError(null);

      const res = await fetch(`/api/v1/documents/${document.id}/confirm`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Origin: window.location.origin,
        },
      });

      if (!res.ok) {
        const problem = await res.json().catch(() => ({}));
        const detailMsg =
          problem.detail ||
          problem.title ||
          `Cannot confirm document (HTTP ${res.status})`;
        setConfirmError(detailMsg);
        throw new Error(detailMsg);
      }

      onToast(
        "success",
        "Document Confirmed",
        "Document has been successfully verified and confirmed for downstream procurement processing."
      );
      await onRefresh();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Confirmation failed.";
      onToast("error", "Confirmation Blocked", msg);
    } finally {
      setConfirmingDoc(false);
    }
  };

  return (
    <div className="flex flex-col space-y-6" data-testid="extraction-review-panel">
      {/* Admin metadata notification */}
      {isAdmin && (
        <div className="rounded-md border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600">
          <span className="font-semibold text-slate-800">Admin View:</span> Viewing document metadata and extraction. Review actions are reserved for the Buyer role.
        </div>
      )}

      {/* Requester / Manager read-only notice */}
      {isReadOnly && !isAdmin && (
        <div className="rounded-md border border-blue-100 bg-blue-50/70 p-3 text-xs text-blue-800 flex items-center gap-2">
          <Info className="h-4 w-4 text-blue-600 flex-shrink-0" />
          <span>You are viewing this document in read-only mode. Review, corrections, and confirmation are handled by the Buyer.</span>
        </div>
      )}

      {/* Vendor Record Header Card */}
      <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-50 text-blue-600 border border-blue-100">
              <Building2 className="h-5 w-5" aria-hidden="true" />
            </div>
            <div>
              <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                Odoo Vendor Record
              </span>
              <h2 className="text-sm font-bold text-slate-900">
                {linkedVendor ? linkedVendor.name : "No Official Vendor Linked"}
              </h2>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {linkedVendor ? (
              <span className="rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-semibold text-emerald-700 border border-emerald-200">
                TRN: {linkedVendor.trn}
              </span>
            ) : (
              <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-600 border border-slate-200">
                Unlinked
              </span>
            )}

            {isBuyer && !isConfirmed && (
              <button
                type="button"
                onClick={() => setVendorDialogOpen(true)}
                className="rounded-md border border-slate-300 bg-white px-2.5 py-1 text-xs font-medium text-slate-700 shadow-sm hover:bg-slate-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-600"
              >
                {linkedVendor ? "Change Vendor" : "Choose Vendor"}
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Header Fields Section */}
      <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-bold text-slate-900">Extracted Header Fields</h2>
          <span className="text-xs text-slate-500">{fields.length} fields</span>
        </div>

        <div className="divide-y divide-slate-100 border rounded-md">
          {fields.map((field) => {
            const isSelected = selectedHighlight?.id === field.id || selectedHighlight?.name === field.name;
            const needsReview = field.status === "needs_review" || field.status === "validation_failed";

            return (
              <div
                key={field.id}
                onClick={() =>
                  onSelectHighlight({
                    id: field.id,
                    name: field.name,
                    page: field.page,
                    bbox: field.bbox,
                    label: formatFieldName(field.name),
                  })
                }
                className={`p-3 transition-colors cursor-pointer ${
                  isSelected
                    ? "bg-blue-50/80 ring-1 ring-blue-500"
                    : needsReview
                    ? "bg-amber-50/30 hover:bg-slate-50"
                    : "hover:bg-slate-50"
                }`}
                data-testid={`field-row-${field.name}`}
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold text-slate-700">
                      {formatFieldName(field.name)}
                    </span>
                    {field.page && (
                      <span className="rounded bg-slate-100 px-1.5 py-0.2 text-[10px] text-slate-700 font-medium">
                        p.{field.page}
                      </span>
                    )}
                  </div>

                  <div className="flex items-center gap-2">
                    <ConfidenceBadge
                      confidence={field.confidence}
                      size="sm"
                    />
                    <StatusBadge status={field.status} size="sm" />
                  </div>
                </div>

                {/* Field Value Display */}
                <div className="mt-1.5 flex items-center justify-between gap-4">
                  <div className="font-mono text-xs font-medium text-slate-900 truncate">
                    {field.value_raw ?? <span className="text-slate-400 italic">Not found</span>}
                  </div>

                  {/* Actions for Buyer */}
                  {isBuyer && !isConfirmed && (
                    <div className="flex items-center gap-1.5" onClick={(e) => e.stopPropagation()}>
                      <button
                        type="button"
                        onClick={() => setEditingField(field)}
                        className="rounded p-1 text-slate-500 hover:bg-slate-100 hover:text-blue-600"
                        title="Correct value"
                        aria-label={`Correct ${formatFieldName(field.name)}`}
                      >
                        <Edit2 className="h-3.5 w-3.5" />
                      </button>

                      {needsReview && (
                        <button
                          type="button"
                          onClick={() => handleConfirmField(field)}
                          className="inline-flex items-center gap-1 rounded bg-emerald-50 px-2 py-0.5 text-[11px] font-semibold text-emerald-700 hover:bg-emerald-100 border border-emerald-200"
                          title="Confirm this field value"
                        >
                          <Check className="h-3 w-3" />
                          <span>Confirm</span>
                        </button>
                      )}
                    </div>
                  )}
                </div>

                {/* Validation message if any */}
                {field.validation_msg && (
                  <div className="mt-2 rounded bg-rose-50 border border-rose-200 p-2 text-xs text-rose-700 flex items-start gap-1.5">
                    <AlertTriangle className="h-3.5 w-3.5 flex-shrink-0 mt-0.5 text-rose-600" />
                    <span>{field.validation_msg}</span>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Extracted Line Items Section */}
      <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-bold text-slate-900">Extracted Line Items</h2>
          <span className="text-xs text-slate-500">{lines.length} lines</span>
        </div>

        {lines.length === 0 ? (
          <div className="p-4 text-center text-xs text-slate-500 italic border rounded-md bg-slate-50">
            No line items extracted for this document type.
          </div>
        ) : (
          <div className="overflow-x-auto border rounded-md" tabIndex={0} role="region" aria-label="Extracted line items table">
            <table className="min-w-full divide-y divide-slate-200 text-left text-xs">
              <thead className="bg-slate-50 text-[11px] font-semibold uppercase text-slate-600">
                <tr>
                  <th scope="col" className="px-3 py-2">#</th>
                  <th scope="col" className="px-3 py-2">Description</th>
                  <th scope="col" className="px-3 py-2 text-right">Qty</th>
                  <th scope="col" className="px-3 py-2 text-right">Unit Price</th>
                  <th scope="col" className="px-3 py-2 text-right">Total</th>
                  <th scope="col" className="px-3 py-2 text-center">Confidence</th>
                  <th scope="col" className="px-3 py-2 text-center">Status</th>
                  {isBuyer && !isConfirmed && <th scope="col" className="px-3 py-2 text-right">Action</th>}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 bg-white">
                {lines.map((line) => {
                  const isSelected = selectedHighlight?.id === line.id;
                  const needsReview = line.status === "needs_review" || line.status === "validation_failed";

                  return (
                    <tr
                      key={line.id}
                      onClick={() =>
                        onSelectHighlight({
                          id: line.id,
                          page: line.page,
                          bbox: line.bbox,
                          label: `Line #${line.line_no}: ${line.description || "Item"}`,
                        })
                      }
                      className={`cursor-pointer transition-colors ${
                        isSelected
                          ? "bg-blue-50/80 font-medium"
                          : needsReview
                          ? "bg-amber-50/40 hover:bg-slate-50"
                          : "hover:bg-slate-50"
                      }`}
                      data-testid={`line-row-${line.line_no}`}
                    >
                      <td className="px-3 py-2 text-slate-500">{line.line_no}</td>
                      <td className="px-3 py-2 text-slate-900 max-w-xs truncate">
                        <span className="font-semibold text-slate-700">{line.item_code ? `[${line.item_code}] ` : ""}</span>
                        {line.description ?? "—"}
                      </td>
                      <td className="px-3 py-2 text-right font-mono text-slate-700">
                        {line.qty != null ? `${line.qty} ${line.uom || ""}` : "—"}
                      </td>
                      <td className="px-3 py-2 text-right font-mono text-slate-700">
                        {line.unit_price != null ? formatCurrency(line.unit_price) : "—"}
                      </td>
                      <td className="px-3 py-2 text-right font-mono font-semibold text-slate-900">
                        {line.line_total != null ? formatCurrency(line.line_total) : "—"}
                      </td>
                      <td className="px-3 py-2 text-center">
                        <ConfidenceBadge confidence={line.confidence} size="sm" />
                      </td>
                      <td className="px-3 py-2 text-center">
                        <StatusBadge status={line.status} size="sm" />
                      </td>
                      {isBuyer && !isConfirmed && (
                        <td className="px-3 py-2 text-right" onClick={(e) => e.stopPropagation()}>
                          {needsReview && (
                            <button
                              type="button"
                              onClick={() => handleConfirmLine(line)}
                              className="rounded bg-emerald-50 px-2 py-0.5 text-[11px] font-semibold text-emerald-700 hover:bg-emerald-100 border border-emerald-200"
                            >
                              Confirm
                            </button>
                          )}
                        </td>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Open Items Panel (Blocks confirmation if any open) */}
      {openSummary.isOpen && (
        <div
          className="rounded-lg border border-amber-300 bg-amber-50 p-4"
          data-testid="open-items-banner"
          role="status"
        >
          <div className="flex items-start gap-2.5">
            <AlertTriangle className="h-5 w-5 text-amber-700 flex-shrink-0 mt-0.5" />
            <div>
              <h2 className="text-sm font-bold text-amber-900">
                Cannot Confirm Document: {openSummary.count} Open Item(s)
              </h2>
              <p className="mt-1 text-xs text-amber-800 leading-relaxed">
                All low-confidence scores, validation mismatches, duplicate warnings, and security flags must be confirmed or acknowledged before this document can enter downstream comparisons, orders, or matches.
              </p>

              <ul className="mt-3 space-y-1.5 text-xs text-amber-900 divide-y divide-amber-200/50">
                {openSummary.items.map((item) => (
                  <li key={item.id} className="pt-1.5 flex items-center justify-between gap-2">
                    <div>
                      <span className="font-semibold">{item.title}:</span>{" "}
                      <span className="text-amber-800">{item.message}</span>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* Confirmation Error Display if any */}
      {confirmError && (
        <div className="rounded-md border border-rose-300 bg-rose-50 p-3 text-xs text-rose-800">
          <span className="font-semibold">Confirmation Blocked:</span> {confirmError}
        </div>
      )}

      {/* Document Confirmation Actions Footer */}
      {isBuyer && (
        <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-bold text-slate-900">Document Status:</span>
              <StatusBadge status={document.status} />
            </div>
            <p className="text-xs text-slate-500 mt-0.5">
              {isConfirmed
                ? "This document is verified and confirmed."
                : openSummary.isOpen
                ? `Resolve ${openSummary.count} open item(s) to enable confirmation.`
                : "All fields and checks verified. Ready for confirmation."}
            </p>
          </div>

          <div>
            {isConfirmed ? (
              <span className="inline-flex items-center gap-1.5 rounded-md bg-emerald-50 px-4 py-2 text-sm font-semibold text-emerald-800 border border-emerald-200">
                <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
                Confirmed by Buyer
              </span>
            ) : (
              <button
                type="button"
                onClick={handleConfirmDocument}
                disabled={openSummary.isOpen || confirmingDoc}
                data-testid="confirm-document-btn"
                className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-600"
              >
                <FileCheck className="h-4 w-4" aria-hidden="true" />
                <span>{confirmingDoc ? "Confirming..." : "Confirm Document"}</span>
              </button>
            )}
          </div>
        </div>
      )}

      {/* Field Edit Dialog */}
      {editingField && (
        <FieldEditDialog
          isOpen={Boolean(editingField)}
          fieldName={editingField.name}
          fieldLabel={formatFieldName(editingField.name)}
          currentValue={editingField.value_raw || ""}
          onClose={() => setEditingField(null)}
          onSave={handleSaveFieldCorrection}
        />
      )}

      {/* Vendor Selection Dialog */}
      {vendorDialogOpen && (
        <VendorSelectDialog
          isOpen={vendorDialogOpen}
          currentVendorId={document.vendor_id}
          onClose={() => setVendorDialogOpen(false)}
          onSave={handleSaveVendor}
        />
      )}
    </div>
  );
};
