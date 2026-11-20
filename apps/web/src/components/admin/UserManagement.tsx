"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  Users,
  UserCheck,
  UserX,
  Edit2,
  Shield,
  AlertTriangle,
  CheckCircle,
  Loader2,
} from "lucide-react";
import { formatMoneyAED, formatGSTDate } from "@/lib/formatters";
import type { UserRole } from "@/lib/types";

export interface AdminUser {
  id: string;
  email: string;
  display_name: string;
  roles: string[];
  department_id?: string | null;
  department_name?: string | null;
  approval_limit_aed: number | string;
  active: boolean;
  is_demo: boolean;
  created_at?: string;
  updated_at?: string;
}

interface Department {
  id: string;
  name: string;
}

export interface UserManagementProps {
  currentUserId: string;
  onToast?: (type: "success" | "error" | "info" | "warning", title: string, message?: string) => void;
}

export const UserManagement: React.FC<UserManagementProps> = ({ currentUserId, onToast }) => {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [loading, setLoading] = useState(true);

  // Edit User Modal
  const [editingUser, setEditingUser] = useState<AdminUser | null>(null);
  const [selectedRoles, setSelectedRoles] = useState<string[]>([]);
  const [limitAed, setLimitAed] = useState<string>("0.00");
  const [departmentId, setDepartmentId] = useState<string>("");
  const [isActive, setIsActive] = useState(true);
  const [reasonInput, setReasonInput] = useState("");
  const [saving, setSaving] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const [usersRes, deptsRes] = await Promise.all([
        fetch("/api/v1/admin/users"),
        fetch("/api/v1/admin/departments"),
      ]);
      if (usersRes.ok) {
        setUsers(await usersRes.json());
      }
      if (deptsRes.ok) {
        setDepartments(await deptsRes.json());
      }
    } catch {
      onToast?.("error", "Error", "Failed to load user administration data.");
    } finally {
      setLoading(false);
    }
  }, [onToast]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const openEditModal = (u: AdminUser) => {
    setEditingUser(u);
    setSelectedRoles([...u.roles]);
    setLimitAed(String(u.approval_limit_aed || "0.00"));
    setDepartmentId(u.department_id || "");
    setIsActive(u.active);
    setReasonInput("");
    setModalError(null);
  };

  const isSelf = editingUser?.id === currentUserId;
  const isTargetAdmin = editingUser?.roles.includes("admin") || selectedRoles.includes("admin");
  const grantingBusinessRoles =
    selectedRoles.some((r) => ["requester", "buyer", "manager"].includes(r)) &&
    (isSelf || isTargetAdmin);

  const handleToggleRole = (role: string) => {
    if (selectedRoles.includes(role)) {
      setSelectedRoles(selectedRoles.filter((r) => r !== role));
    } else {
      setSelectedRoles([...selectedRoles, role]);
    }
  };

  const handleSaveUser = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingUser) return;

    if (grantingBusinessRoles && reasonInput.trim().length < 10) {
      setModalError(
        "Admin cannot grant business roles silently: an audit reason of at least 10 characters is required."
      );
      return;
    }

    try {
      setSaving(true);
      setModalError(null);
      const res = await fetch(`/api/v1/admin/users/${editingUser.id}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Origin: window.location.origin,
        },
        body: JSON.stringify({
          roles: selectedRoles,
          approval_limit_aed: parseFloat(limitAed) || 0,
          department_id: departmentId || null,
          active: isActive,
          reason: reasonInput.trim() || undefined,
        }),
      });

      if (!res.ok) {
        const problem = await res.json().catch(() => ({}));
        throw new Error(problem.detail || problem.title || `HTTP ${res.status}`);
      }

      onToast?.("success", "User Updated", `User ${editingUser.email} has been updated and audited.`);
      setEditingUser(null);
      loadData();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to update user.";
      setModalError(msg);
      onToast?.("error", "Save Error", msg);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
          <Users className="h-5 w-5 text-blue-600" />
          Users & Delegated Roles (US-25)
        </h2>
        <p className="mt-1 text-xs text-slate-500">
          Manage system accounts, assign RBAC roles, define financial delegation limits, and manage status. All modifications are logged in the tamper-evident audit trail.
        </p>
      </div>

      <div className="rounded-lg border border-slate-200 bg-white shadow-sm overflow-hidden">
        {loading ? (
          <div className="py-12 text-center text-xs text-slate-500">Loading user records...</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-xs">
              <thead className="bg-slate-50 text-[11px] font-semibold uppercase text-slate-500">
                <tr>
                  <th className="px-4 py-3 text-left">User</th>
                  <th className="px-4 py-3 text-left">Department</th>
                  <th className="px-4 py-3 text-left">Roles</th>
                  <th className="px-4 py-3 text-right">Approval Limit</th>
                  <th className="px-4 py-3 text-center">Status</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {users.map((u) => (
                  <tr key={u.id} className="hover:bg-slate-50/50">
                    <td className="px-4 py-3">
                      <div className="font-semibold text-slate-900">{u.display_name}</div>
                      <div className="text-[11px] text-slate-500 font-mono">{u.email}</div>
                    </td>
                    <td className="px-4 py-3 text-slate-700">
                      {u.department_name || "—"}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-1">
                        {u.roles.map((r) => (
                          <span
                            key={r}
                            className={`rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase ${
                              r === "admin"
                                ? "bg-amber-100 text-amber-800"
                                : r === "manager"
                                ? "bg-emerald-100 text-emerald-800"
                                : r === "buyer"
                                ? "bg-purple-100 text-purple-800"
                                : "bg-blue-100 text-blue-800"
                            }`}
                          >
                            {r}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-slate-800">
                      {formatMoneyAED(u.approval_limit_aed)}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span
                        className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                          u.active
                            ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                            : "bg-slate-100 text-slate-500"
                        }`}
                      >
                        {u.active ? "Active" : "Inactive"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        type="button"
                        onClick={() => openEditModal(u)}
                        data-testid={`edit-user-btn-${u.email}`}
                        className="inline-flex items-center gap-1 rounded border border-slate-300 px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50"
                      >
                        <Edit2 className="h-3.5 w-3.5" />
                        <span>Edit</span>
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Edit User Modal */}
      {editingUser && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
        >
          <div className="w-full max-w-lg rounded-lg bg-white p-6 shadow-xl border border-slate-200 text-xs">
            <h3 className="text-base font-bold text-slate-900 mb-1">
              Edit User: {editingUser.display_name}
            </h3>
            <p className="text-slate-500 font-mono mb-4">{editingUser.email}</p>

            {modalError && (
              <div className="mb-4 rounded border border-rose-200 bg-rose-50 p-2.5 text-rose-700">
                {modalError}
              </div>
            )}

            <form onSubmit={handleSaveUser} className="space-y-4">
              {/* Roles Multi-Select */}
              <div>
                <label className="block font-semibold text-slate-700 mb-2">Assigned Roles:</label>
                <div className="grid grid-cols-2 gap-2">
                  {["requester", "buyer", "manager", "admin"].map((role) => (
                    <label
                      key={role}
                      className={`flex items-center gap-2 p-2.5 rounded border cursor-pointer ${
                        selectedRoles.includes(role)
                          ? "bg-blue-50 border-blue-300 text-blue-900"
                          : "hover:bg-slate-50 border-slate-200 text-slate-700"
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={selectedRoles.includes(role)}
                        onChange={() => handleToggleRole(role)}
                        className="rounded text-blue-600 focus:ring-blue-500"
                      />
                      <span className="capitalize font-medium">{role}</span>
                    </label>
                  ))}
                </div>
              </div>

              {/* Department */}
              <div>
                <label htmlFor="edit-user-dept" className="block font-semibold text-slate-700 mb-1">
                  Department:
                </label>
                <select
                  id="edit-user-dept"
                  value={departmentId}
                  onChange={(e) => setDepartmentId(e.target.value)}
                  className="w-full rounded border border-slate-300 p-2 text-slate-900"
                >
                  <option value="">No Department Assigned</option>
                  {departments.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name}
                    </option>
                  ))}
                </select>
              </div>

              {/* Approval Limit */}
              <div>
                <label htmlFor="edit-user-limit" className="block font-semibold text-slate-700 mb-1">
                  Manager Delegated Approval Limit (AED):
                </label>
                <input
                  id="edit-user-limit"
                  type="number"
                  min="0"
                  step="0.01"
                  value={limitAed}
                  onChange={(e) => setLimitAed(e.target.value)}
                  className="w-full rounded border border-slate-300 p-2 text-slate-900"
                />
              </div>

              {/* Active Toggle */}
              <div>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={isActive}
                    onChange={(e) => setIsActive(e.target.checked)}
                    className="rounded text-blue-600"
                  />
                  <span className="font-semibold text-slate-700">Account Active</span>
                </label>
              </div>

              {/* Reason Input (enforced when admin grants business roles to admin or self) */}
              {grantingBusinessRoles && (
                <div className="rounded-md border border-amber-200 bg-amber-50/70 p-3">
                  <label htmlFor="admin-audit-reason-input" className="block font-semibold text-amber-900 mb-1">
                    Audit Justification Reason * (Strict Security Governance)
                  </label>
                  <p className="text-[11px] text-amber-700 mb-2">
                    Admin cannot grant itself or administrators business roles silently. Enter a recorded reason of at least 10 characters.
                  </p>
                  <textarea
                    id="admin-audit-reason-input"
                    value={reasonInput}
                    onChange={(e) => setReasonInput(e.target.value)}
                    rows={2}
                    required
                    placeholder="Enter audit reason for granting business roles..."
                    data-testid="admin-audit-reason-input"
                    className="w-full rounded border border-amber-300 bg-white p-2 text-slate-900"
                  />
                  <span className="text-[10px] text-amber-800">
                    {reasonInput.trim().length} / 10 characters min
                  </span>
                </div>
              )}

              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setEditingUser(null)}
                  className="rounded-md border border-slate-300 px-3.5 py-1.5 text-slate-700 hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  data-testid="save-user-submit-btn"
                  className="rounded-md bg-blue-600 px-4 py-1.5 font-semibold text-white shadow-sm hover:bg-blue-700 disabled:opacity-50"
                >
                  {saving ? "Saving..." : "Save User Changes"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
