"use client";

import React, { useState, useCallback } from "react";
import {
  FileText,
  AlertTriangle,
  RefreshCw,
  GitCompare,
  Clock,
  Sparkles,
  HelpCircle,
  TrendingUp,
  ShieldCheck,
  Building2,
} from "lucide-react";
import { useToast } from "@/components/ui/Toast";

export interface FieldCorrectionRate {
  field_name: string;
  total_count: number;
  corrected_count: number;
  correction_rate: number;
}

export interface AITodayMetrics {
  calls_today: number;
  tokens_today: number;
  tokens_in_today: number;
  tokens_out_today: number;
  estimated_cost_aed: number;
  daily_budget_aed: number;
  budget_utilization_pct: number;
}

export interface DepartmentSpendMetric {
  department_id: string;
  department_name: string;
  purchase_requests_count: number;
  purchase_requests_total_aed: number;
  purchase_orders_count: number;
  purchase_orders_total_aed: number;
  pending_approvals_count: number;
}

export interface AdminMetricsResponse {
  documents_processed: number;
  total_fields: number;
  fields_needing_review_count: number;
  share_of_fields_needing_review: number;
  correction_rate_per_field: FieldCorrectionRate[];
  match_exception_rate: number;
  total_matches: number;
  exception_matches: number;
  approval_cycle_time_seconds: number | null;
  approval_cycle_time_hours: number | null;
  ai_today: AITodayMetrics;
  qa_refusal_rate: number;
  qa_total_questions: number;
  qa_refused_questions: number;
  spend_by_department?: DepartmentSpendMetric[];
}

