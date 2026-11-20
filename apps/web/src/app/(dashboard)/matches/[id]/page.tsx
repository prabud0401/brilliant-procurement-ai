"use client";

import React, { useState, useEffect, use } from "react";
import { MatchDetail } from "@/components/flow/MatchDetail";
import { Toast, type ToastState } from "@/components/ui/Toast";
import type { MatchResult } from "@/lib/flow/types";
import type { UserPrincipal } from "@/lib/types";

export default function MatchDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const [match, setMatch] = useState<MatchResult | null>(null);
  const [user, setUser] = useState<UserPrincipal | null>(null);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState<ToastState | null>(null);

  useEffect(() => {
    Promise.all([
      fetch(`/api/v1/matches/${id}`),
      fetch("/api/v1/me"),
    ])
      .then(async ([matchRes, meRes]) => {
        if (matchRes.ok) {
          setMatch(await matchRes.json());
        }
        if (meRes.ok) {
          setUser(await meRes.json());
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return <div className="py-12 text-center text-xs text-slate-500">Loading match result...</div>;
  }

  if (!match || !user) {
    return (
      <div className="rounded-lg border border-rose-200 bg-rose-50 p-6 text-center text-xs text-rose-700">
        Match result not found or access denied.
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

      <MatchDetail
        match={match}
        userRoles={user.roles}
        onToast={(type, title, message) => setToast({ type, title, message })}
      />
    </div>
  );
}
