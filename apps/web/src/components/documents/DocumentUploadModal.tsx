"use client";

import React, { useState, useRef, useCallback } from "react";
import Link from "next/link";
import {
  UploadCloud,
  FileText,
  AlertTriangle,
  CheckCircle2,
  X,
  Loader2,
  RefreshCw,
  ExternalLink,
} from "lucide-react";
import { validateUploadFile, MAX_UPLOAD_SIZE_BYTES } from "@/lib/documents/validation";
import { useDocumentPolling } from "@/lib/documents/use-document-polling";
import { StatusBadge } from "@/components/ui/StatusBadge";
import type { DocumentType } from "@/lib/documents/types";

export interface DocumentUploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (newDocId: string) => void;
  onToast: (type: "success" | "error" | "info" | "warning", title: string, message?: string) => void;
}

export const DocumentUploadModal: React.FC<DocumentUploadModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
  onToast,
}) => {
  const [file, setFile] = useState<File | null>(null);
  const [docType, setDocType] = useState<string>("");
  const [isDragging, setIsDragging] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<number>(0);

  // Post-upload polling state
  const [uploadedDocId, setUploadedDocId] = useState<string | null>(null);
  const [duplicateDocId, setDuplicateDocId] = useState<string | null>(null);
  const [retrying, setRetrying] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);

  // Polling hook for post-upload extraction progress
  const {
    document: polledDoc,
    status: polledStatus,
    isPolling,
    refetch,
  } = useDocumentPolling({
    documentId: uploadedDocId,
    enabled: Boolean(uploadedDocId),
    onStatusChange: (newStatus) => {
      if (newStatus === "needs_review" || newStatus === "ready") {
        onToast("success", "Extraction Complete", `Document status is ${newStatus}. Ready for review.`);
      }
    },
    onTerminal: (_status, doc) => {
      onSuccess(doc.id);
    },
  });

  const resetForm = useCallback(() => {
    setFile(null);
    setDocType("");
    setValidationError(null);
    setUploading(false);
    setUploadProgress(0);
    setUploadedDocId(null);
    setDuplicateDocId(null);
  }, []);

  const handleClose = () => {
    resetForm();
    onClose();
  };

  const handleFileSelection = async (selectedFile: File) => {
    setValidationError(null);
    setDuplicateDocId(null);

    const validation = await validateUploadFile(selectedFile);
    if (!validation.valid) {
      setValidationError(validation.error || "Invalid file format.");
      setFile(null);
      return;
    }

    setFile(selectedFile);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      await handleFileSelection(e.dataTransfer.files[0]);
    }
  };

  const handleUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;

    try {
      setUploading(true);
      setUploadProgress(20);
      setValidationError(null);
      setDuplicateDocId(null);

      const formData = new FormData();
      formData.append("file", file);
      if (docType) {
        formData.append("doc_type", docType);
      }

      setUploadProgress(60);

      const res = await fetch("/api/v1/documents", {
        method: "POST",
        headers: {
          Origin: window.location.origin,
        },
        body: formData,
      });

      setUploadProgress(100);

      if (res.status === 409) {
        // Exact duplicate
        const problem = await res.json().catch(() => ({}));
        const existingId =
          problem.errors?.[0]?.existing_document_id ||
          (typeof problem.detail === "string" && problem.detail.split(" ").pop()) ||
          null;
        setDuplicateDocId(existingId);
        onToast(
          "warning",
          "Duplicate Document Detected",
          "This file has an identical SHA-256 hash to an already uploaded document."
        );
        setUploading(false);
        return;
      }

      if (!res.ok) {
        const problem = await res.json().catch(() => ({}));
        throw new Error(problem.detail || problem.title || `Upload failed with status ${res.status}`);
      }

      const data = await res.json();
      setUploadedDocId(data.id);
      setUploading(false);
      onToast("info", "Upload Accepted", "Document uploaded and queued for AI extraction.");
    } catch (err: unknown) {
      setUploading(false);
      const msg = err instanceof Error ? err.message : "Failed to upload document.";
      setValidationError(msg);
      onToast("error", "Upload Failed", msg);
    }
  };

  const handleRetryExtract = async () => {
    if (!uploadedDocId) return;
    try {
      setRetrying(true);
      const res = await fetch(`/api/v1/documents/${uploadedDocId}/extract`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Origin: window.location.origin,
        },
      });

      if (!res.ok) {
        const problem = await res.json().catch(() => ({}));
        throw new Error(problem.detail || problem.title || "Failed to retry extraction.");
      }

      onToast("info", "Extraction Re-queued", "Re-running Document Intelligence & LLM extraction.");
      await refetch();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Retry failed.";
      onToast("error", "Retry Error", msg);
    } finally {
      setRetrying(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="upload-modal-title"
    >
      <div className="relative w-full max-w-xl rounded-lg bg-white p-6 shadow-2xl border border-slate-200">
        <button
          type="button"
          onClick={handleClose}
          className="absolute right-4 top-4 text-slate-400 hover:text-slate-600"
          aria-label="Close upload modal"
        >
          <X className="h-5 w-5" aria-hidden="true" />
        </button>

        <div className="flex items-center gap-3 mb-5">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-100 text-blue-700">
            <UploadCloud className="h-5 w-5" aria-hidden="true" />
          </div>
          <div>
            <h2 id="upload-modal-title" className="text-base font-bold text-slate-900">
              Upload Procurement Document (US-01)
            </h2>
            <p className="text-xs text-slate-500">
              Upload PDF or image files (PNG, JPG, TIFF) up to 20 MB.
            </p>
          </div>
        </div>

        {/* 1. DUPLICATE RESULT BANNER */}
        {duplicateDocId && (
          <div className="mb-5 rounded-lg border border-amber-300 bg-amber-50 p-4 text-xs text-amber-900">
            <div className="flex items-start gap-2.5">
              <AlertTriangle className="h-5 w-5 text-amber-700 flex-shrink-0 mt-0.5" />
              <div>
                <h4 className="font-bold text-amber-900">Exact Duplicate Document (US-06)</h4>
                <p className="mt-1 leading-relaxed">
                  This document has already been uploaded previously. An exact SHA-256 match exists in the system.
                </p>
                <div className="mt-3 flex items-center gap-3">
                  <Link
                    href={`/documents/${duplicateDocId}`}
                    onClick={handleClose}
                    className="inline-flex items-center gap-1.5 rounded-md bg-amber-700 px-3.5 py-1.5 font-semibold text-white shadow-sm hover:bg-amber-800"
                  >
                    <span>View Existing Document</span>
                    <ExternalLink className="h-3.5 w-3.5" />
                  </Link>
                  <button
                    type="button"
                    onClick={() => setDuplicateDocId(null)}
                    className="text-xs text-amber-800 underline hover:text-amber-900"
                  >
                    Upload Another File
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 2. LIVE EXTRACTION PROGRESS & STATUS POLLING */}
        {uploadedDocId && !duplicateDocId ? (
          <div className="space-y-4 py-2" data-testid="upload-status-tracker">
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-semibold text-slate-700">Processing Status</span>
                <StatusBadge status={polledStatus || "queued"} />
              </div>

              {/* Status explanation */}
              <div className="flex items-center gap-3 text-xs text-slate-600 mb-4">
                {isPolling && <Loader2 className="h-4 w-4 animate-spin text-blue-600" />}
                <span>
                  {polledStatus === "queued" && "Document queued. Waiting for worker to claim..."}
                  {polledStatus === "processing" && "AI running Document Intelligence OCR and LLM structured extraction..."}
                  {polledStatus === "needs_review" && "Extraction complete! Field confidences calculated. Review required."}
                  {polledStatus === "ready" && "Extraction complete! All validations passed."}
                  {polledStatus === "failed" && "Extraction failed. Click Retry to re-run extraction."}
                </span>
              </div>

              {/* Action buttons once done */}
              {polledStatus === "failed" ? (
                <div className="flex items-center gap-3 pt-2">
                  <button
                    type="button"
                    onClick={handleRetryExtract}
                    disabled={retrying}
                    className="inline-flex items-center gap-1.5 rounded-md bg-rose-600 px-4 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-rose-700"
                  >
                    <RefreshCw className={`h-3.5 w-3.5 ${retrying ? "animate-spin" : ""}`} />
                    <span>{retrying ? "Retrying..." : "Retry Extraction"}</span>
                  </button>
                  <button
                    type="button"
                    onClick={resetForm}
                    className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
                  >
                    Upload Different File
                  </button>
                </div>
              ) : polledStatus === "ready" || polledStatus === "needs_review" ? (
                <div className="flex items-center justify-between gap-3 pt-2 border-t border-slate-200">
                  <span className="text-xs text-slate-500 font-mono">ID: {uploadedDocId}</span>
                  <Link
                    href={`/documents/${uploadedDocId}`}
                    onClick={handleClose}
                    className="inline-flex items-center gap-1.5 rounded-md bg-blue-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-blue-700"
                  >
                    <span>Open Review Screen</span>
                    <ExternalLink className="h-3.5 w-3.5" />
                  </Link>
                </div>
              ) : (
                <div className="flex items-center justify-between gap-3 pt-2 border-t border-slate-200">
                  <span className="text-xs text-slate-500 font-mono">ID: {uploadedDocId}</span>
                  <div className="inline-flex items-center gap-1.5 rounded-md bg-slate-100 px-3.5 py-1.5 text-xs font-medium text-slate-500">
                    <Loader2 className="h-3.5 w-3.5 animate-spin text-blue-600" />
                    <span>Processing extraction...</span>
                  </div>
                </div>
              )}
            </div>
          </div>
        ) : (
          /* 3. UPLOAD FORM */
          !duplicateDocId && (
            <form onSubmit={handleUploadSubmit} className="space-y-4">
              {validationError && (
                <div className="rounded-md border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700 flex items-start gap-2">
                  <AlertTriangle className="h-4 w-4 text-rose-600 flex-shrink-0 mt-0.5" />
                  <span>{validationError}</span>
                </div>
              )}

              {/* Drag & Drop Zone */}
              <div
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
                className={`flex flex-col items-center justify-center rounded-lg border-2 border-dashed p-6 text-center cursor-pointer transition-colors ${
                  isDragging
                    ? "border-blue-500 bg-blue-50"
                    : file
                    ? "border-emerald-400 bg-emerald-50/40"
                    : "border-slate-300 hover:border-slate-400 bg-slate-50/50"
                }`}
                tabIndex={0}
                role="button"
                aria-label="Upload document dropzone"
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    fileInputRef.current?.click();
                  }
                }}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,.png,.jpg,.jpeg,.tiff,.tif"
                  onChange={(e) => {
                    if (e.target.files && e.target.files.length > 0) {
                      handleFileSelection(e.target.files[0]);
                    }
                  }}
                  className="hidden"
                  data-testid="file-upload-input"
                />

                {file ? (
                  <div className="flex items-center gap-3 text-left">
                    <div className="flex h-10 w-10 items-center justify-center rounded-full bg-emerald-100 text-emerald-700">
                      <FileText className="h-5 w-5" />
                    </div>
                    <div>
                      <p className="text-xs font-bold text-slate-900 truncate max-w-xs">{file.name}</p>
                      <p className="text-[11px] text-slate-500">
                        {(file.size / 1024).toFixed(1)} KB • Click or drop another to replace
                      </p>
                    </div>
                  </div>
                ) : (
                  <>
                    <UploadCloud className="h-9 w-9 text-slate-400 mb-2" />
                    <p className="text-xs font-semibold text-slate-700">
                      Click to browse or drag and drop your document here
                    </p>
                    <p className="mt-1 text-[11px] text-slate-500">
                      PDF, PNG, JPG, or TIFF up to 20 MB
                    </p>
                  </>
                )}
              </div>

              {/* Document Type Select (Optional per US-01) */}
              <div>
                <label htmlFor="doc-type-select" className="block text-xs font-semibold text-slate-700 mb-1">
                  Document Type <span className="font-normal text-slate-500">(Optional — AI detects automatically)</span>
                </label>
                <select
                  id="doc-type-select"
                  value={docType}
                  onChange={(e) => setDocType(e.target.value)}
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-xs text-slate-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                >
                  <option value="">Auto-Detect Document Type</option>
                  <option value="quote">Quotation (Supplier Quote)</option>
                  <option value="purchase_order">Purchase Order (PO)</option>
                  <option value="delivery_note">Delivery Note (Goods Receipt)</option>
                  <option value="invoice">Tax Invoice</option>
                  <option value="other">Other Document</option>
                </select>
              </div>

              {/* Progress Bar */}
              {uploading && (
                <div className="space-y-1">
                  <div className="flex justify-between text-xs text-slate-600 font-medium">
                    <span>Uploading...</span>
                    <span>{uploadProgress}%</span>
                  </div>
                  <div className="h-1.5 w-full bg-slate-200 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-blue-600 transition-all duration-300"
                      style={{ width: `${uploadProgress}%` }}
                    />
                  </div>
                </div>
              )}

              {/* Submit / Cancel Buttons */}
              <div className="mt-6 flex justify-end gap-3 pt-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={handleClose}
                  disabled={uploading}
                  className="rounded-md border border-slate-300 bg-white px-3.5 py-2 text-xs font-medium text-slate-700 shadow-sm hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={!file || uploading}
                  data-testid="upload-submit-btn"
                  className="inline-flex items-center gap-1.5 rounded-md bg-blue-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {uploading ? (
                    <>
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      <span>Uploading...</span>
                    </>
                  ) : (
                    <span>Upload & Process</span>
                  )}
                </button>
              </div>
            </form>
          )
        )}
      </div>
    </div>
  );
};
