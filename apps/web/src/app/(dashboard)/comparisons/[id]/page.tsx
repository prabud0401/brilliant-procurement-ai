"use client";

import React, { useState, useEffect, use } from "react";
import { ComparisonView } from "@/components/flow/ComparisonView";
import { Toast, type ToastState } from "@/components/ui/Toast";
import type { Comparison, PurchaseRequest } from "@/lib/flow/types";
import type { UserPrincipal } from "@/lib/types";

export default function ComparisonDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const [comp, setComp] = useState<Comparison | null>(null);
  const [pr, setPr] = useState<PurchaseRequest | null>(null);
  const [user, setUser] = useState<UserPrincipal | null>(null);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState<ToastState | null>(null);

  useEffect(() => {
    Promise.all([
      fetch(`/api/v1/comparisons/${id}`),
      fetch("/api/v1/me"),
    ])
      .then(async ([compRes, meRes]) => {
        if (compRes.ok) {
          const compData: Comparison = await compRes.json();
          setComp(compData);
          if (compData.pr_id) {
            const prRes = await fetch(`/api/v1/purchase-requests/${compData.pr_id}`);
            if (prRes.ok) {
              setPr(await prRes.json());
            }
          }
        }
        if (meRes.ok) {
          setUser(await meRes.json());
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return <div className="py-12 text-center text-xs text-slate-500">Loading quote comparison...</div>;
  }

  if (!comp || !user) {
    return (
      <div className="rounded-lg border border-rose-200 bg-rose-50 p-6 text-center text-xs text-rose-700">
        Quote comparison not found or access denied.
      </div>
    );
  }

  return (
    <div>
      {toast && (
        <Toast
          type={toast.type}
          title={toast.title}
          message={toast.message}
          onClose={() => setToast(null)}
        />
      )}

      <ComparisonView
        comparison={comp}
        prTitle={pr?.title}
        prNumber={pr?.number}
        userRoles={user.roles}
        onToast={(type, title, message) => setToast({ type, title, message })}
      />
    </div>
  );
}
