"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { CheckSquare, ArrowRight, ShieldCheck, Clock, CheckCircle } from "lucide-react";
import { formatMoneyAED, formatGSTDate } from "@/lib/formatters";
import type { InboxItem } from "@/lib/flow/types";

export default function ApprovalsInboxPage() {
  const [inbox, setInbox] = useState<InboxItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [forbidden, setForbidden] = useState(false);

  useEffect(() => {
    fetch("/api/v1/approvals/inbox")
      .then(async (res) => {
        if (res.status === 403) {
          setForbidden(true);
          return [];
        }
        return res.ok ? res.json() : [];
      })
      .then((data: InboxItem[]) => setInbox(data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (forbidden) {
    return (
      <div className="rounded-lg border border-rose-200 bg-rose-50 p-6 text-center text-xs text-rose-700" data-testid="approvals-access-denied">
        <h1 className="text-sm font-bold text-rose-900 mb-1">Access Denied (403 Forbidden)</h1>
        <p>Business role (Buyer or Manager) required to access approvals inbox.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        <h1 className="text-xl font-bold text-slate-900 flex items-center gap-2">
          <CheckSquare className="h-5 w-5 text-blue-600" />
          Pending Approvals Inbox (US-21, US-22)
        </h1>
        <p className="mt-1 text-xs text-slate-500">
          Commitments requiring your review and authorization. Only steps you are authorized and delegated to decide appear here. Segregation of duties is automatically verified.
        </p>
      </div>

      <div className="rounded-lg border border-slate-200 bg-white shadow-sm overflow-hidden">
        {loading ? (
          <div className="py-12 text-center text-xs text-slate-500">Loading pending approvals...</div>
        ) : inbox.length === 0 ? (
          <div className="py-12 text-center text-xs text-slate-500 flex flex-col items-center gap-2">
            <CheckCircle className="h-8 w-8 text-emerald-500" />
            <span className="font-semibold text-slate-800">Your approvals inbox is clear!</span>
            <span>No pending procurement commitments currently awaiting your sign-off.</span>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-xs">
              <thead className="bg-slate-50 text-[11px] font-semibold uppercase text-slate-500">
                <tr>
                  <th className="px-4 py-3 text-left">Subject</th>
                  <th className="px-4 py-3 text-left">Title / Purpose</th>
                  <th className="px-4 py-3 text-left">Requester</th>
                  <th className="px-4 py-3 text-left">Department</th>
                  <th className="px-4 py-3 text-center">Tier</th>
                  <th className="px-4 py-3 text-right">Commitment Value</th>
                  <th className="px-4 py-3 text-left">Submitted Date</th>
                  <th className="px-4 py-3 text-right">Decision</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {inbox.map((item) => (
                  <tr key={item.step_id} className="hover:bg-slate-50/50" data-testid={`approval-row-${item.subject_number}`}>
                    <td className="px-4 py-3 font-mono font-bold text-blue-600">
                      <Link href={`/approvals/${item.step_id}`} className="hover:underline">
                        {item.subject_number}
                      </Link>
                    </td>
                    <td className="px-4 py-3 font-semibold text-slate-900 max-w-xs truncate">
                      {item.title}
                    </td>
                    <td className="px-4 py-3 text-slate-700">{item.requester_name}</td>
                    <td className="px-4 py-3 text-slate-600">{item.department_name || "—"}</td>
                    <td className="px-4 py-3 text-center">
                      <span className="rounded bg-blue-100 text-blue-800 px-2 py-0.5 text-[10px] font-bold">
                        Tier {item.tier}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right font-bold text-slate-900 font-mono">
                      {formatMoneyAED(item.total_aed)}
                    </td>
                    <td className="px-4 py-3 text-slate-500">{formatGSTDate(item.created_at)}</td>
                    <td className="px-4 py-3 text-right">
                      <Link
                        href={`/approvals/${item.step_id}`}
                        data-testid={`review-approval-link-${item.subject_number}`}
                        className="inline-flex items-center gap-1 rounded bg-blue-600 px-3 py-1 text-xs font-semibold text-white shadow-sm hover:bg-blue-700"
                      >
                        <span>Review</span>
                        <ArrowRight className="h-3.5 w-3.5" />
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
