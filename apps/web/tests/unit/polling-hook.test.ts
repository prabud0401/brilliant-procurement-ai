import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useDocumentPolling } from "@/lib/documents/use-document-polling";
import type { DocumentResponse } from "@/lib/documents/types";

describe("useDocumentPolling hook (with fake timers)", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  const mockDoc = (status: string): DocumentResponse => ({
    id: "doc-123",
    owner_id: "user-1",
    department_id: "dept-1",
    pr_id: null,
    po_id: null,
    vendor_id: null,
    doc_type: "quote",
    status,
    file_sha256: "hash123",
    mime: "application/pdf",
    pages: 1,
    size_bytes: 1024,
    source: "upload",
    duplicate_of: null,
    duplicate_cleared_reason: null,
    suspicious: false,
    suspicious_ack_reason: null,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  });

  it("does not poll when documentId is null or enabled is false", () => {
    const fetchSpy = vi.spyOn(global, "fetch");

    renderHook(() =>
      useDocumentPolling({
        documentId: null,
        enabled: true,
      })
    );

    renderHook(() =>
      useDocumentPolling({
        documentId: "doc-123",
        enabled: false,
      })
    );

    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("polls every 2000ms through queued -> processing -> needs_review and stops on terminal status", async () => {
    const statusSequence = ["queued", "processing", "needs_review"];
    let callCount = 0;

    const onStatusChange = vi.fn();
    const onTerminal = vi.fn();

    vi.spyOn(global, "fetch").mockImplementation(async () => {
      const currentStatus = statusSequence[Math.min(callCount, statusSequence.length - 1)];
      callCount++;
      return {
        ok: true,
        status: 200,
        json: async () => mockDoc(currentStatus),
      } as Response;
    });

    const { result } = renderHook(() =>
      useDocumentPolling({
        documentId: "doc-123",
        intervalMs: 2000,
        onStatusChange,
        onTerminal,
      })
    );

    // Initial fetch (call 1: queued)
    await act(async () => {
      await Promise.resolve();
    });

    expect(result.current.status).toBe("queued");
    expect(result.current.isPolling).toBe(true);
    expect(onStatusChange).toHaveBeenCalledWith("queued", expect.anything());

    // Advance 2000ms (call 2: processing)
    await act(async () => {
      vi.advanceTimersByTime(2000);
      await Promise.resolve();
    });

    expect(result.current.status).toBe("processing");
    expect(result.current.isPolling).toBe(true);
    expect(onStatusChange).toHaveBeenCalledWith("processing", expect.anything());

    // Advance 2000ms (call 3: needs_review - terminal status)
    await act(async () => {
      vi.advanceTimersByTime(2000);
      await Promise.resolve();
    });

    expect(result.current.status).toBe("needs_review");
    expect(result.current.isPolling).toBe(false);
    expect(onTerminal).toHaveBeenCalledWith("needs_review", expect.anything());

    // Further timer advances should NOT make any more fetch calls
    const callsAfterTerminal = callCount;
    await act(async () => {
      vi.advanceTimersByTime(5000);
      await Promise.resolve();
    });
    expect(callCount).toBe(callsAfterTerminal);
  });

  it("stops polling and sets terminal state when status is failed", async () => {
    const onTerminal = vi.fn();

    vi.spyOn(global, "fetch").mockImplementation(async () => {
      return {
        ok: true,
        status: 200,
        json: async () => mockDoc("failed"),
      } as Response;
    });

    const { result } = renderHook(() =>
      useDocumentPolling({
        documentId: "doc-failed",
        onTerminal,
      })
    );

    await act(async () => {
      await Promise.resolve();
    });

    expect(result.current.status).toBe("failed");
    expect(result.current.isPolling).toBe(false);
    expect(onTerminal).toHaveBeenCalledWith("failed", expect.anything());
  });

  it("handles HTTP 404 error cleanly", async () => {
    vi.spyOn(global, "fetch").mockImplementation(async () => {
      return {
        ok: false,
        status: 404,
      } as Response;
    });

    const { result } = renderHook(() =>
      useDocumentPolling({
        documentId: "missing-doc",
      })
    );

    await act(async () => {
      await Promise.resolve();
    });

    expect(result.current.error).toBe("Document not found");
    expect(result.current.isPolling).toBe(false);
  });

  it("cleans up active timers on unmount", async () => {
    vi.spyOn(global, "fetch").mockImplementation(async () => {
      return {
        ok: true,
        status: 200,
        json: async () => mockDoc("queued"),
      } as Response;
    });

    const { unmount } = renderHook(() =>
      useDocumentPolling({
        documentId: "doc-cleanup",
        intervalMs: 2000,
      })
    );

    await act(async () => {
      await Promise.resolve();
    });

    unmount();

    // Advancing timers should not cause errors
    await act(async () => {
      vi.advanceTimersByTime(5000);
      await Promise.resolve();
    });
  });
});
