"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import type { DocumentResponse } from "./types";

export interface UseDocumentPollingOptions {
  documentId: string | null;
  enabled?: boolean;
  intervalMs?: number;
  onStatusChange?: (newStatus: string, doc: DocumentResponse) => void;
  onTerminal?: (status: string, doc: DocumentResponse) => void;
}

const TERMINAL_STATUSES = new Set([
  "ready",
  "needs_review",
  "confirmed",
  "failed",
]);

/**
 * Polls GET /api/v1/documents/{id} every 2 seconds while document status is non-terminal (queued/processing).
 * Stops polling when status becomes ready, needs_review, confirmed, or failed.
 */
export function useDocumentPolling({
  documentId,
  enabled = true,
  intervalMs = 2000,
  onStatusChange,
  onTerminal,
}: UseDocumentPollingOptions) {
  const [document, setDocument] = useState<DocumentResponse | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [isPolling, setIsPolling] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const prevStatusRef = useRef<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isMountedRef = useRef<boolean>(true);

  const fetchStatus = useCallback(async () => {
    if (!documentId) return;

    try {
      const res = await fetch(`/api/v1/documents/${documentId}`, {
        headers: { Accept: "application/json" },
      });

      if (!isMountedRef.current) return;

      if (!res.ok) {
        if (res.status === 404) {
          setError("Document not found");
        } else {
          setError(`HTTP ${res.status}`);
        }
        setIsPolling(false);
        return;
      }

      const data: DocumentResponse = await res.json();
      setDocument(data);
      setStatus(data.status);
      setError(null);

      if (prevStatusRef.current !== data.status) {
        onStatusChange?.(data.status, data);
        prevStatusRef.current = data.status;
      }

      // Check if terminal
      if (TERMINAL_STATUSES.has(data.status)) {
        setIsPolling(false);
        onTerminal?.(data.status, data);
      } else if (enabled) {
        // Schedule next poll
        timerRef.current = setTimeout(fetchStatus, intervalMs);
      }
    } catch (err: unknown) {
      if (!isMountedRef.current) return;
      const msg = err instanceof Error ? err.message : "Polling failed";
      setError(msg);
      // Retry after interval if still enabled
      if (enabled) {
        timerRef.current = setTimeout(fetchStatus, intervalMs);
      }
    }
  }, [documentId, enabled, intervalMs, onStatusChange, onTerminal]);

  useEffect(() => {
    isMountedRef.current = true;

    if (!documentId || !enabled) {
      setIsPolling(false);
      return;
    }

    setIsPolling(true);
    fetchStatus();

    return () => {
      isMountedRef.current = false;
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
    };
  }, [documentId, enabled, fetchStatus]);

  const refetch = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    return fetchStatus();
  }, [fetchStatus]);

  return {
    document,
    status,
    isPolling,
    error,
    refetch,
  };
}
