"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import {
  Layers,
  FileText,
  AlertCircle,
  CheckCircle2,
  AlertTriangle,
  Info,
} from "lucide-react";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { formatMoneyAED, formatGSTDate } from "@/lib/formatters";
import type { MatchResult } from "@/lib/flow/types";
import type { DocumentSummary } from "@/lib/documents/types";

export interface MatchDetailProps {
  match: MatchResult;
  userRoles: string[];
  onToast?: (type: "success" | "error" | "info" | "warning", title: string, message?: string) => void;
}

export const MatchDetail: React.FC<MatchDetailProps> = ({ match, userRoles }) => {
  const isComplete = match.overall_status !== "incomplete";
  const [docSummary, setDocSummary] = useState<DocumentSummary | null>(null);

  useEffect(() => {
    if (!match.invoice_document_number && !match.vendor_name && match.invoice_document_id) {
      fetch("/api/v1/documents")
        .then((res) => (res.ok ? res.json() : []))
        .then((docs: DocumentSummary[]) => {
          const found = docs.find((d) => d.id === match.invoice_document_id);
          if (found) setDocSummary(found);
        })
        .catch(() => {});
    }
  }, [match.invoice_document_id, match.invoice_document_number, match.vendor_name]);

  const vendor = match.vendor_name || docSummary?.vendor_name;
  const docNum = match.invoice_document_number || docSummary?.document_number;

  const invoiceLabel = (() => {
    if (vendor && docNum) return `${vendor} · ${docNum}`;
    if (docNum) return docNum;
    if (vendor) return vendor;
    return null;
  })();

  return (
    <div className="space-y-6">
      {/* Header Summary */}
      <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="flex items-center gap-3">
              <span className="font-mono text-xs uppercase bg-blue-100 text-blue-700 px-2 py-0.5 rounded font-bold">
                Three-Way Match
              </span>
              <StatusBadge status={match.overall_status} />
            </div>
            <h1 className="mt-1 text-xl font-bold text-slate-900">
              {invoiceLabel ? `Match Evaluation for Invoice ${invoiceLabel}` : "Match Evaluation for Invoice"}
            </h1>
            <p className="mt-1 text-xs text-slate-500">
              Evaluated {formatGSTDate(match.created_at)}
              <span className="font-mono text-[11px] text-slate-400 ml-1.5" title={match.invoice_document_id}>
                ({match.invoice_document_id.slice(0, 8)}...)
              </span>
              {" • "}
              <Link
                href={`/documents/${match.invoice_document_id}`}
                className="text-blue-600 hover:underline"
              >
                View Invoice Document
              </Link>
            </p>
          </div>

          <div>
            {match.overall_status === "matched" && (
              <span className="inline-flex items-center gap-1.5 rounded-md bg-emerald-50 border border-emerald-200 px-3.5 py-1.5 text-xs font-semibold text-emerald-800">
                <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                Ready for Payment
              </span>
            )}
            {match.overall_status === "exception" && (
              <span className="inline-flex items-center gap-1.5 rounded-md bg-rose-50 border border-rose-200 px-3.5 py-1.5 text-xs font-semibold text-rose-800">
                <AlertCircle className="h-4 w-4 text-rose-600" />
                Exceptions Open (Resolution Required)
              </span>
            )}
            {match.overall_status === "incomplete" && (
              <span className="inline-flex items-center gap-1.5 rounded-md bg-amber-50 border border-amber-200 px-3.5 py-1.5 text-xs font-semibold text-amber-800">
                <AlertTriangle className="h-4 w-4 text-amber-600" />
                Incomplete Match: Missing {match.missing_document || "Documents"}
              </span>
            )}
          </div>
        </div>

        {match.missing_document && (
          <div className="mt-4 rounded-md border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
            <strong>Missing Document:</strong> Three-way match could not complete because {match.missing_document} was not found or has not been confirmed yet.
          </div>
        )}
      </div>

      {/* Line-by-Line Result Table */}
      <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-base font-semibold text-slate-900 mb-4 flex items-center gap-2">
          <Layers className="h-4 w-4 text-slate-500" />
          Line-by-Line Match Results
        </h2>

        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-xs">
            <thead className="bg-slate-50 text-[11px] font-semibold uppercase text-slate-500">
              <tr>
                <th className="px-3 py-2 text-left w-12">#</th>
                <th className="px-3 py-2 text-left">Description</th>
                <th className="px-3 py-2 text-right">Ordered Qty</th>
                <th className="px-3 py-2 text-right">Received Qty</th>
                <th className="px-3 py-2 text-right">Invoiced Qty</th>
                <th className="px-3 py-2 text-right">PO Unit Price</th>
                <th className="px-3 py-2 text-right">Inv Unit Price</th>
                <th className="px-3 py-2 text-right">Variance (AED)</th>
                <th className="px-3 py-2 text-center w-28">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {match.lines?.map((line, idx) => {
                const invUnitPrice = line.inv_unit_price ?? line.invoice_unit_price;
                const lineNo = line.line_no ?? idx + 1;
                const description = line.description || "—";
                return (
                  <tr key={line.id || idx} className="hover:bg-slate-50/50" data-testid={`match-line-row-${idx}`}>
                    <td className="px-3 py-2.5 font-mono text-slate-400">{lineNo}</td>
                    <td className="px-3 py-2.5 font-medium text-slate-900">{description}</td>
                    <td className="px-3 py-2.5 text-right text-slate-700">{line.ordered_qty}</td>
                    <td className="px-3 py-2.5 text-right text-slate-700 font-medium">
                      {line.received_qty}
                    </td>
                    <td className="px-3 py-2.5 text-right text-slate-900 font-bold">
                      {line.invoiced_qty}
                    </td>
                    <td className="px-3 py-2.5 text-right text-slate-600">
                      {formatMoneyAED(line.po_unit_price)}
                    </td>
                    <td className="px-3 py-2.5 text-right text-slate-900 font-medium" data-testid={`inv-unit-price-${idx}`}>
                      {formatMoneyAED(invUnitPrice)}
                    </td>
                    <td className="px-3 py-2.5 text-right font-mono font-semibold">
                      <span
                        className={
                          Number(line.variance_aed) > 0
                            ? "text-rose-600"
                            : Number(line.variance_aed) < 0
                            ? "text-emerald-600"
                            : "text-slate-700"
                        }
                      >
                        {formatMoneyAED(line.variance_aed)}
                      </span>
                    </td>
                    <td className="px-3 py-2.5 text-center">
                      <StatusBadge status={line.status} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Tolerances Snapshot Card */}
      {match.tolerances_snapshot && (
        <div className="rounded-lg border border-slate-200 bg-slate-50/60 p-6 text-xs text-slate-600">
          <h3 className="font-bold text-slate-900 mb-2 flex items-center gap-1.5">
            <Info className="h-4 w-4 text-blue-600" />
            Applied Tolerances Snapshot
          </h3>
          <p className="text-slate-500 mb-3">
            Matches are evaluated against company tolerances captured at the time the match was run.
          </p>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono text-[11px]">
            <div className="bg-white p-2.5 rounded border border-slate-200">
              <span className="text-slate-400 block text-[10px]">Price Variance %</span>
              <strong className="text-slate-800">
                {String(match.tolerances_snapshot.unit_price_variance_pct ?? 2)}%
              </strong>
            </div>
            <div className="bg-white p-2.5 rounded border border-slate-200">
              <span className="text-slate-400 block text-[10px]">Price Variance Max</span>
              <strong className="text-slate-800">
                AED {String(match.tolerances_snapshot.unit_price_variance_max_aed ?? "50.00")}
              </strong>
            </div>
            <div className="bg-white p-2.5 rounded border border-slate-200">
              <span className="text-slate-400 block text-[10px]">Qty Tolerance</span>
              <strong className="text-slate-800">
                {String(match.tolerances_snapshot.invoiced_vs_received_qty_max_units ?? 0)} units
              </strong>
            </div>
            <div className="bg-white p-2.5 rounded border border-slate-200">
              <span className="text-slate-400 block text-[10px]">VAT Max Diff</span>
              <strong className="text-slate-800">
                AED {String(match.tolerances_snapshot.vat_max_difference_aed ?? "1.00")}
              </strong>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
