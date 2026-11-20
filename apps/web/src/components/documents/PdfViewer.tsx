"use client";

import React, { useEffect, useRef, useState, useCallback } from "react";
import {
  ChevronLeft,
  ChevronRight,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  ExternalLink,
  AlertCircle,
  Loader2,
} from "lucide-react";
import { HighlightOverlay } from "./HighlightOverlay";
import type { BoundingBox } from "@/lib/documents/bbox";
import type { PDFDocumentProxy, RenderTask } from "pdfjs-dist";

export interface PdfViewerProps {
  documentId: string;
  activePage: number;
  highlightBox?: BoundingBox | null;
  highlightLabel?: string;
  onPageChange?: (page: number) => void;
  className?: string;
}

export const PdfViewer: React.FC<PdfViewerProps> = ({
  documentId,
  activePage,
  highlightBox,
  highlightLabel,
  onPageChange,
  className = "",
}) => {
  const [numPages, setNumPages] = useState<number>(1);
  const [scale, setScale] = useState<number>(1.0);
  const [loading, setLoading] = useState<boolean>(true);
  const [pageRendering, setPageRendering] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const pdfDocRef = useRef<PDFDocumentProxy | null>(null);
  const renderTaskRef = useRef<RenderTask | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  // 1. Load the PDF document
  useEffect(() => {
    let isCancelled = false;
    setLoading(true);
    setError(null);

    const loadPdf = async () => {
      try {
        const pdfjsLib = await import("pdfjs-dist");
        if (!pdfjsLib.GlobalWorkerOptions.workerSrc) {
          pdfjsLib.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";
        }

        const res = await fetch(`/api/v1/documents/${documentId}/file`);
        if (!res.ok) {
          throw new Error(`Failed to load document file (HTTP ${res.status})`);
        }

        const buffer = await res.arrayBuffer();
        if (isCancelled) return;

        const loadingTask = pdfjsLib.getDocument({
          data: buffer,
          cMapUrl: "/cmaps/",
          cMapPacked: true,
        });

        const doc = await loadingTask.promise;
        if (isCancelled) return;

        pdfDocRef.current = doc;
        setNumPages(doc.numPages);
        setLoading(false);
      } catch (err: unknown) {
        if (isCancelled) return;
        const msg = err instanceof Error ? err.message : "Failed to parse PDF document.";
        setError(msg);
        setLoading(false);
      }
    };

    loadPdf();

    return () => {
      isCancelled = true;
      if (renderTaskRef.current) {
        try {
          renderTaskRef.current.cancel();
        } catch {
          // ignore cancel error
        }
      }
    };
  }, [documentId]);

  // 2. Render page when activePage or scale changes
  const renderPage = useCallback(
    async (pageNum: number) => {
      const doc = pdfDocRef.current;
      const canvas = canvasRef.current;
      if (!doc || !canvas) return;

      if (renderTaskRef.current) {
        try {
          renderTaskRef.current.cancel();
        } catch {
          // ignore cancel error
        }
      }

      try {
        setPageRendering(true);
        const page = await doc.getPage(pageNum);
        const viewport = page.getViewport({ scale });

        // Set dimensions for high-DPI display
        const dpr = typeof window !== "undefined" ? window.devicePixelRatio || 1 : 1;
        canvas.width = viewport.width * dpr;
        canvas.height = viewport.height * dpr;
        canvas.style.width = `${viewport.width}px`;
        canvas.style.height = `${viewport.height}px`;

        const ctx = canvas.getContext("2d");
        if (!ctx) return;
        ctx.scale(dpr, dpr);

        const renderContext = {
          canvasContext: ctx,
          viewport,
          canvas,
        };

        const renderTask = page.render(renderContext);
        renderTaskRef.current = renderTask;
        await renderTask.promise;
      } catch (err: unknown) {
        if ((err as { name?: string })?.name !== "RenderingCancelledException") {
          console.error("PDF render error:", err);
        }
      } finally {
        setPageRendering(false);
      }
    },
    [scale]
  );

  useEffect(() => {
    if (!loading && pdfDocRef.current) {
      const targetPage = Math.max(1, Math.min(activePage, numPages));
      renderPage(targetPage);
    }
  }, [loading, activePage, numPages, renderPage]);

  // Zoom handlers
  const handleZoomIn = () => setScale((s) => Math.min(2.5, +(s + 0.2).toFixed(1)));
  const handleZoomOut = () => setScale((s) => Math.max(0.6, +(s - 0.2).toFixed(1)));
  const handleZoomReset = () => setScale(1.0);

  // Navigation handlers
  const handlePrevPage = () => {
    if (activePage > 1) {
      onPageChange?.(activePage - 1);
    }
  };

  const handleNextPage = () => {
    if (activePage < numPages) {
      onPageChange?.(activePage + 1);
    }
  };

  const showHighlight =
    Boolean(highlightBox) &&
    (highlightBox?.page === undefined || highlightBox?.page === activePage);

  return (
    <div
      ref={containerRef}
      className={`flex flex-col h-full rounded-lg border border-slate-200 bg-slate-100/70 shadow-inner overflow-hidden ${className}`}
      data-testid="pdf-viewer"
    >
      {/* Viewer Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 bg-white px-3 py-2 text-xs">
        {/* Page navigation */}
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={handlePrevPage}
            disabled={activePage <= 1 || loading}
            aria-label="Previous Page"
            className="rounded p-1 text-slate-600 hover:bg-slate-100 disabled:opacity-40 disabled:hover:bg-transparent"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>

          <span className="font-medium text-slate-700 select-none">
            Page {activePage} of {numPages}
          </span>

          <button
            type="button"
            onClick={handleNextPage}
            disabled={activePage >= numPages || loading}
            aria-label="Next Page"
            className="rounded p-1 text-slate-600 hover:bg-slate-100 disabled:opacity-40 disabled:hover:bg-transparent"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>

        {/* Zoom controls & External link */}
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={handleZoomOut}
            disabled={scale <= 0.6 || loading}
            aria-label="Zoom Out"
            className="rounded p-1 text-slate-600 hover:bg-slate-100 disabled:opacity-40"
          >
            <ZoomOut className="h-4 w-4" />
          </button>

          <span className="w-12 text-center font-mono font-medium text-slate-600 select-none">
            {Math.round(scale * 100)}%
          </span>

          <button
            type="button"
            onClick={handleZoomIn}
            disabled={scale >= 2.5 || loading}
            aria-label="Zoom In"
            className="rounded p-1 text-slate-600 hover:bg-slate-100 disabled:opacity-40"
          >
            <ZoomIn className="h-4 w-4" />
          </button>

          <button
            type="button"
            onClick={handleZoomReset}
            disabled={scale === 1.0 || loading}
            aria-label="Reset Zoom"
            title="Reset Zoom"
            className="rounded p-1 text-slate-600 hover:bg-slate-100 disabled:opacity-40 ml-1"
          >
            <RotateCcw className="h-3.5 w-3.5" />
          </button>

          <div className="h-4 w-px bg-slate-200 mx-1" />

          <a
            href={`/api/v1/documents/${documentId}/file`}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-[11px] font-medium text-blue-600 hover:text-blue-800"
            title="Open raw document in new tab"
          >
            <ExternalLink className="h-3.5 w-3.5" />
            <span>Open</span>
          </a>
        </div>
      </div>

      {/* Main Canvas Viewport Area */}
      <div tabIndex={0} role="region" aria-label="PDF Document Viewer" className="flex-1 overflow-auto p-4 flex justify-center items-start relative">
        {loading && (
          <div className="my-auto flex flex-col items-center justify-center p-8 text-slate-500">
            <Loader2 className="h-8 w-8 animate-spin text-blue-600 mb-2" />
            <p className="text-xs">Loading document viewer...</p>
          </div>
        )}

        {error && (
          <div className="my-auto max-w-sm rounded-lg border border-rose-200 bg-white p-4 text-center shadow-sm">
            <AlertCircle className="mx-auto h-8 w-8 text-rose-500 mb-2" />
            <h4 className="text-sm font-semibold text-slate-900">Failed to render PDF</h4>
            <p className="mt-1 text-xs text-slate-600">{error}</p>
            <a
              href={`/api/v1/documents/${documentId}/file`}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-3 inline-block rounded bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-blue-700"
            >
              Download PDF Directly
            </a>
          </div>
        )}

        {/* Canvas & Overlay Wrapper */}
        <div
          className={`relative shadow-md transition-opacity duration-200 ${
            loading || error ? "hidden" : "block"
          }`}
          style={{ maxWidth: "100%" }}
        >
          <canvas
            ref={canvasRef}
            aria-label={`PDF page ${activePage}`}
            role="img"
            className="block bg-white rounded"
          />

          {/* Active Bounding Box Highlight Overlay */}
          {showHighlight && (
            <HighlightOverlay
              bbox={highlightBox}
              label={highlightLabel}
            />
          )}

          {pageRendering && (
            <div className="absolute inset-0 bg-white/40 flex items-center justify-center pointer-events-none">
              <Loader2 className="h-6 w-6 animate-spin text-blue-600" />
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
