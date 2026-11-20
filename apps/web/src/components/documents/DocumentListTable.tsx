"use client";

import React, { useState, useMemo, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  FileText,
  Upload,
  Search,
  Filter,
  RefreshCw,
  ShieldAlert,
  Copy,
  ExternalLink,
  Eye,
  Edit3,
} from "lucide-react";
import { DataTable, type Column } from "@/components/ui/DataTable";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { DocumentUploadModal } from "./DocumentUploadModal";
import { fetchVendors, type Vendor } from "@/lib/constants/vendors";
import { formatDate } from "@/lib/formatters";
import type { DocumentSummary, DocumentType, DocumentStatus } from "@/lib/documents/types";

export interface DocumentListTableProps {
  userRoles: string[];
  onToast: (type: "success" | "error" | "info" | "warning", title: string, message?: string) => void;
}

export const DocumentListTable: React.FC<DocumentListTableProps> = ({
  userRoles,
  onToast,
}) => {
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [vendorsList, setVendorsList] = useState<Vendor[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [uploadModalOpen, setUploadModalOpen] = useState<boolean>(false);

  useEffect(() => {
    fetchVendors()
      .then((data) => setVendorsList(data))
      .catch(() => {});
  }, []);

  // Filters
  const [typeFilter, setTypeFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [vendorFilter, setVendorFilter] = useState<string>("all");
  const [suspiciousOnly, setSuspiciousOnly] = useState<boolean>(false);
  const [duplicateOnly, setDuplicateOnly] = useState<boolean>(false);
  const [searchQuery, setSearchQuery] = useState<string>("");

  const isBuyer = userRoles.includes("buyer");
  const isRequester = userRoles.includes("requester");
  const canUpload = isBuyer || isRequester;

  const fetchDocuments = useCallback(async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams();
      if (typeFilter !== "all") params.append("doc_type", typeFilter);
      if (statusFilter !== "all") params.append("status", statusFilter);
      if (vendorFilter !== "all") params.append("vendor_id", vendorFilter);

      const res = await fetch(`/api/v1/documents?${params.toString()}`, {
        headers: { Accept: "application/json" },
      });

      if (!res.ok) {
        throw new Error(`Failed to load documents (HTTP ${res.status})`);
      }

      const data: DocumentSummary[] = await res.json();
      setDocuments(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Error fetching documents";
      onToast("error", "Failed to Load Documents", msg);
    } finally {
      setLoading(false);
    }
  }, [typeFilter, statusFilter, vendorFilter, onToast]);

  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  // Client-side filtering for search & boolean flags
  const filteredDocuments = useMemo(() => {
    return documents.filter((doc) => {
      if (suspiciousOnly && !doc.suspicious) return false;
      if (duplicateOnly && !doc.duplicate_of) return false;
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim();
        const matchesId = doc.id.toLowerCase().includes(q);
        const matchesType = doc.doc_type.toLowerCase().includes(q);
        if (!matchesId && !matchesType) return false;
      }
      return true;
    });
  }, [documents, suspiciousOnly, duplicateOnly, searchQuery]);

  // Format document type for display
  const formatDocType = (type: string) => {
    const labels: Record<string, string> = {
      quote: "Quotation",
      purchase_order: "Purchase Order",
      delivery_note: "Delivery Note",
      invoice: "Invoice",
      other: "Other",
    };
    return labels[type] || type.replace(/_/g, " ").toUpperCase();
  };

  const columns: Column<DocumentSummary>[] = [
    {
      key: "id",
      header: "Document ID",
      sortable: true,
      render: (row) => (
        <div className="flex items-center gap-2">
          <FileText className="h-4 w-4 text-slate-400 flex-shrink-0" />
          <Link
            href={`/documents/${row.id}`}
            className="font-mono text-xs font-semibold text-blue-600 hover:text-blue-800 hover:underline truncate max-w-[140px]"
            title={row.id}
          >
            {row.id}
          </Link>
        </div>
      ),
    },
    {
      key: "doc_type",
      header: "Type",
      sortable: true,
      render: (row) => (
        <span className="inline-flex items-center rounded-md bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700">
          {formatDocType(row.doc_type)}
        </span>
      ),
    },
    {
      key: "status",
      header: "Status",
      sortable: true,
      render: (row) => <StatusBadge status={row.status} size="sm" />,
    },
    {
      key: "pages",
      header: "Pages",
      sortable: true,
      align: "center",
      render: (row) => <span className="text-xs text-slate-600 font-mono">{row.pages}</span>,
    },
    {
      key: "size_bytes",
      header: "Size",
      sortable: true,
      align: "right",
      render: (row) => (
        <span className="text-xs text-slate-500 font-mono">
          {(row.size_bytes / 1024).toFixed(0)} KB
        </span>
      ),
    },
    {
      key: "flags",
      header: "Security / Flags",
      render: (row) => (
        <div className="flex flex-wrap items-center gap-1.5">
          {row.suspicious && (
            <span
              className="inline-flex items-center gap-1 rounded bg-rose-100 px-2 py-0.5 text-[10px] font-bold text-rose-800 border border-rose-200"
              title="Flagged for suspicious instructions (Prompt Injection Defence)"
            >
              <ShieldAlert className="h-3 w-3 text-rose-600" />
              <span>Suspicious</span>
            </span>
          )}
          {row.duplicate_of && (
            <span
              className="inline-flex items-center gap-1 rounded bg-orange-100 px-2 py-0.5 text-[10px] font-medium text-orange-800 border border-orange-200"
              title="Possible duplicate document"
            >
              <Copy className="h-3 w-3 text-orange-600" />
              <span>Duplicate</span>
            </span>
          )}
          {!row.suspicious && !row.duplicate_of && (
            <span className="text-xs text-slate-400">—</span>
          )}
        </div>
      ),
    },
    {
      key: "created_at",
      header: "Uploaded",
      sortable: true,
      render: (row) => (
        <span className="text-xs text-slate-500 whitespace-nowrap">
          {formatDate(row.created_at)}
        </span>
      ),
    },
    {
      key: "actions",
      header: "Action",
      align: "right",
      render: (row) => (
        <Link
          href={`/documents/${row.id}`}
          className={`inline-flex items-center gap-1 rounded px-2.5 py-1 text-xs font-semibold shadow-sm transition-colors ${
            isBuyer
              ? "bg-blue-600 text-white hover:bg-blue-700"
              : "bg-slate-100 text-slate-700 hover:bg-slate-200"
          }`}
          data-testid={`action-btn-${row.id}`}
        >
          {isBuyer ? (
            <>
              <Edit3 className="h-3 w-3" />
              <span>Review</span>
            </>
          ) : (
            <>
              <Eye className="h-3 w-3" />
              <span>View</span>
            </>
          )}
        </Link>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      {/* Top Header & Actions Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            Procurement Documents
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Upload, verify, and review supplier quotes, purchase orders, delivery notes, and tax invoices.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={fetchDocuments}
            disabled={loading}
            aria-label="Refresh document list"
            className="inline-flex items-center gap-1.5 rounded-md border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-700 shadow-sm hover:bg-slate-50"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
            <span>Refresh</span>
          </button>

          {canUpload && (
            <button
              type="button"
              onClick={() => setUploadModalOpen(true)}
              data-testid="open-upload-modal-btn"
              className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-blue-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-600"
            >
              <Upload className="h-4 w-4" />
              <span>Upload Document</span>
            </button>
          )}
        </div>
      </div>

      {/* Filter Toolbar */}
      <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm space-y-3">
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
          {/* Document Type */}
          <div>
            <label htmlFor="filter-type" className="block text-[11px] font-semibold text-slate-600 mb-1">
              Document Type
            </label>
            <select
              id="filter-type"
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="w-full rounded-md border border-slate-300 px-2.5 py-1.5 text-xs text-slate-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value="all">All Types</option>
              <option value="quote">Quotation</option>
              <option value="purchase_order">Purchase Order</option>
              <option value="delivery_note">Delivery Note</option>
              <option value="invoice">Invoice</option>
              <option value="other">Other</option>
            </select>
          </div>

          {/* Status */}
          <div>
            <label htmlFor="filter-status" className="block text-[11px] font-semibold text-slate-600 mb-1">
              Processing Status
            </label>
            <select
              id="filter-status"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="w-full rounded-md border border-slate-300 px-2.5 py-1.5 text-xs text-slate-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value="all">All Statuses</option>
              <option value="queued">Queued</option>
              <option value="processing">Processing</option>
              <option value="needs_review">Needs Review</option>
              <option value="ready">Ready</option>
              <option value="confirmed">Confirmed</option>
              <option value="failed">Failed</option>
            </select>
          </div>

          {/* Vendor */}
          <div>
            <label htmlFor="filter-vendor" className="block text-[11px] font-semibold text-slate-600 mb-1">
              Vendor
            </label>
            <select
              id="filter-vendor"
              value={vendorFilter}
              onChange={(e) => setVendorFilter(e.target.value)}
              className="w-full rounded-md border border-slate-300 px-2.5 py-1.5 text-xs text-slate-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value="all">All Vendors</option>
              {vendorsList.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.name}
                </option>
              ))}
            </select>
          </div>

          {/* Search Query */}
          <div>
            <label htmlFor="filter-search" className="block text-[11px] font-semibold text-slate-600 mb-1">
              Search
            </label>
            <div className="relative">
              <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-slate-400" />
              <input
                id="filter-search"
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search by ID or type..."
                className="w-full rounded-md border border-slate-300 pl-8 pr-3 py-1.5 text-xs text-slate-900 placeholder:text-slate-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>
          </div>
        </div>

        {/* Toggles for Flags */}
        <div className="flex flex-wrap items-center gap-6 pt-2 border-t border-slate-100 text-xs">
          <label className="inline-flex items-center gap-2 cursor-pointer text-slate-700">
            <input
              type="checkbox"
              checked={suspiciousOnly}
              onChange={(e) => setSuspiciousOnly(e.target.checked)}
              className="rounded border-slate-300 text-rose-600 focus:ring-rose-500"
            />
            <span className="font-medium text-rose-800">Suspicious Content Only (Prompt Injection)</span>
          </label>

          <label className="inline-flex items-center gap-2 cursor-pointer text-slate-700">
            <input
              type="checkbox"
              checked={duplicateOnly}
              onChange={(e) => setDuplicateOnly(e.target.checked)}
              className="rounded border-slate-300 text-orange-600 focus:ring-orange-500"
            />
            <span className="font-medium text-orange-800">Duplicate Warnings Only</span>
          </label>
        </div>
      </div>

      {/* Documents Data Table */}
      <DataTable
        data={filteredDocuments as unknown as Record<string, unknown>[]}
        columns={columns as unknown as Column<Record<string, unknown>>[]}
        pageSize={15}
        emptyTitle="No documents match your filters"
        emptyDescription="Try clearing or adjusting filters, or upload a new procurement document."
        rowKey={(row) => (row as unknown as DocumentSummary).id}
        ariaLabel="Documents table"
      />

      {/* Upload Document Modal */}
      {uploadModalOpen && (
        <DocumentUploadModal
          isOpen={uploadModalOpen}
          onClose={() => setUploadModalOpen(false)}
          onSuccess={() => {
            fetchDocuments();
          }}
          onToast={onToast}
        />
      )}
    </div>
  );
};