export function MetricsClient({
  initialData,
}: {
  initialData: AdminMetricsResponse | null;
}) {
  const toast = useToast();
  const [metrics, setMetrics] = useState<AdminMetricsResponse | null>(initialData);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const fetchMetrics = useCallback(async () => {
    setIsRefreshing(true);
    setErrorMsg(null);
    try {
      const res = await fetch("/api/v1/admin/metrics", {
        headers: { Accept: "application/json" },
      });
      if (!res.ok) {
        const errorJson = await res.json().catch(() => ({}));
        throw new Error(
          errorJson.detail || errorJson.title || "Failed to load admin metrics."
        );
      }
      const data: AdminMetricsResponse = await res.json();
      setMetrics(data);
      toast.success("Observability metrics refreshed");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to refresh metrics.";
      setErrorMsg(msg);
      toast.error(msg);
    } finally {
      setIsRefreshing(false);
    }
  }, [toast]);

  if (!metrics && !isRefreshing && errorMsg) {
    return (
      <div className="mx-auto max-w-4xl py-12 text-center">
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-6">
          <AlertTriangle className="mx-auto h-8 w-8 text-rose-600 mb-2" />
          <h2 className="text-lg font-bold text-rose-900">Failed to Load Metrics</h2>
          <p className="mt-1 text-sm text-rose-700">{errorMsg}</p>
          <button
            type="button"
            onClick={fetchMetrics}
            className="mt-4 inline-flex items-center gap-1.5 rounded-md bg-rose-600 px-3.5 py-2 text-sm font-semibold text-white shadow-sm hover:bg-rose-500"
          >
            <RefreshCw className="h-4 w-4" />
            Try Again
          </button>
        </div>
      </div>
    );
  }

  const ai = metrics?.ai_today;

  return (
    <div className="space-y-8">
      {/* Top Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              Observability & Business Metrics
            </h1>
            <span className="rounded-md bg-purple-100 px-2.5 py-0.5 text-xs font-semibold text-purple-800">
              Admin Exclusive
            </span>
          </div>
          <p className="mt-1 text-sm text-slate-500">
            Real-time pipeline metrics, AI activity, and compliance telemetry per NFR-OBS-03 / design 9.1.
          </p>
        </div>

        <button
          type="button"
          onClick={fetchMetrics}
          disabled={isRefreshing}
          className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-sm font-semibold text-slate-700 shadow-sm hover:bg-slate-50 disabled:opacity-50 transition-colors"
        >
          <RefreshCw
            className={`h-4 w-4 text-slate-500 ${isRefreshing ? "animate-spin" : ""}`}
          />
          {isRefreshing ? "Refreshing..." : "Refresh Metrics"}
        </button>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {/* 1. Documents Processed */}
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-2xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Documents Processed
            </span>
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-50 text-blue-600">
              <FileText className="h-5 w-5" />
            </div>
          </div>
          <div className="mt-3">
            <span className="text-3xl font-bold tracking-tight text-slate-900">
              {metrics?.documents_processed ?? 0}
            </span>
          </div>
          <p className="mt-2 text-xs text-slate-500">
            Total procurement documents processed through OCR and extraction.
          </p>
        </div>

        {/* 2. Share of Fields Needing Review */}
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-2xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Fields Needing Review
            </span>
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-amber-50 text-amber-600">
              <AlertTriangle className="h-5 w-5" />
            </div>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-bold tracking-tight text-slate-900">
              {metrics ? `${(metrics.share_of_fields_needing_review * 100).toFixed(1)}%` : "0.0%"}
            </span>
            <span className="text-xs font-mono text-slate-500">
              ({metrics?.fields_needing_review_count ?? 0} / {metrics?.total_fields ?? 0})
            </span>
          </div>
          <p className="mt-2 text-xs text-slate-500">
            Share of fields flagged below 80% confidence or with validation errors.
          </p>
        </div>

        {/* 3. Three-Way Match Exception Rate */}
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-2xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Match Exception Rate
            </span>
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-rose-50 text-rose-600">
              <GitCompare className="h-5 w-5" />
            </div>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-bold tracking-tight text-slate-900">
              {metrics ? `${(metrics.match_exception_rate * 100).toFixed(1)}%` : "0.0%"}
            </span>
            <span className="text-xs font-mono text-slate-500">
              ({metrics?.exception_matches ?? 0} / {metrics?.total_matches ?? 0} matches)
            </span>
          </div>
          <p className="mt-2 text-xs text-slate-500">
            Invoices exceeding price or quantity tolerances during 3-way matching.
          </p>
        </div>

        {/* 4. Approval Cycle Time */}
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-2xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Approval Cycle Time
            </span>
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600">
              <Clock className="h-5 w-5" />
            </div>
          </div>
          <div className="mt-3">
            <span className="text-3xl font-bold tracking-tight text-slate-900">
              {metrics?.approval_cycle_time_hours != null
                ? `${metrics.approval_cycle_time_hours} hrs`
                : metrics?.approval_cycle_time_seconds != null
                ? `${metrics.approval_cycle_time_seconds} sec`
                : "–"}
            </span>
          </div>
          <p className="mt-2 text-xs text-slate-500">
            Average time from step assignment to approval decision.
          </p>
        </div>

        {/* 5. Q&A Refusal Rate */}
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-2xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Q&A Refusal Rate
            </span>
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-50 text-indigo-600">
              <HelpCircle className="h-5 w-5" />
            </div>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-bold tracking-tight text-slate-900">
              {metrics ? `${(metrics.qa_refusal_rate * 100).toFixed(1)}%` : "0.0%"}
            </span>
            <span className="text-xs font-mono text-slate-500">
              ({metrics?.qa_refused_questions ?? 0} / {metrics?.qa_total_questions ?? 0} questions)
            </span>
          </div>
          <p className="mt-2 text-xs text-slate-500">
            Questions declined due to lack of accessible grounding evidence.
          </p>
        </div>

        {/* 6. AI Compliance / Safety */}
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-2xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              AI Security & Safety
            </span>
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-teal-50 text-teal-600">
              <ShieldCheck className="h-5 w-5" />
            </div>
          </div>
          <div className="mt-3">
            <span className="text-3xl font-bold tracking-tight text-slate-900">Active</span>
          </div>
          <p className="mt-2 text-xs text-slate-500">
            Strict injection screening, PII redaction, and hallucination grounding enabled.
          </p>
        </div>
      </div>

      {/* AI Activity & Token Consumption Section */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-2xs">
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-100 pb-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-50 text-blue-600">
              <Sparkles className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold tracking-tight text-slate-900">
                AI Invocations & Token Usage Today
              </h2>
              <p className="text-xs text-slate-500">
                Tracking LLM and Document Intelligence usage and token throughput (UTC).
              </p>
            </div>
          </div>
        </div>

        <div className="mt-6 grid grid-cols-1 gap-6 md:grid-cols-2">
          {/* AI Calls today */}
          <div className="rounded-lg bg-slate-50 p-4 border border-slate-100">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              AI Invocations Today
            </span>
            <p className="mt-1 text-2xl font-bold text-slate-900">{ai?.calls_today ?? 0}</p>
            <p className="mt-1 text-[11px] text-slate-500">Extractions & Q&A generation calls</p>
          </div>

          {/* Tokens today */}
          <div className="rounded-lg bg-slate-50 p-4 border border-slate-100">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Total Tokens Today
            </span>
            <p className="mt-1 text-2xl font-bold text-slate-900">
              {(ai?.tokens_today ?? 0).toLocaleString()}
            </p>
            <p className="mt-1 text-[11px] text-slate-500">
              In: {(ai?.tokens_in_today ?? 0).toLocaleString()} • Out:{" "}
              {(ai?.tokens_out_today ?? 0).toLocaleString()}
            </p>
          </div>
        </div>
      </div>

      {/* Field Correction Rates Table */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-2xs">
        <div className="flex items-center gap-2 mb-4">
          <TrendingUp className="h-5 w-5 text-blue-600" />
          <h2 className="text-lg font-bold tracking-tight text-slate-900">
            Field Correction Rate by Field Type
          </h2>
        </div>
        <p className="text-xs text-slate-500 mb-4">
          Identifies fields that human buyers frequently adjust after AI extraction, pinpointing prompt or OCR accuracy bottlenecks.
        </p>

        {(!metrics?.correction_rate_per_field || metrics.correction_rate_per_field.length === 0) ? (
          <div className="py-8 text-center text-sm text-slate-500">
            No extracted field data recorded yet.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
              <thead className="bg-slate-50 text-xs font-semibold uppercase tracking-wider text-slate-600">
                <tr>
                  <th scope="col" className="px-4 py-3">Field Name</th>
                  <th scope="col" className="px-4 py-3 text-right">Total Extracted</th>
                  <th scope="col" className="px-4 py-3 text-right">Manual Corrections</th>
                  <th scope="col" className="px-4 py-3 text-right">Correction Rate</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 bg-white">
                {metrics.correction_rate_per_field.map((item) => (
                  <tr key={item.field_name} className="hover:bg-slate-50/80 transition-colors">
                    <td className="px-4 py-3 font-medium text-slate-900 font-mono text-xs">
                      {item.field_name}
                    </td>
                    <td className="px-4 py-3 text-right text-slate-600 font-mono text-xs">
                      {item.total_count}
                    </td>
                    <td className="px-4 py-3 text-right text-slate-600 font-mono text-xs">
                      {item.corrected_count}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <span
                        className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                          item.correction_rate > 0.3
                            ? "bg-rose-100 text-rose-800"
                            : item.correction_rate > 0.1
                            ? "bg-amber-100 text-amber-800"
                            : "bg-emerald-100 text-emerald-800"
                        }`}
                      >
                        {(item.correction_rate * 100).toFixed(1)}%
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Spend by Department Table */}
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-2xs">
        <div className="flex items-center gap-2 mb-4">
          <Building2 className="h-5 w-5 text-blue-600" />
          <h2 className="text-lg font-bold tracking-tight text-slate-900">
            Spend by Department
          </h2>
        </div>
        <p className="text-xs text-slate-500 mb-4">
          Aggregated procurement spend and approval volume across all active departments.
        </p>

        {(!metrics?.spend_by_department || metrics.spend_by_department.length === 0) ? (
          <div className="py-8 text-center text-sm text-slate-500">
            No department spend data available.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
              <thead className="bg-slate-50 text-xs font-semibold uppercase tracking-wider text-slate-600">
                <tr>
                  <th scope="col" className="px-4 py-3">Department</th>
                  <th scope="col" className="px-4 py-3 text-right">Purchase Requests</th>
                  <th scope="col" className="px-4 py-3 text-right">PR Total (AED)</th>
                  <th scope="col" className="px-4 py-3 text-right">Purchase Orders</th>
                  <th scope="col" className="px-4 py-3 text-right">PO Total (AED)</th>
                  <th scope="col" className="px-4 py-3 text-right">Pending Approvals</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 bg-white">
                {metrics.spend_by_department.map((dept) => (
                  <tr key={dept.department_id || dept.department_name} className="hover:bg-slate-50/80 transition-colors">
                    <td className="px-4 py-3 font-medium text-slate-900">
                      {dept.department_name}
                    </td>
                    <td className="px-4 py-3 text-right text-slate-600 font-mono text-xs">
                      {dept.purchase_requests_count}
                    </td>
                    <td className="px-4 py-3 text-right text-slate-900 font-mono text-xs font-medium">
                      AED {dept.purchase_requests_total_aed.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </td>
                    <td className="px-4 py-3 text-right text-slate-600 font-mono text-xs">
                      {dept.purchase_orders_count}
                    </td>
                    <td className="px-4 py-3 text-right text-slate-900 font-mono text-xs font-medium">
                      AED {dept.purchase_orders_total_aed.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <span
                        className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                          dept.pending_approvals_count > 0
                            ? "bg-amber-100 text-amber-800"
                            : "bg-slate-100 text-slate-600"
                        }`}
                      >
                        {dept.pending_approvals_count}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
