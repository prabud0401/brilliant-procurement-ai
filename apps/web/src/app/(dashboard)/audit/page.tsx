"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  Shield,
  Download,
  CheckCircle2,
  AlertTriangle,
  Search,
  Filter,
  RefreshCw,
  Loader2,
  ExternalLink,
} from "lucide-react";
import { formatGSTDate } from "@/lib/formatters";
import type { UserPrincipal } from "@/lib/types";

interface AuditItem {
  id: number;
  occurred_at: string;
  actor_id?: string | null;
  actor_roles?: string[] | null;
  action: string;
  entity_type: string;
  entity_id?: string | null;
  entity_label?: string | null;
  before?: Record<string, any> | null;
  after?: Record<string, any> | null;
  reason?: string | null;
  ai_model?: string | null;
  prompt_version?: string | null;
  request_id?: string | null;
  hash: string;
}

interface AuditVerifyResult {
  valid: boolean;
  count: number;
  error?: string | null;
}

export default function AuditPage() {
  const [logs, setLogs] = useState<AuditItem[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [user, setUser] = useState<UserPrincipal | null>(null);

  // Filters
  const [entityFilter, setEntityFilter] = useState("all");
  const [actionFilter, setActionFilter] = useState("");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");

  // Verification state
  const [verifying, setVerifying] = useState(false);
  const [verifyResult, setVerifyResult] = useState<AuditVerifyResult | null>(null);

  useEffect(() => {
    fetch("/api/v1/me")
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => setUser(data))
      .catch(() => {});
  }, []);

  const loadAuditLogs = useCallback((cursor?: string | null) => {
    setLoading(true);
    const params = new URLSearchParams();
    params.append("limit", "25");
    if (cursor) params.append("cursor", cursor);
    if (entityFilter !== "all") params.append("entity_type", entityFilter);
    if (actionFilter.trim()) params.append("action", actionFilter.trim());
    if (fromDate) params.append("from", new Date(fromDate).toISOString());
    if (toDate) params.append("to", new Date(toDate).toISOString());

    fetch(`/api/v1/audit?${params.toString()}`)
      .then((res) => (res.ok ? res.json() : { items: [], next_cursor: null }))
      .then((data) => {
        setLogs(data.items || []);
        setNextCursor(data.next_cursor || null);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [entityFilter, actionFilter, fromDate, toDate]);

  useEffect(() => {
    loadAuditLogs();
  }, [loadAuditLogs]);

  const handleVerifyChain = async () => {
    try {
      setVerifying(true);
      const res = await fetch("/api/v1/audit/verify");
      if (res.ok) {
        const data = await res.json();
        setVerifyResult(data);
      } else {
        setVerifyResult({ valid: false, count: 0, error: "Failed to verify audit chain." });
      }
    } catch {
      setVerifyResult({ valid: false, count: 0, error: "Network error during verification." });
    } finally {
      setVerifying(false);
    }
  };

  const handleExportCsv = () => {
    const params = new URLSearchParams();
    if (fromDate) params.append("from", new Date(fromDate).toISOString());
    if (toDate) params.append("to", new Date(toDate).toISOString());
    window.open(`/api/v1/audit/export.csv?${params.toString()}`, "_blank");
  };

  const isAdmin = user?.roles.includes("admin");

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-xl font-bold text-slate-900 flex items-center gap-2">
              <Shield className="h-5 w-5 text-blue-600" />
              Audit Trail & Integrity Log
            </h1>
            <p className="mt-1 text-xs text-slate-500">
              Cryptographically chained SHA-256 tamper-evident record of all procurement events, field corrections, approvals, and policy updates.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            {/* Hash Chain Verify Button */}
            <button
              type="button"
              onClick={handleVerifyChain}
              disabled={verifying}
              data-testid="verify-audit-chain-btn"
              className="inline-flex items-center gap-2 rounded-md border border-slate-300 bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 shadow-sm hover:bg-slate-50 disabled:opacity-50"
            >
              <RefreshCw className={`h-4 w-4 ${verifying ? "animate-spin text-blue-600" : "text-slate-500"}`} />
              <span>{verifying ? "Verifying..." : "Verify Hash Chain"}</span>
            </button>

            {/* CSV Export Button (Admin Only per US-24/Design 7.2) */}
            {isAdmin && (
              <button
                type="button"
                onClick={handleExportCsv}
                data-testid="export-audit-csv-btn"
                className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-blue-700"
              >
                <Download className="h-4 w-4" />
                <span>Export Audit CSV</span>
              </button>
            )}
          </div>
        </div>

        {/* Verification Result Banner */}
        {verifyResult && (
          <div
            className={`mt-4 rounded-md p-3 text-xs flex items-center justify-between border ${
              verifyResult.valid
                ? "bg-emerald-50 border-emerald-200 text-emerald-900"
                : "bg-rose-50 border-rose-200 text-rose-900"
            }`}
            data-testid="audit-verify-result-banner"
          >
            <div className="flex items-center gap-2">
              {verifyResult.valid ? (
                <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
              ) : (
                <AlertTriangle className="h-4 w-4 text-rose-600 shrink-0" />
              )}
              <span>
                {verifyResult.valid ? (
                  <>
                    <strong>Hash-Chain Verification Passed:</strong> All {verifyResult.count} contiguous audit log entries verified against cumulative SHA-256 digests.
                  </>
                ) : (
                  <>
                    <strong>Verification Failed:</strong> {verifyResult.error || "Chain integrity broken."}
                  </>
                )}
              </span>
            </div>
            <button
              type="button"
              onClick={() => setVerifyResult(null)}
              className="text-[11px] font-semibold text-slate-500 hover:text-slate-800"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Filter Toolbar */}
        <div className="mt-6 pt-4 border-t border-slate-100 grid grid-cols-1 sm:grid-cols-4 gap-4 text-xs">
          <div>
            <label htmlFor="audit-entity-filter" className="block font-semibold text-slate-600 mb-1">
              Entity Type:
            </label>
            <select
              id="audit-entity-filter"
              value={entityFilter}
              onChange={(e) => setEntityFilter(e.target.value)}
              className="w-full rounded border border-slate-300 p-1.5 text-slate-900"
            >
              <option value="all">All Entities</option>
              <option value="purchase_request">Purchase Request</option>
              <option value="purchase_order">Purchase Order</option>
              <option value="comparison">Quote Comparison</option>
              <option value="document">Document</option>
              <option value="match">Match</option>
              <option value="setting">Setting / Policy</option>
              <option value="user">User Account</option>
              <option value="auth">Authentication</option>
            </select>
          </div>

          <div>
            <label htmlFor="audit-action-filter" className="block font-semibold text-slate-600 mb-1">
              Action Name:
            </label>
            <input
              id="audit-action-filter"
              type="text"
              value={actionFilter}
              onChange={(e) => setActionFilter(e.target.value)}
              placeholder="e.g. pr.created, po.approved..."
              className="w-full rounded border border-slate-300 p-1.5 text-slate-900"
            />
          </div>

          <div>
            <label htmlFor="audit-from-date" className="block font-semibold text-slate-600 mb-1">
              From Date:
            </label>
            <input
              id="audit-from-date"
              type="date"
              value={fromDate}
              onChange={(e) => setFromDate(e.target.value)}
              className="w-full rounded border border-slate-300 p-1.5 text-slate-900"
            />
          </div>

          <div>
            <label htmlFor="audit-to-date" className="block font-semibold text-slate-600 mb-1">
              To Date:
            </label>
            <input
              id="audit-to-date"
              type="date"
              value={toDate}
              onChange={(e) => setToDate(e.target.value)}
              className="w-full rounded border border-slate-300 p-1.5 text-slate-900"
            />
          </div>
        </div>
      </div>

      {/* Logs Table */}
      <div className="rounded-lg border border-slate-200 bg-white shadow-sm overflow-hidden">
        {loading ? (
          <div className="py-12 text-center text-xs text-slate-500">Loading audit log entries...</div>
        ) : logs.length === 0 ? (
          <div className="py-12 text-center text-xs text-slate-500">No matching audit entries found.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-xs">
              <thead className="bg-slate-50 text-[11px] font-semibold uppercase text-slate-500">
                <tr>
                  <th className="px-4 py-3 text-left w-16">ID</th>
                  <th className="px-4 py-3 text-left">Timestamp (GST)</th>
                  <th className="px-4 py-3 text-left">Action</th>
                  <th className="px-4 py-3 text-left">Entity</th>
                  <th className="px-4 py-3 text-left">Actor Roles</th>
                  <th className="px-4 py-3 text-left">Justification / Reason</th>
                  <th className="px-4 py-3 text-right">Hash Digest</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {logs.map((log) => (
                  <tr key={log.id} className="hover:bg-slate-50/50">
                    <td className="px-4 py-2.5 font-mono text-slate-400 font-bold">#{log.id}</td>
                    <td className="px-4 py-2.5 text-slate-700 whitespace-nowrap">
                      {formatGSTDate(log.occurred_at)}
                    </td>
                    <td className="px-4 py-2.5 font-mono font-semibold text-blue-700">
                      {log.action}
                    </td>
                    <td className="px-4 py-2.5">
                      <span className="font-semibold text-slate-800">
                        {log.entity_label || `${log.entity_type} —`}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-slate-600">
                      {log.actor_roles && log.actor_roles.length > 0 ? (
                        <div className="flex flex-wrap gap-1">
                          {log.actor_roles.map((r) => (
                            <span key={r} className="rounded bg-slate-100 px-1.5 py-0.2 text-[10px] font-medium uppercase text-slate-700">
                              {r}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <span className="text-slate-400">System</span>
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-slate-700 max-w-sm truncate">
                      {log.reason || "—"}
                    </td>
                    <td className="px-4 py-2.5 text-right font-mono text-[10px] text-slate-400">
                      {log.hash.slice(0, 10)}...
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        {nextCursor && (
          <div className="p-4 border-t border-slate-100 flex justify-center">
            <button
              type="button"
              onClick={() => loadAuditLogs(nextCursor)}
              className="rounded-md border border-slate-300 bg-white px-4 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 shadow-sm"
            >
              Load Next Page →
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
