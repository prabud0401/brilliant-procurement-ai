"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  Sliders,
  CheckCircle2,
  History,
  Save,
  AlertCircle,
  Loader2,
} from "lucide-react";
import { formatGSTDate } from "@/lib/formatters";

interface SettingItem {
  key: string;
  value: any;
  version: number;
  updated_at?: string;
}

interface SettingHistory {
  id: number;
  occurred_at: string;
  actor_name?: string | null;
  action: string;
  version?: number | null;
  value: any;
  reason?: string | null;
}

export interface SettingsManagementProps {
  onToast?: (type: "success" | "error" | "info" | "warning", title: string, message?: string) => void;
}

export const SettingsManagement: React.FC<SettingsManagementProps> = ({ onToast }) => {
  const [activeTab, setActiveTab] = useState<"thresholds" | "tolerances" | "buyer-policy">("thresholds");
  const [currentSetting, setCurrentSetting] = useState<SettingItem | null>(null);
  const [history, setHistory] = useState<SettingHistory[]>([]);
  const [jsonText, setJsonText] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const loadSettingData = useCallback(async (key: string) => {
    try {
      setLoading(true);
      setErrorMsg(null);
      const [settingRes, histRes] = await Promise.all([
        fetch(`/api/v1/settings/${key}`),
        fetch(`/api/v1/admin/settings/${key}/history`),
      ]);

      if (settingRes.ok) {
        const data: SettingItem = await settingRes.json();
        setCurrentSetting(data);
        setJsonText(JSON.stringify(data.value, null, 2));
      }
      if (histRes.ok) {
        setHistory(await histRes.json());
      }
    } catch (err: unknown) {
      setErrorMsg("Failed to load setting data.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSettingData(activeTab);
  }, [activeTab, loadSettingData]);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setSaving(true);
      setErrorMsg(null);
      let parsedValue: any;
      try {
        parsedValue = JSON.parse(jsonText);
      } catch {
        throw new Error("Invalid JSON format. Please verify the configuration syntax.");
      }

      const res = await fetch(`/api/v1/settings/${activeTab}`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Origin: window.location.origin,
        },
        body: JSON.stringify({ value: parsedValue }),
      });

      if (!res.ok) {
        const problem = await res.json().catch(() => ({}));
        throw new Error(problem.detail || problem.title || `HTTP ${res.status}`);
      }

      const updated = await res.json();
      setCurrentSetting(updated);
      onToast?.("success", "Settings Saved", `${activeTab} updated to version ${updated.version}.`);
      loadSettingData(activeTab);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Error saving settings.";
      setErrorMsg(msg);
      onToast?.("error", "Save Error", msg);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Settings Navigation Tabs */}
      <div className="border-b border-slate-200">
        <nav className="-mb-px flex space-x-8" aria-label="Settings Sections">
          {[
            { id: "thresholds", label: "Approval Tiers (Thresholds)" },
            { id: "tolerances", label: "Three-Way Match Tolerances" },
            { id: "buyer-policy", label: "Buyer Exception Policy" },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`py-3 px-1 border-b-2 font-medium text-xs transition-colors ${
                activeTab === tab.id
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {loading ? (
        <div className="py-12 text-center text-xs text-slate-500">Loading settings...</div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main Editor */}
          <div className="lg:col-span-2 rounded-lg border border-slate-200 bg-white p-6 shadow-sm space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-slate-900 capitalize">
                  {activeTab.replace("-", " ")} Configuration
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Current Version:{" "}
                  <strong className="font-mono text-slate-800">v{currentSetting?.version || 1}</strong>
                  {currentSetting?.updated_at && ` • Last updated ${formatGSTDate(currentSetting.updated_at)}`}
                </p>
              </div>

              <button
                type="button"
                onClick={handleSave}
                disabled={saving}
                data-testid="save-setting-btn"
                className="inline-flex items-center gap-1.5 rounded-md bg-blue-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-blue-700 disabled:opacity-50"
              >
                <Save className="h-4 w-4" />
                <span>{saving ? "Saving..." : "Save Configuration"}</span>
              </button>
            </div>

            {errorMsg && (
              <div className="rounded border border-rose-200 bg-rose-50 p-2.5 text-xs text-rose-700">
                {errorMsg}
              </div>
            )}

            <div>
              <label htmlFor="settings-json-editor" className="block text-xs font-semibold text-slate-700 mb-1">
                JSON Configuration Value:
              </label>
              <textarea
                id="settings-json-editor"
                value={jsonText}
                onChange={(e) => setJsonText(e.target.value)}
                rows={16}
                data-testid="setting-json-editor"
                className="w-full rounded border border-slate-300 font-mono text-xs p-3 text-slate-900 focus:outline-none focus:ring-1 focus:ring-blue-500 bg-slate-50/50"
              />
            </div>
          </div>

          {/* Version History Sidebar (US-14 / US-25) */}
          <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
            <h3 className="text-sm font-bold text-slate-900 mb-1 flex items-center gap-2">
              <History className="h-4 w-4 text-purple-600" />
              Version History
            </h3>
            <p className="text-xs text-slate-500 mb-4">
              Audit log of past setting versions and modifications.
            </p>

            {history.length === 0 ? (
              <div className="text-xs text-slate-500 py-4 text-center border rounded-md bg-slate-50">
                No past revisions logged yet.
              </div>
            ) : (
              <div className="space-y-3 max-h-96 overflow-y-auto">
                {history.map((h) => (
                  <div key={h.id} className="border rounded-md p-3 text-xs bg-slate-50">
                    <div className="flex items-center justify-between font-bold text-slate-900">
                      <span>Version {h.version ?? "—"}</span>
                      <span className="text-[10px] text-slate-400 font-normal">
                        {formatGSTDate(h.occurred_at)}
                      </span>
                    </div>
                    {h.actor_name && (
                      <p className="text-[11px] text-slate-600 mt-1">
                        Updated by: <strong>{h.actor_name}</strong>
                      </p>
                    )}
                    {h.reason && (
                      <p className="mt-1 rounded bg-white p-1.5 border border-slate-200 text-slate-700 italic text-[11px]">
                        &ldquo;{h.reason}&rdquo;
                      </p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
