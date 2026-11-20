"use client";

import React, { useState, useEffect, use } from "react";
import { ApprovalDetail } from "@/components/flow/ApprovalDetail";
import { Toast, type ToastState } from "@/components/ui/Toast";
import type { ApprovalBundle } from "@/lib/flow/types";
import type { UserPrincipal } from "@/lib/types";

export default function ApprovalDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const [bundle, setBundle] = useState<ApprovalBundle | null>(null);
  const [user, setUser] = useState<UserPrincipal | null>(null);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState<ToastState | null>(null);

  useEffect(() => {
    Promise.all([
      fetch(`/api/v1/approvals/${id}`),
      fetch("/api/v1/me"),
    ])
      .then(async ([appRes, meRes]) => {
        if (appRes.ok) {
          setBundle(await appRes.json());
        }
        if (meRes.ok) {
          setUser(await meRes.json());
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return <div className="py-12 text-center text-xs text-slate-500">Loading approval bundle...</div>;
  }

  if (!bundle || !user) {
    return (
      <div className="rounded-lg border border-rose-200 bg-rose-50 p-6 text-center text-xs text-rose-700">
        Approval step not found or you do not have permission to access it.
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

      <ApprovalDetail
        bundle={bundle}
        currentUserId={user.id}
        userRoles={user.roles}
        userLimit={user.approval_limit_aed}
        onToast={(type, title, message) => setToast({ type, title, message })}
      />
    </div>
  );
}
