"use client";

import React, { useState } from "react";
import { PRForm } from "@/components/flow/PRForm";
import { Toast, type ToastState } from "@/components/ui/Toast";

export default function NewRequestPage() {
  const [toast, setToast] = useState<ToastState | null>(null);

  return (
    <div className="space-y-6">
      {toast && (
        <Toast
          type={toast.type}
          title={toast.title}
          message={toast.message}
          onClose={() => setToast(null)}
        />
      )}

      <div>
        <h1 className="text-xl font-bold text-slate-900">Create Purchase Request (US-21)</h1>
        <p className="mt-1 text-xs text-slate-500">
          Specify procurement requirements and product line items. Totals will be computed live in AED.
        </p>
      </div>

      <PRForm
        onToast={(type, title, message) => setToast({ type, title, message })}
      />
    </div>
  );
}
