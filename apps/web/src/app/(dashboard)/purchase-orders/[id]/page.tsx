"use client";

import React, { useState, useEffect, use } from "react";
import { PODetail } from "@/components/flow/PODetail";
import { Toast, type ToastState } from "@/components/ui/Toast";
import type { PurchaseOrder } from "@/lib/flow/types";
import type { UserPrincipal } from "@/lib/types";

export default function PurchaseOrderDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const [po, setPo] = useState<PurchaseOrder | null>(null);
  const [user, setUser] = useState<UserPrincipal | null>(null);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState<ToastState | null>(null);

  useEffect(() => {
    Promise.all([
      fetch(`/api/v1/purchase-orders/${id}`),
      fetch("/api/v1/me"),
    ])
      .then(async ([poRes, meRes]) => {
        if (poRes.ok) {
          setPo(await poRes.json());
        }
        if (meRes.ok) {
          setUser(await meRes.json());
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return <div className="py-12 text-center text-xs text-slate-500">Loading purchase order...</div>;
  }

  if (!po || !user) {
    return (
      <div className="rounded-lg border border-rose-200 bg-rose-50 p-6 text-center text-xs text-rose-700">
        Purchase order not found or access denied.
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

      <PODetail
        po={po}
        userRoles={user.roles}
        userId={user.id}
        onToast={(type, title, message) => setToast({ type, title, message })}
      />
    </div>
  );
}
