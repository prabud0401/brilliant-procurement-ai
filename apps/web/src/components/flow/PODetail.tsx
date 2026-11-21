"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  FileCheck,
  Send,
  Building2,
  ExternalLink,
  CheckCircle2,
  Clock,
  Loader2,
  Share2,
} from "lucide-react";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { formatMoneyAED, formatGSTDate, formatVatRate } from "@/lib/formatters";
import type { PurchaseOrder } from "@/lib/flow/types";

export interface PODetailProps {
  po: PurchaseOrder;
  userRoles: string[];
  userId: string;
  onToast?: (type: "success" | "error" | "info" | "warning", title: string, message?: string) => void;
}

export const PODetail: React.FC<PODetailProps> = ({ po: initialPo, userRoles, userId, onToast }) => {
  const router = useRouter();
  const [po, setPo] = useState<PurchaseOrder>(initialPo);
  const [submitting, setSubmitting] = useState(false);
  const [pushing, setPushing] = useState(false);
  const [pushResult, setPushResult] = useState<{ status: string; odoo_ref: string } | null>(
    po.odoo_ref ? { status: po.status, odoo_ref: po.odoo_ref } : null
  );

  const isBuyer = userRoles.includes("buyer");
  const isDraft = po.status === "draft";
  const isApproved = po.status === "approved";
  const isSent = po.status === "sent_to_vendor";
  const canPushToOdoo = isBuyer && (isApproved || isSent);

  const handleSubmitPO = async () => {
    try {
      setSubmitting(true);
      const res = await fetch(`/api/v1/purchase-orders/${po.id}/submit`, {
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
      setPo(updated);
      onToast?.("success", "PO Submitted", `Purchase Order ${updated.number} submitted for manager approval.`);
      router.refresh();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to submit PO.";
      onToast?.("error", "Error", msg);
    } finally {
      setSubmitting(false);
    }
  };

  const handlePushToOdoo = async () => {
    try {
      setPushing(true);
      const idempotencyKey = crypto.randomUUID();
      const res = await fetch(`/api/v1/purchase-orders/${po.id}/push-to-odoo`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": idempotencyKey,
          Origin: window.location.origin,
        },
      });

      if (!res.ok) {
        const problem = await res.json().catch(() => ({}));
        throw new Error(problem.detail || problem.title || `HTTP ${res.status}`);
      }

      const result = await res.json();
      setPushResult(result);
      setPo({ ...po, status: "sent_to_vendor", odoo_ref: result.odoo_ref });
      onToast?.("success", "Pushed to Odoo (mock adapter)", `Odoo Reference: ${result.odoo_ref}`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to push to Odoo.";
      onToast?.("error", "Odoo Sync Error", msg);
    } finally {
      setPushing(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Header Card */}
      <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="flex items-center gap-3">
              <span className="font-mono text-sm font-bold text-blue-600">{po.number}</span>
              <StatusBadge status={po.status} />
              {po.odoo_ref && (
                <span className="rounded bg-indigo-50 border border-indigo-200 px-2 py-0.5 text-xs font-mono font-semibold text-indigo-700">
                  {po.odoo_ref}
                </span>
              )}
            </div>
            <h1 className="mt-1 text-xl font-bold text-slate-900">
              Purchase Order for {po.vendor_name || "Awarded Vendor"}
            </h1>
            <p className="mt-1 text-xs text-slate-500">
              Created {formatGSTDate(po.created_at)}
              {po.comparison_id && (
                <>
                  {" • "}
                  <Link href={`/comparisons/${po.comparison_id}`} className="text-blue-600 hover:underline">
                    View Sourcing Comparison
                  </Link>
                </>
              )}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {isDraft && isBuyer && (
              <button
                type="button"
                onClick={handleSubmitPO}
                disabled={submitting}
                data-testid="submit-po-btn"
                className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-blue-700 disabled:opacity-50"
              >
                <Send className="h-4 w-4" />
                <span>{submitting ? "Submitting..." : "Submit for Approval"}</span>
              </button>
            )}

            {canPushToOdoo && (
              <button
                type="button"
                onClick={handlePushToOdoo}
                disabled={pushing || isSent}
                data-testid="push-to-odoo-btn"
                className="inline-flex items-center gap-2 rounded-md bg-indigo-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-indigo-700 disabled:opacity-50"
              >
                <Share2 className="h-4 w-4" />
                <span>
                  {pushing
                    ? "Syncing with Odoo..."
                    : isSent
                    ? `Pushed to Odoo (${po.odoo_ref})`
                    : "Push to Odoo"}
                </span>
              </button>
            )}
          </div>
        </div>

        {/* Integration Notification / Odoo Status (US-27) */}
        {pushResult && (
          <div className="mt-4 rounded-md border border-indigo-200 bg-indigo-50/70 p-4 text-xs text-indigo-900 flex items-start justify-between" data-testid="odoo-push-success-banner">
            <div>
              <div className="flex items-center gap-2 font-bold text-indigo-950">
                <CheckCircle2 className="h-4 w-4 text-indigo-600" />
                <span>Successfully Synced to Odoo (mock adapter)</span>
              </div>
              <p className="mt-1 text-indigo-800">
                Purchase Order has been transmitted to ERP system of record.
                <br />
                Odoo Reference ID: <strong className="font-mono text-indigo-950">{pushResult.odoo_ref}</strong>
              </p>
            </div>
            <span className="text-[11px] font-mono bg-white px-2 py-0.5 rounded border border-indigo-200 text-indigo-700">
              Odoo (mock adapter)
            </span>
          </div>
        )}

        {po.status === "submitted" && (
          <div className="mt-4 rounded-md border border-blue-200 bg-blue-50/70 p-3 text-xs text-blue-800 flex items-center gap-2">
            <Clock className="h-4 w-4 text-blue-600" />
            <span>
              Status: Pending Approval • Waiting on:{" "}
              <strong>{po.current_approver || "Assigned Approver"}</strong>
            </span>
          </div>
        )}
      </div>

      {/* Line Items Table */}
      <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-base font-semibold text-slate-900 mb-4 flex items-center gap-2">
          <FileCheck className="h-4 w-4 text-slate-500" />
          PO Line Items ({po.lines?.length || 0})
        </h2>

        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-xs">
            <thead className="bg-slate-50 text-[11px] font-semibold uppercase text-slate-500">
              <tr>
                <th className="px-3 py-2 text-left w-12">#</th>
                <th className="px-3 py-2 text-left">Description</th>
                <th className="px-3 py-2 text-right">Qty</th>
                <th className="px-3 py-2 text-left">UOM</th>
                <th className="px-3 py-2 text-right">Unit Price</th>
                <th className="px-3 py-2 text-right">VAT Rate</th>
                <th className="px-3 py-2 text-right">Line Total (AED)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {po.lines?.map((line, idx) => (
                <tr key={line.id || idx}>
                  <td className="px-3 py-2.5 text-slate-400 font-mono">{line.line_no || idx + 1}</td>
                  <td className="px-3 py-2.5 font-medium text-slate-900">{line.description}</td>
                  <td className="px-3 py-2.5 text-right text-slate-700">{line.qty}</td>
                  <td className="px-3 py-2.5 text-slate-600">{line.uom}</td>
                  <td className="px-3 py-2.5 text-right text-slate-700">
                    {formatMoneyAED(line.unit_price)}
                  </td>
                  <td className="px-3 py-2.5 text-right text-slate-500">{formatVatRate(line.vat_rate)}</td>
                  <td className="px-3 py-2.5 text-right font-medium text-slate-900">
                    {formatMoneyAED(line.line_total)}
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="border-t border-slate-200 bg-slate-50/50">
                <td colSpan={6} className="px-3 py-2 text-right text-slate-600">
                  Subtotal:
                </td>
                <td className="px-3 py-2 text-right font-semibold text-slate-900" data-testid="po-subtotal">
                  {formatMoneyAED(po.subtotal)}
                </td>
              </tr>
              <tr className="bg-slate-50/50">
                <td colSpan={6} className="px-3 py-2 text-right text-slate-600">
                  VAT (5% Standard UAE):
                </td>
                <td className="px-3 py-2 text-right font-semibold text-slate-900" data-testid="po-vat">
                  {formatMoneyAED(po.vat)}
                </td>
              </tr>
              <tr className="border-t-2 border-slate-200 bg-slate-50 font-bold text-slate-900">
                <td colSpan={6} className="px-3 py-3 text-right">
                  Total (incl. VAT):
                </td>
                <td className="px-3 py-3 text-right text-sm text-blue-700" data-testid="po-total">
                  {formatMoneyAED(po.total)}
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>
    </div>
  );
};
