"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { Plus, ShoppingCart, Filter, Search } from "lucide-react";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { formatMoneyAED, formatGSTDate } from "@/lib/formatters";
import type { PurchaseRequest } from "@/lib/flow/types";

export default function RequestsPage() {
  const [requests, setRequests] = useState<PurchaseRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");

  const loadRequests = useCallback(() => {
    setLoading(true);
    const query = statusFilter !== "all" ? `?status=${statusFilter}` : "";
    fetch(`/api/v1/purchase-requests${query}`)
      .then((res) => (res.ok ? res.json() : []))
      .then((data: PurchaseRequest[]) => setRequests(data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [statusFilter]);

  useEffect(() => {
    loadRequests();
  }, [loadRequests]);

  const filteredRequests = requests.filter((r) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase().trim();
    return (
      r.number.toLowerCase().includes(q) ||
      r.title.toLowerCase().includes(q)
    );
  });

  return (
    <div className="space-y-6">
      <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-xl font-bold text-slate-900 flex items-center gap-2">
              <ShoppingCart className="h-5 w-5 text-blue-600" />
              Purchase Requests (US-21)
            </h1>
            <p className="mt-1 text-xs text-slate-500">
              Create, review, and track purchase requests and procurement line items across company approval tiers.
            </p>
          </div>

          <Link
            href="/requests/new"
            data-testid="new-pr-link-btn"
            className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-blue-700"
          >
            <Plus className="h-4 w-4" />
            <span>New Purchase Request</span>
          </Link>
        </div>

        {/* Filters */}
        <div className="mt-6 flex flex-col sm:flex-row items-center gap-4 pt-4 border-t border-slate-100">
          <div className="relative flex-1 w-full">
            <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-slate-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by request number or title..."
              className="w-full rounded-md border border-slate-300 pl-9 pr-3 py-1.5 text-xs text-slate-900 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <label htmlFor="pr-status-filter" className="text-xs font-semibold text-slate-600">
              Status:
            </label>
            <select
              id="pr-status-filter"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-xs text-slate-900 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value="all">All Requests</option>
              <option value="draft">Draft</option>
              <option value="submitted">Submitted / Pending</option>
              <option value="approved">Approved</option>
              <option value="rejected">Rejected</option>
            </select>
          </div>
        </div>
      </div>

      {/* Requests Table */}
      <div className="rounded-lg border border-slate-200 bg-white shadow-sm overflow-hidden">
        {loading ? (
          <div className="py-12 text-center text-xs text-slate-500">Loading purchase requests...</div>
        ) : filteredRequests.length === 0 ? (
          <div className="py-12 text-center text-xs text-slate-500">
            No purchase requests found. Click &ldquo;New Purchase Request&rdquo; to create one.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-xs">
              <thead className="bg-slate-50 text-[11px] font-semibold uppercase text-slate-500">
                <tr>
                  <th className="px-4 py-3 text-left">PR Number</th>
                  <th className="px-4 py-3 text-left">Title</th>
                  <th className="px-4 py-3 text-right">Items</th>
                  <th className="px-4 py-3 text-right">Total (AED)</th>
                  <th className="px-4 py-3 text-center">Status</th>
                  <th className="px-4 py-3 text-left">Current Approver</th>
                  <th className="px-4 py-3 text-left">Created Date</th>
                  <th className="px-4 py-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredRequests.map((r) => (
                  <tr key={r.id} className="hover:bg-slate-50/50">
                    <td className="px-4 py-3 font-mono font-bold text-blue-600">
                      <Link href={`/requests/${r.id}`} className="hover:underline">
                        {r.number}
                      </Link>
                    </td>
                    <td className="px-4 py-3 font-medium text-slate-900 max-w-xs truncate">
                      {r.title}
                    </td>
                    <td className="px-4 py-3 text-right text-slate-700">{r.lines?.length || 0}</td>
                    <td className="px-4 py-3 text-right font-bold text-slate-900">
                      {formatMoneyAED(r.total_aed)}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <StatusBadge status={r.status} />
                    </td>
                    <td className="px-4 py-3 text-slate-600">
                      {r.current_approver ? (
                        <span className="font-medium text-blue-800">{r.current_approver}</span>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="px-4 py-3 text-slate-500">{formatGSTDate(r.created_at)}</td>
                    <td className="px-4 py-3 text-right">
                      <Link
                        href={`/requests/${r.id}`}
                        className="rounded border border-slate-300 px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50"
                      >
                        View
                      </Link>
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
