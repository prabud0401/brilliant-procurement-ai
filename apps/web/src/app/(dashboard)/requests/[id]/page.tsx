"use client";

import React, { useState, useEffect, use } from "react";
import { PRDetail } from "@/components/flow/PRDetail";
import { Toast, type ToastState } from "@/components/ui/Toast";
import type { PurchaseRequest } from "@/lib/flow/types";
import type { UserPrincipal } from "@/lib/types";

export default function RequestDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const [pr, setPr] = useState<PurchaseRequest | null>(null);
  const [user, setUser] = useState<UserPrincipal | null>(null);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState<ToastState | null>(null);

  useEffect(() => {
    Promise.all([
      fetch(`/api/v1/purchase-requests/${id}`),
      fetch("/api/v1/me"),
    ])
      .then(async ([prRes, meRes]) => {
        if (prRes.ok) {
          setPr(await prRes.json());
        }
        if (meRes.ok) {
          setUser(await meRes.json());
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return <div className="py-12 text-center text-xs text-slate-500">Loading purchase request...</div>;
  }

  if (!pr || !user) {
    return (
      <div className="rounded-lg border border-rose-200 bg-rose-50 p-6 text-center text-xs text-rose-700">
        Purchase request not found or access denied.
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

      <PRDetail
        pr={pr}
        userRoles={user.roles}
        userId={user.id}
        onToast={(type, title, message) => setToast({ type, title, message })}
      />
    </div>
  );
}
