"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Plus, Trash2, ShoppingCart, Loader2 } from "lucide-react";
import { fetchProducts, type Product } from "@/lib/constants/vendors";
import { formatMoneyAED } from "@/lib/formatters";
import type { PRCreatePayload, PRCreateLinePayload } from "@/lib/flow/types";

interface DepartmentOption {
  id: string;
  name: string;
}

export interface PRFormProps {
  userDepartmentId?: string | null;
  onToast?: (type: "success" | "error" | "info" | "warning", title: string, message?: string) => void;
}

export const PRForm: React.FC<PRFormProps> = ({ userDepartmentId, onToast }) => {
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [departmentId, setDepartmentId] = useState<string>(userDepartmentId || "");
  const [departments, setDepartments] = useState<DepartmentOption[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [lines, setLines] = useState<PRCreateLinePayload[]>([
    {
      product_id: null,
      description: "",
      qty: 1,
      uom: "unit",
      est_unit_price: 0,
    },
  ]);

  useEffect(() => {
    // Load products catalogue
    fetchProducts()
      .then((data) => setProducts(data))
      .catch(() => {});

    // Load departments
    fetch("/api/v1/departments")
      .then((res) => (res.ok ? res.json() : []))
      .then((data: DepartmentOption[]) => {
        setDepartments(data);
        if (!departmentId && data.length > 0) {
          setDepartmentId(data[0].id);
        }
      })
      .catch(() => {});
  }, [departmentId]);

  const handleProductSelect = (index: number, productId: string) => {
    const selected = products.find((p) => p.id === productId);
    const updated = [...lines];
    if (selected) {
      updated[index] = {
        ...updated[index],
        product_id: selected.id,
        description: selected.name,
        uom: selected.uom || "unit",
      };
    } else {
      updated[index] = {
        ...updated[index],
        product_id: null,
      };
    }
    setLines(updated);
  };

  const handleLineChange = (
    index: number,
    field: keyof PRCreateLinePayload,
    value: string | number
  ) => {
    const updated = [...lines];
    updated[index] = {
      ...updated[index],
      [field]: value,
    };
    setLines(updated);
  };

  const addLine = () => {
    setLines([
      ...lines,
      {
        product_id: null,
        description: "",
        qty: 1,
        uom: "unit",
        est_unit_price: 0,
      },
    ]);
  };

  const removeLine = (index: number) => {
    if (lines.length <= 1) return;
    setLines(lines.filter((_, idx) => idx !== index));
  };

  const totalAmount = lines.reduce((acc, line) => {
    const q = Number(line.qty) || 0;
    const p = Number(line.est_unit_price) || 0;
    return acc + q * p;
  }, 0);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) {
      setError("Request title is required.");
      return;
    }
    if (lines.some((l) => !l.description.trim() || Number(l.qty) <= 0)) {
      setError("All lines must have a description and quantity greater than zero.");
      return;
    }

    try {
      setSubmitting(true);
      setError(null);
      const payload: PRCreatePayload = {
        title: title.trim(),
        department_id: departmentId || undefined,
        lines: lines.map((l) => ({
          product_id: l.product_id || undefined,
          description: l.description.trim(),
          qty: Number(l.qty),
          uom: l.uom || "unit",
          est_unit_price: Number(l.est_unit_price) || 0,
        })),
      };

      const res = await fetch("/api/v1/purchase-requests", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Origin: window.location.origin,
        },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const problem = await res.json().catch(() => ({}));
        throw new Error(problem.detail || problem.title || `HTTP ${res.status}`);
      }

      const created = await res.json();
      onToast?.("success", "Purchase Request Created", `Request ${created.number} created.`);
      router.push(`/requests/${created.id}`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to create request.";
      setError(msg);
      onToast?.("error", "Error", msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6" data-testid="pr-form">
      {error && (
        <div className="rounded-md border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700">
          {error}
        </div>
      )}

      <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-base font-semibold text-slate-900 mb-4 flex items-center gap-2">
          <ShoppingCart className="h-5 w-5 text-blue-600" />
          Request Overview
        </h2>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="pr-title" className="block text-xs font-medium text-slate-700 mb-1">
              Title / Purpose *
            </label>
            <input
              id="pr-title"
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. IT Equipment for New Engineering Cohort"
              required
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>

          <div>
            <label htmlFor="pr-dept" className="block text-xs font-medium text-slate-700 mb-1">
              Department
            </label>
            <select
              id="pr-dept"
              value={departmentId}
              onChange={(e) => setDepartmentId(e.target.value)}
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value="">Select department...</option>
              {departments.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Line Items */}
      <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-slate-900">Requested Items</h2>
          <button
            type="button"
            onClick={addLine}
            className="inline-flex items-center gap-1.5 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 shadow-sm hover:bg-slate-50"
          >
            <Plus className="h-4 w-4" />
            Add Item
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200">
            <thead className="bg-slate-50 text-[11px] font-semibold uppercase text-slate-500">
              <tr>
                <th className="px-3 py-2 text-left">Catalogue Product</th>
                <th className="px-3 py-2 text-left">Description *</th>
                <th className="px-3 py-2 text-right w-24">Qty *</th>
                <th className="px-3 py-2 text-left w-20">UOM</th>
                <th className="px-3 py-2 text-right w-36">Est. Unit Price (AED)</th>
                <th className="px-3 py-2 text-right w-36">Line Total</th>
                <th className="px-3 py-2 text-center w-12"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-xs">
              {lines.map((line, idx) => {
                const lineTotal = (Number(line.qty) || 0) * (Number(line.est_unit_price) || 0);
                return (
                  <tr key={idx} className="hover:bg-slate-50/50">
                    <td className="px-3 py-2">
                      <select
                        aria-label={`Product for line ${idx + 1}`}
                        value={line.product_id || ""}
                        onChange={(e) => handleProductSelect(idx, e.target.value)}
                        className="w-full rounded border border-slate-300 px-2 py-1 text-xs text-slate-900"
                      >
                        <option value="">Custom / Non-catalogue</option>
                        {products.map((p) => (
                          <option key={p.id} value={p.id}>
                            [{p.code}] {p.name}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="px-3 py-2">
                      <input
                        aria-label={`Description for line ${idx + 1}`}
                        type="text"
                        value={line.description}
                        onChange={(e) => handleLineChange(idx, "description", e.target.value)}
                        placeholder="Item description"
                        required
                        className="w-full rounded border border-slate-300 px-2 py-1 text-xs text-slate-900"
                      />
                    </td>
                    <td className="px-3 py-2">
                      <input
                        aria-label={`Quantity for line ${idx + 1}`}
                        type="number"
                        min="1"
                        step="any"
                        value={line.qty}
                        onChange={(e) => handleLineChange(idx, "qty", parseFloat(e.target.value) || 0)}
                        required
                        className="w-full rounded border border-slate-300 px-2 py-1 text-right text-xs text-slate-900"
                      />
                    </td>
                    <td className="px-3 py-2">
                      <input
                        aria-label={`UOM for line ${idx + 1}`}
                        type="text"
                        value={line.uom}
                        onChange={(e) => handleLineChange(idx, "uom", e.target.value)}
                        className="w-full rounded border border-slate-300 px-2 py-1 text-xs text-slate-900"
                      />
                    </td>
                    <td className="px-3 py-2">
                      <input
                        aria-label={`Est Unit Price for line ${idx + 1}`}
                        type="number"
                        min="0"
                        step="0.01"
                        value={line.est_unit_price}
                        onChange={(e) =>
                          handleLineChange(idx, "est_unit_price", parseFloat(e.target.value) || 0)
                        }
                        className="w-full rounded border border-slate-300 px-2 py-1 text-right text-xs text-slate-900"
                      />
                    </td>
                    <td className="px-3 py-2 text-right font-medium text-slate-900" data-testid={`line-total-${idx}`}>
                      {formatMoneyAED(lineTotal)}
                    </td>
                    <td className="px-3 py-2 text-center">
                      <button
                        type="button"
                        aria-label={`Remove line ${idx + 1}`}
                        onClick={() => removeLine(idx)}
                        disabled={lines.length <= 1}
                        className="text-slate-400 hover:text-rose-600 disabled:opacity-30"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
            <tfoot>
              <tr className="border-t-2 border-slate-200 bg-slate-50 font-bold text-slate-900">
                <td colSpan={5} className="px-3 py-3 text-right">
                  Total Estimated Amount:
                </td>
                <td className="px-3 py-3 text-right text-sm text-blue-700" data-testid="pr-total-amount">
                  {formatMoneyAED(totalAmount)}
                </td>
                <td></td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>

      <div className="flex justify-end gap-3">
        <button
          type="button"
          onClick={() => router.back()}
          className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-50"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={submitting}
          data-testid="create-pr-submit-btn"
          className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-5 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 disabled:opacity-50"
        >
          {submitting ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              <span>Saving...</span>
            </>
          ) : (
            <span>Create Purchase Request</span>
          )}
        </button>
      </div>
    </form>
  );
};
