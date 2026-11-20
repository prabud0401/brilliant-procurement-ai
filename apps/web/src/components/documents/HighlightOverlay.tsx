"use client";

import React from "react";
import { bboxToOverlay, type BoundingBox, type OverlayScalingOptions } from "@/lib/documents/bbox";

export interface HighlightOverlayProps {
  bbox: BoundingBox | null | undefined;
  options?: OverlayScalingOptions;
  label?: string;
  className?: string;
}

export const HighlightOverlay: React.FC<HighlightOverlayProps> = ({
  bbox,
  options,
  label,
  className = "",
}) => {
  const overlay = bboxToOverlay(bbox, options);
  if (!overlay) return null;

  return (
    <div
      style={overlay.style}
      data-testid="bbox-highlight-overlay"
      className={`absolute pointer-events-none rounded border-2 border-blue-600 bg-blue-500/25 ring-2 ring-blue-400/50 shadow-sm transition-all duration-300 ease-out z-20 ${className}`}
      aria-hidden="true"
    >
      {label && (
        <span className="absolute -top-6 left-0 truncate max-w-[200px] rounded bg-blue-700 px-1.5 py-0.5 text-[10px] font-semibold text-white shadow">
          {label}
        </span>
      )}
    </div>
  );
};
