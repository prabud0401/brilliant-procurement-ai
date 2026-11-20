"use client";

import React, { useState } from "react";
import { ZoomIn, ZoomOut, RotateCcw, ExternalLink } from "lucide-react";
import { HighlightOverlay } from "./HighlightOverlay";
import type { BoundingBox } from "@/lib/documents/bbox";

export interface ImageViewerProps {
  documentId: string;
  highlightBox?: BoundingBox | null;
  highlightLabel?: string;
  className?: string;
}

export const ImageViewer: React.FC<ImageViewerProps> = ({
  documentId,
  highlightBox,
  highlightLabel,
  className = "",
}) => {
  const [scale, setScale] = useState<number>(1.0);

  const handleZoomIn = () => setScale((s) => Math.min(2.5, +(s + 0.2).toFixed(1)));
  const handleZoomOut = () => setScale((s) => Math.max(0.6, +(s - 0.2).toFixed(1)));
  const handleZoomReset = () => setScale(1.0);

  const fileUrl = `/api/v1/documents/${documentId}/file`;

  return (
    <div
      className={`flex flex-col h-full rounded-lg border border-slate-200 bg-slate-100/70 shadow-inner overflow-hidden ${className}`}
      data-testid="image-viewer"
    >
      {/* Toolbar */}
      <div className="flex items-center justify-between border-b border-slate-200 bg-white px-3 py-2 text-xs">
        <span className="font-semibold text-slate-700">Image Document</span>

        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={handleZoomOut}
            disabled={scale <= 0.6}
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
            disabled={scale >= 2.5}
            aria-label="Zoom In"
            className="rounded p-1 text-slate-600 hover:bg-slate-100 disabled:opacity-40"
          >
            <ZoomIn className="h-4 w-4" />
          </button>

          <button
            type="button"
            onClick={handleZoomReset}
            disabled={scale === 1.0}
            aria-label="Reset Zoom"
            className="rounded p-1 text-slate-600 hover:bg-slate-100 disabled:opacity-40 ml-1"
          >
            <RotateCcw className="h-3.5 w-3.5" />
          </button>

          <div className="h-4 w-px bg-slate-200 mx-1" />

          <a
            href={fileUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-[11px] font-medium text-blue-600 hover:text-blue-800"
          >
            <ExternalLink className="h-3.5 w-3.5" />
            <span>Open</span>
          </a>
        </div>
      </div>

      {/* Main Image Area */}
      <div tabIndex={0} role="region" aria-label="Image Document Viewer" className="flex-1 overflow-auto p-4 flex justify-center items-start">
        <div
          className="relative shadow-md rounded bg-white"
          style={{
            transform: `scale(${scale})`,
            transformOrigin: "top center",
            transition: "transform 0.15s ease-out",
          }}
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={fileUrl}
            alt="Original document view"
            className="max-w-full block rounded"
          />

          {highlightBox && (
            <HighlightOverlay
              bbox={highlightBox}
              label={highlightLabel}
            />
          )}
        </div>
      </div>
    </div>
  );
};
