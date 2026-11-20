"use client";

import React from "react";
import dynamic from "next/dynamic";
import { ImageViewer } from "./ImageViewer";
import type { BoundingBox } from "@/lib/documents/bbox";
import { Skeleton } from "@/components/ui/Skeleton";

// Dynamically import PdfViewer to prevent SSR canvas/web-worker issues
const DynamicPdfViewer = dynamic(
  () => import("./PdfViewer").then((mod) => mod.PdfViewer),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-full flex-col items-center justify-center p-8 bg-slate-50 border border-slate-200 rounded-lg">
        <Skeleton className="h-6 w-48 mb-4" />
        <Skeleton className="h-[450px] w-full max-w-lg rounded-md" />
      </div>
    ),
  }
);

export interface DocumentViewerProps {
  documentId: string;
  mimeType: string;
  activePage: number;
  highlightBox?: BoundingBox | null;
  highlightLabel?: string;
  onPageChange?: (page: number) => void;
  className?: string;
}

export const DocumentViewer: React.FC<DocumentViewerProps> = ({
  documentId,
  mimeType,
  activePage,
  highlightBox,
  highlightLabel,
  onPageChange,
  className = "",
}) => {
  const isPdf = mimeType === "application/pdf" || mimeType.includes("pdf");

  if (isPdf) {
    return (
      <DynamicPdfViewer
        documentId={documentId}
        activePage={activePage}
        highlightBox={highlightBox}
        highlightLabel={highlightLabel}
        onPageChange={onPageChange}
        className={className}
      />
    );
  }

  return (
    <ImageViewer
      documentId={documentId}
      highlightBox={highlightBox}
      highlightLabel={highlightLabel}
      className={className}
    />
  );
};
