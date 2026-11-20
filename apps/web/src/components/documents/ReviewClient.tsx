"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  FileText,
  Calendar,
  Layers,
  Sparkles,
  Columns,
  Maximize2,
  FileCheck,
} from "lucide-react";
import { DocumentViewer } from "./DocumentViewer";
import { ExtractionReview } from "./ExtractionReview";
import { SuspiciousBanner } from "./SuspiciousBanner";
import { DuplicateBanner } from "./DuplicateBanner";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { useToast } from "@/components/ui/Toast";
import { formatFieldName } from "@/lib/documents/open-items";
import type {
  DocumentResponse,
  ExtractionResponse,
  HighlightTarget,
} from "@/lib/documents/types";

export interface ReviewClientProps {
  initialDocument: DocumentResponse;
  initialExtraction: ExtractionResponse | null;
  userRoles: string[];
  initialPage?: number;
  initialHighlightId?: string;
}

export const ReviewClient: React.FC<ReviewClientProps> = ({
  initialDocument,
  initialExtraction,
  userRoles,
  initialPage = 1,
  initialHighlightId,
}) => {
  const toast = useToast();

  const [document, setDocument] = useState<DocumentResponse>(initialDocument);
  const [extraction, setExtraction] = useState<ExtractionResponse | null>(initialExtraction);
  const [activePage, setActivePage] = useState<number>(initialPage);
  const [selectedHighlight, setSelectedHighlight] = useState<HighlightTarget | null>(null);

  // Tablet responsive view tab
  const [activeViewTab, setActiveViewTab] = useState<"both" | "document" | "review">("both");

  // Re-fetch document and extraction state in-place without page reload
  const handleRefresh = useCallback(async () => {
    try {
      const [docRes, extRes] = await Promise.all([
        fetch(`/api/v1/documents/${document.id}`, { headers: { Accept: "application/json" } }),
        fetch(`/api/v1/documents/${document.id}/extraction`, { headers: { Accept: "application/json" } }),
      ]);

      if (docRes.ok) {
        const docData = await docRes.json();
        setDocument(docData);
      }

      if (extRes.ok) {
        const extData = await extRes.json();
        setExtraction(extData);
      }
    } catch (err: unknown) {
      console.error("Failed to refresh document state:", err);
    }
  }, [document.id]);

  // Auto-poll if document is queued/processing or extraction is missing
  useEffect(() => {
    if (extraction && !["queued", "processing"].includes(document.status)) return;
    const interval = setInterval(() => {
      handleRefresh();
    }, 2000);
    return () => clearInterval(interval);
  }, [extraction, document.status, handleRefresh]);

  // Deep-link citation highlight effect (US-20)
  useEffect(() => {
    if (!initialHighlightId || !extraction) return;

    // Check header fields first
    const matchedField = extraction.fields?.find(
      (f) =>
        f.id.toLowerCase() === initialHighlightId.toLowerCase() ||
        f.name.toLowerCase() === initialHighlightId.toLowerCase()
    );

    if (matchedField) {
      const targetPage = matchedField.page || 1;
      setActivePage(targetPage);
      setSelectedHighlight({
        id: matchedField.id,
        name: matchedField.name,
        page: targetPage,
        bbox: matchedField.bbox,
        label: formatFieldName(matchedField.name),
      });
      return;
    }

    // Check line items
    const matchedLine = extraction.lines?.find(
      (l) =>
        l.id.toLowerCase() === initialHighlightId.toLowerCase() ||
        `line_${l.line_no}` === initialHighlightId.toLowerCase()
    );

    if (matchedLine) {
      const targetPage = matchedLine.page || 1;
      setActivePage(targetPage);
      setSelectedHighlight({
        id: matchedLine.id,
        page: targetPage,
        bbox: matchedLine.bbox,
        label: `Line #${matchedLine.line_no}: ${matchedLine.description || "Item"}`,
      });
    }
  }, [initialHighlightId, extraction]);

  const handleSelectHighlight = (target: HighlightTarget | null) => {
    setSelectedHighlight(target);
    if (target?.page) {
      setActivePage(target.page);
    }
  };

  const isBuyer = userRoles.includes("buyer");

  return (
    <div className="space-y-6">
      {/* Top Back & Header Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 pb-4">
        <div className="flex items-center gap-3">
          <Link
            href="/documents"
            className="flex h-9 w-9 items-center justify-center rounded-lg border border-slate-300 bg-white text-slate-600 shadow-sm hover:bg-slate-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-600"
            aria-label="Back to documents list"
          >
            <ArrowLeft className="h-4 w-4" />
          </Link>

          <div>
            <div className="flex items-center gap-2.5">
              <h1 className="text-xl font-bold tracking-tight text-slate-900">
                Document Review: {document.doc_type.toUpperCase().replace(/_/g, " ")}
              </h1>
              <StatusBadge status={document.status} />
            </div>
            <p className="text-xs text-slate-500 font-mono mt-0.5">
              ID: {document.id} • {document.pages} page(s) • {(document.size_bytes / 1024).toFixed(0)} KB
            </p>
          </div>
        </div>

        {/* View mode toggle for smaller/tablet viewports */}
        <div className="flex lg:hidden items-center rounded-lg border border-slate-200 bg-white p-1 text-xs">
          <button
            type="button"
            onClick={() => setActiveViewTab("both")}
            className={`rounded px-3 py-1 font-medium transition-colors ${
              activeViewTab === "both" ? "bg-blue-600 text-white" : "text-slate-600 hover:text-slate-900"
            }`}
          >
            Split View
          </button>
          <button
            type="button"
            onClick={() => setActiveViewTab("document")}
            className={`rounded px-3 py-1 font-medium transition-colors ${
              activeViewTab === "document" ? "bg-blue-600 text-white" : "text-slate-600 hover:text-slate-900"
            }`}
          >
            Document
          </button>
          <button
            type="button"
            onClick={() => setActiveViewTab("review")}
            className={`rounded px-3 py-1 font-medium transition-colors ${
              activeViewTab === "review" ? "bg-blue-600 text-white" : "text-slate-600 hover:text-slate-900"
            }`}
          >
            Extracted Data
          </button>
        </div>
      </div>

      {/* Security & Warning Banners */}
      <SuspiciousBanner
        doc={document}
        isBuyer={isBuyer}
        onAcknowledged={handleRefresh}
        onToast={(type, title, msg) => toast[type](title, msg)}
      />

      <DuplicateBanner
        doc={document}
        isBuyer={isBuyer}
        onCleared={handleRefresh}
        onToast={(type, title, msg) => toast[type](title, msg)}
      />

      {/* Review Split Screen Grid (Left: Document Viewer, Right: Extracted Fields) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column: PDF / Image Viewer (6 cols on lg) */}
        <div
          className={`lg:col-span-6 lg:sticky lg:top-24 h-[calc(100vh-160px)] min-h-[550px] ${
            activeViewTab === "review" ? "hidden lg:block" : "block"
          }`}
        >
          <DocumentViewer
            documentId={document.id}
            mimeType={document.mime}
            activePage={activePage}
            highlightBox={selectedHighlight?.bbox}
            highlightLabel={selectedHighlight?.label}
            onPageChange={(page) => setActivePage(page)}
            className="h-full"
          />
        </div>

        {/* Right Column: Extracted Header Fields and Line Items (6 cols on lg) */}
        <div
          className={`lg:col-span-6 overflow-y-auto ${
            activeViewTab === "document" ? "hidden lg:block" : "block"
          }`}
        >
          {extraction ? (
            <ExtractionReview
              document={document}
              extraction={extraction}
              userRoles={userRoles}
              selectedHighlight={selectedHighlight}
              onSelectHighlight={handleSelectHighlight}
              onRefresh={handleRefresh}
              onToast={(type, title, msg) => toast[type](title, msg)}
            />
          ) : (
            <div className="rounded-lg border border-slate-200 bg-white p-8 text-center text-slate-500">
              <FileText className="mx-auto h-12 w-12 text-slate-300 mb-3" />
              <h3 className="text-sm font-bold text-slate-800">Extraction in Progress</h3>
              <p className="mt-1 text-xs text-slate-500 max-w-sm mx-auto">
                AI extraction is currently running for this document. Once complete, fields and line items will appear here automatically.
              </p>
              <button
                type="button"
                onClick={handleRefresh}
                className="mt-4 rounded-md border border-slate-300 bg-white px-3.5 py-1.5 text-xs font-semibold text-slate-700 shadow-sm hover:bg-slate-50"
              >
                Check Now
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
