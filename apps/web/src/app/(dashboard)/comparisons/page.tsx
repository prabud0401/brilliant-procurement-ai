"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { GitCompare, Plus, Sparkles, Award } from "lucide-react";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { formatGSTDate } from "@/lib/formatters";
import type { Comparison } from "@/lib/flow/types";

export default function ComparisonsPage() {
  const [comparisons, setComparisons] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // In backend, comparisons can be retrieved or listed via PRs
    // Also we can query comparisons or PRs
    fetch("/api/v1/purchase-requests")
      .then((res) => (res.ok ? res.json() : []))
      .then((prs: any[]) => {
        // Find comparisons if any
        setComparisons(prs);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-6">
      <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-xl font-bold text-slate-900 flex items-center gap-2">
              <GitCompare className="h-5 w-5 text-purple-600" />
              Quote Comparisons & Sourcing Matrices (US-08)
            </h1>
            <p className="mt-1 text-xs text-slate-500">
              Evaluate competitive quotations side-by-side with 60/20/10/10 scoring, AI explanations, and audited override justifications.
            </p>
          </div>

          <Link
            href="/comparisons/new"
            className="inline-flex items-center gap-2 rounded-md bg-purple-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-purple-700"
          >
            <Plus className="h-4 w-4" />
            <span>New Comparison</span>
          </Link>
        </div>
      </div>

      <div className="rounded-lg border border-slate-200 bg-white shadow-sm p-6">
        <h2 className="text-sm font-bold text-slate-900 mb-3">Active Sourcing Projects</h2>
        <p className="text-xs text-slate-500 mb-4">
          Select a purchase request to launch or view its quote comparison matrix.
        </p>

        {loading ? (
          <div className="py-8 text-center text-xs text-slate-500">Loading procurement requests...</div>
        ) : comparisons.length === 0 ? (
          <div className="py-8 text-center text-xs text-slate-500">No requests found.</div>
        ) : (
          <div className="divide-y divide-slate-100">
            {comparisons.map((pr) => (
              <div key={pr.id} className="py-3.5 flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-bold text-blue-600">{pr.number}</span>
                    <StatusBadge status={pr.status} />
                  </div>
                  <h3 className="text-xs font-semibold text-slate-900 mt-1">{pr.title}</h3>
                  <p className="text-[11px] text-slate-500">Created {formatGSTDate(pr.created_at)}</p>
                </div>

                <div className="flex items-center gap-2">
                  <Link
                    href={`/comparisons/new?pr_id=${pr.id}`}
                    className="rounded-md border border-purple-200 bg-purple-50 px-3 py-1.5 text-xs font-semibold text-purple-700 hover:bg-purple-100"
                  >
                    Compare Quotes →
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
