"use client";

import React, { useState, useEffect } from "react";
import { Settings, Users, Sliders, Server, ShieldAlert } from "lucide-react";
import { UserManagement } from "@/components/admin/UserManagement";
import { SettingsManagement } from "@/components/admin/SettingsManagement";
import { IntegrationsManagement } from "@/components/admin/IntegrationsManagement";
import { Toast, type ToastState } from "@/components/ui/Toast";
import type { UserPrincipal } from "@/lib/types";

export default function AdminPage() {
  const [user, setUser] = useState<UserPrincipal | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"users" | "settings" | "integrations">("users");
  const [toast, setToast] = useState<ToastState | null>(null);

  useEffect(() => {
    fetch("/api/v1/me")
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => setUser(data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <div className="py-12 text-center text-xs text-slate-500">Loading admin console...</div>;
  }

  const isAdmin = user?.roles.includes("admin");

  if (!isAdmin) {
    return (
      <div className="rounded-lg border border-rose-200 bg-rose-50 p-8 text-center text-xs text-rose-800">
        <ShieldAlert className="h-8 w-8 text-rose-600 mx-auto mb-2" />
        <h2 className="text-base font-bold text-rose-900">Access Restricted</h2>
        <p className="mt-1">
          This system configuration area is restricted strictly to users with the Admin role.
        </p>
      </div>
    );
  }

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

      {/* Header */}
      <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-xl font-bold text-slate-900 flex items-center gap-2">
              <Settings className="h-5 w-5 text-slate-700" />
              System Administration
            </h1>
            <p className="mt-1 text-xs text-slate-500">
              Manage accounts and delegated roles, configure approval tiers and matching tolerances, and inspect ERP adapters.
            </p>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="mt-6 border-b border-slate-200">
          <nav className="-mb-px flex space-x-8" aria-label="Admin Tabs">
            {[
              { id: "users", label: "Users & Roles", icon: Users },
              { id: "settings", label: "Thresholds & Tolerances", icon: Sliders },
              { id: "integrations", label: "ERP Integrations", icon: Server },
            ].map((tab) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id as any)}
                  className={`inline-flex items-center gap-2 py-3 px-1 border-b-2 text-xs font-semibold transition-colors ${
                    isActive
                      ? "border-blue-600 text-blue-600"
                      : "border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300"
                  }`}
                >
                  <Icon className="h-4 w-4" />
                  <span>{tab.label}</span>
                </button>
              );
            })}
          </nav>
        </div>
      </div>

      {/* Tab Panels */}
      {activeTab === "users" && user && (
        <UserManagement
          currentUserId={user.id}
          onToast={(type, title, message) => setToast({ type, title, message })}
        />
      )}

      {activeTab === "settings" && (
        <SettingsManagement
          onToast={(type, title, message) => setToast({ type, title, message })}
        />
      )}

      {activeTab === "integrations" && <IntegrationsManagement />}
    </div>
  );
}
