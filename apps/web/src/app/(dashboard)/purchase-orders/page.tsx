"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { FileCheck, Search, Filter, ExternalLink, Share2 } from "lucide-react";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { formatMoneyAED, formatGSTDate } from "@/lib/formatters";
import type { PurchaseOrder } from "@/lib/flow/types";

export default function PurchaseOrdersPage() {
  const [orders, setOrders] = useState<PurchaseOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");

  const loadOrders = useCallback(() => {
    setLoading(true);
    const query = statusFilter !== "all" ? `?status=${statusFilter}` : "";
    fetch(`/api/v1/purchase-orders${query}`)
      .then((res) => (res.ok ? res.json() : []))
      .then((data: PurchaseOrder[]) => setOrders(data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [statusFilter]);

  useEffect(() => {
    loadOrders();
  }, [loadOrders]);

  const filteredOrders = orders.filter((po) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase().trim();
    return (
      po.number.toLowerCase().includes(q) ||
      (po.odoo_ref && po.odoo_ref.toLowerCase().includes(q)) ||
      (po.vendor_name && po.vendor_name.toLowerCase().includes(q))
    );
  });

  return (
    <div className="space-y-6">
      <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-xl font-bold text-slate-900 flex items-center gap-2">
              <FileCheck className="h-5 w-5 text-blue-600" />
              Purchase Orders (US-08, US-27)
            </h1>
            <p className="mt-1 text-xs text-slate-500">
              Manage purchase order drafts created from winning quotations, submit for financial approval, and push to Odoo ERP system of record.
            </p>
          </div>
        </div>

        {/* Filters */}
        <div className="mt-6 flex flex-col sm:flex-row items-center gap-4 pt-4 border-t border-slate-100">
          <div className="relative flex-1 w-full">
            <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-slate-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by PO number or Odoo reference..."
              className="w-full rounded-md border border-slate-300 pl-9 pr-3 py-1.5 text-xs text-slate-900 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <label htmlFor="po-status-filter" className="text-xs font-semibold text-slate-600">
              Status:
            </label>
            <select
              id="po-status-filter"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-xs text-slate-900 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value="all">All Orders</option>
              <option value="draft">Draft</option>
              <option value="submitted">Submitted / Pending</option>
              <option value="approved">Approved</option>
              <option value="sent_to_vendor">Sent to Odoo</option>
              <option value="rejected">Rejected</option>
            </select>
          </div>
        </div>
      </div>

      {/* Orders Table */}
      <div className="rounded-lg border border-slate-200 bg-white shadow-sm overflow-hidden">
        {loading ? (
          <div className="py-12 text-center text-xs text-slate-500">Loading purchase orders...</div>
        ) : filteredOrders.length === 0 ? (
          <div className="py-12 text-center text-xs text-slate-500">
            No purchase orders found. Orders are created from decided quote comparisons.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-xs">
              <thead className="bg-slate-50 text-[11px] font-semibold uppercase text-slate-500">
                <tr>
                  <th className="px-4 py-3 text-left">PO Number</th>
                  <th className="px-4 py-3 text-left">Odoo Reference</th>
                  <th className="px-4 py-3 text-right">Subtotal</th>
                  <th className="px-4 py-3 text-right">VAT (5%)</th>
                  <th className="px-4 py-3 text-right">Total (AED)</th>
                  <th className="px-4 py-3 text-center">Status</th>
                  <th className="px-4 py-3 text-left">Created Date</th>
                  <th className="px-4 py-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredOrders.map((po) => (
                  <tr key={po.id} className="hover:bg-slate-50/50">
                    <td className="px-4 py-3 font-mono font-bold text-blue-600">
                      <Link href={`/purchase-orders/${po.id}`} className="hover:underline">
                        {po.number}
                      </Link>
                    </td>
                    <td className="px-4 py-3 font-mono text-slate-700">
                      {po.odoo_ref ? (
                        <span className="rounded bg-indigo-50 border border-indigo-200 px-2 py-0.5 text-[11px] font-bold text-indigo-700">
                          {po.odoo_ref}
                        </span>
                      ) : (
                        <span className="text-slate-400">Not synced</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right text-slate-700 font-mono">
                      {formatMoneyAED(po.subtotal)}
                    </td>
                    <td className="px-4 py-3 text-right text-slate-700 font-mono">
                      {formatMoneyAED(po.vat)}
                    </td>
                    <td className="px-4 py-3 text-right font-bold text-slate-900 font-mono">
                      {formatMoneyAED(po.total)}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <StatusBadge status={po.status} />
                    </td>
                    <td className="px-4 py-3 text-slate-500">{formatGSTDate(po.created_at)}</td>
                    <td className="px-4 py-3 text-right">
                      <Link
                        href={`/purchase-orders/${po.id}`}
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
