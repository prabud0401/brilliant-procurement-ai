"use client";

import React, { useState, useEffect } from "react";
import { Share2, Server, CheckCircle2, ShieldCheck, Database, FolderSync } from "lucide-react";

interface IntegrationItem {
  adapter: string;
  name: string;
  mode: string;
  label: string;
}

export const IntegrationsManagement: React.FC = () => {
  const [integrations, setIntegrations] = useState<IntegrationItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/v1/admin/integrations")
      .then((res) => (res.ok ? res.json() : []))
      .then((data: IntegrationItem[]) => setIntegrations(data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const getAdapterIcon = (adapter: string) => {
    switch (adapter) {
      case "odoo":
        return <Database className="h-6 w-6 text-purple-600" />;
      case "sharepoint":
        return <FolderSync className="h-6 w-6 text-blue-600" />;
      case "power_automate":
        return <Share2 className="h-6 w-6 text-teal-600" />;
      case "identity":
        return <ShieldCheck className="h-6 w-6 text-indigo-600" />;
      default:
        return <Server className="h-6 w-6 text-slate-600" />;
    }
  };

  return (
    <div className="space-y-6">
      <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
          <Server className="h-5 w-5 text-indigo-600" />
          Integration Adapters & ERP Connectors (Section 8)
        </h2>
        <p className="mt-1 text-xs text-slate-500">
          The Procurement Document Assistant interfaces with Odoo ERP, Microsoft SharePoint, Power Automate, and Entra ID via pluggable Python adapters. All external systems operate through the adapter interface.
        </p>
      </div>

      {loading ? (
        <div className="py-12 text-center text-xs text-slate-500">Loading integration status...</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {integrations.map((item) => (
            <div
              key={item.adapter}
              className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm flex flex-col justify-between"
              data-testid={`integration-card-${item.adapter}`}
            >
              <div>
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-slate-50 border border-slate-100">
                      {getAdapterIcon(item.adapter)}
                    </div>
                    <div>
                      <h3 className="text-sm font-bold text-slate-900">{item.name}</h3>
                      <p className="text-xs font-mono text-slate-500">{item.label}</p>
                    </div>
                  </div>

                  <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 border border-emerald-200 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-700">
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    Connected
                  </span>
                </div>

                <div className="mt-4 pt-4 border-t border-slate-100 text-xs text-slate-600 space-y-1">
                  <div className="flex justify-between">
                    <span className="text-slate-500">Configured Mode:</span>
                    <span className="font-semibold uppercase text-slate-800">{item.mode}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Adapter Interface:</span>
                    <span className="font-mono text-[11px] text-slate-700">{item.label}</span>
                  </div>
                </div>
              </div>

              <div className="mt-4 pt-3 border-t border-slate-100 text-[11px] text-slate-500">
                {item.adapter === "odoo" && (
                  <span>System of Record for vendors, catalogues, and purchase orders.</span>
                )}
                {item.adapter === "sharepoint" && (
                  <span>Primary source of truth for procurement PDF documents.</span>
                )}
                {item.adapter === "power_automate" && (
                  <span>Orchestrates Microsoft Teams approval notifications.</span>
                )}
                {item.adapter === "identity" && (
                  <span>Validates enterprise Microsoft Entra user directory tokens.</span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
