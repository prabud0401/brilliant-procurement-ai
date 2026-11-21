import { describe, it, expect, vi, beforeEach } from "vitest";
import React from "react";
import { render, screen, act, fireEvent } from "@testing-library/react";
import { DocumentListTable } from "@/components/documents/DocumentListTable";
import { PRDetail } from "@/components/flow/PRDetail";
import { MatchDetail } from "@/components/flow/MatchDetail";
import { formatDocumentTitle } from "@/lib/formatters";
import type { DocumentSummary } from "@/lib/documents/types";
import type { PurchaseRequest, MatchResult } from "@/lib/flow/types";

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    refresh: vi.fn(),
  }),
}));

describe("formatDocumentTitle helper", () => {
  it("formats vendor and document number with middle dot", () => {
    expect(
      formatDocumentTitle({
        vendor_name: "Gulf Line IT Trading",
        document_number: "Q-1042",
      })
    ).toBe("Gulf Line IT Trading · Q-1042");
  });

  it("returns vendor only when document number is missing", () => {
    expect(
      formatDocumentTitle({
        vendor_name: "Falcon Supplies",
        document_number: null,
      })
    ).toBe("Falcon Supplies");
  });

  it("returns document number only when vendor is missing", () => {
    expect(
      formatDocumentTitle({
        vendor_name: null,
        document_number: "INV-2291",
      })
    ).toBe("INV-2291");
  });

  it("falls back to document type label when both are missing", () => {
    expect(
      formatDocumentTitle({
        vendor_name: null,
        document_number: null,
        doc_type: "quote",
      })
    ).toBe("Quotation");

    expect(
      formatDocumentTitle({
        vendor_name: null,
        document_number: null,
        doc_type: "invoice",
      })
    ).toBe("Invoice");
  });

  it("never returns raw UUID when doc has an id", () => {
    const rawUuid = "939d451f-b52b-4dbd-8869-7c87c0ff7930";
    const title = formatDocumentTitle({
      vendor_name: "Gulf Line IT Trading",
      document_number: "Q-1042",
      doc_type: "quote",
    });
    expect(title).not.toContain(rawUuid);
    expect(title).toBe("Gulf Line IT Trading · Q-1042");
  });
});

describe("DocumentListTable human-readable titles (F31)", () => {
  const docWithVendorAndNum: DocumentSummary = {
    id: "939d451f-b52b-4dbd-8869-7c87c0ff7930",
    doc_type: "quote",
    status: "confirmed",
    pages: 2,
    size_bytes: 4096,
    created_at: new Date().toISOString(),
    duplicate_of: null,
    suspicious: false,
    vendor_name: "Gulf Line IT Trading",
    document_number: "Q-1042",
  };

  const docFallback: DocumentSummary = {
    id: "a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d",
    doc_type: "invoice",
    status: "ready",
    pages: 1,
    size_bytes: 2048,
    created_at: new Date().toISOString(),
    duplicate_of: null,
    suspicious: false,
    vendor_name: null,
    document_number: null,
  };

  beforeEach(() => {
    vi.spyOn(global, "fetch").mockImplementation(async (url) => {
      const u = String(url);
      if (u.includes("/api/v1/documents")) {
        return {
          ok: true,
          status: 200,
          json: async () => [docWithVendorAndNum, docFallback],
        } as unknown as Response;
      }
      return {
        ok: true,
        status: 200,
        json: async () => [],
      } as unknown as Response;
    });
  });

  it("renders 'Vendor · NUMBER' and does not use UUID as primary visible title", async () => {
    await act(async () => {
      render(<DocumentListTable userRoles={["buyer"]} onToast={vi.fn()} />);
    });

    // Primary visible link text for doc 1
    const link = screen.getByRole("link", { name: "Gulf Line IT Trading · Q-1042" });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute("href", `/documents/${docWithVendorAndNum.id}`);

    // UUID is NOT the primary link text
    expect(screen.queryByRole("link", { name: docWithVendorAndNum.id })).toBeNull();

    // Fallback doc renders doc_type label as title, not raw UUID
    const fallbackLink = screen.getByRole("link", { name: "Invoice" });
    expect(fallbackLink).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: docFallback.id })).toBeNull();
  });

  it("allows searching documents by vendor name and document number", async () => {
    await act(async () => {
      render(<DocumentListTable userRoles={["buyer"]} onToast={vi.fn()} />);
    });

    const searchInput = screen.getByPlaceholderText(
      "Search by vendor, document number, ID, or type..."
    );

    // Search by vendor name
    await act(async () => {
      fireEvent.change(searchInput, { target: { value: "Gulf Line" } });
    });
    expect(screen.getByRole("link", { name: "Gulf Line IT Trading · Q-1042" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Invoice" })).toBeNull();

    // Search by document number
    await act(async () => {
      fireEvent.change(searchInput, { target: { value: "Q-1042" } });
    });
    expect(screen.getByRole("link", { name: "Gulf Line IT Trading · Q-1042" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Invoice" })).toBeNull();
  });
});

describe("PRDetail linked quotations title (F31)", () => {
  const mockPr: PurchaseRequest = {
    id: "pr-001",
    number: "PR-2026-0001",
    title: "IT Equipment Refresh",
    department_id: "dept-1",
    requester_id: "user-1",
    status: "draft",
    currency: "AED",
    total_aed: "28875.00",
    created_at: new Date().toISOString(),
    lines: [],
  };

  const mockQuote: DocumentSummary = {
    id: "939d451f-b52b-4dbd-8869-7c87c0ff7930",
    doc_type: "quote",
    status: "confirmed",
    pages: 2,
    size_bytes: 4096,
    created_at: new Date().toISOString(),
    duplicate_of: null,
    suspicious: false,
    vendor_name: "Gulf Line IT Trading",
    document_number: "Q-1042",
  };

  beforeEach(() => {
    vi.spyOn(global, "fetch").mockImplementation(async (url) => {
      const u = String(url);
      if (u.includes("doc_type=quote")) {
        return {
          ok: true,
          status: 200,
          json: async () => [mockQuote],
        } as unknown as Response;
      }
      return {
        ok: true,
        status: 200,
        json: async () => [],
      } as unknown as Response;
    });
  });

  it("renders 'Vendor · NUMBER' and does not use 'Quotation Document (uuid...)'", async () => {
    await act(async () => {
      render(
        <PRDetail pr={mockPr} userRoles={["buyer"]} userId="user-1" onToast={vi.fn()} />
      );
    });

    // Should display human title
    const link = screen.getByRole("link", { name: "Gulf Line IT Trading · Q-1042" });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute("href", `/documents/${mockQuote.id}`);

    // Should NOT display old uuid label
    expect(screen.queryByText(/Quotation Document \(939d451f/)).toBeNull();
  });
});

describe("MatchDetail heading (F31)", () => {
  it("uses invoice document number and vendor without leading with truncated UUID", () => {
    const mockMatch: MatchResult = {
      id: "m-001",
      invoice_document_id: "939d451f-b52b-4dbd-8869-7c87c0ff7930",
      po_id: "po-001",
      overall_status: "matched",
      lines: [],
      exceptions: [],
      tolerances_snapshot: {},
      created_at: new Date().toISOString(),
      invoice_document_number: "INV-2291",
      vendor_name: "Gulf Line IT Trading",
    };

    render(<MatchDetail match={mockMatch} userRoles={["buyer"]} />);

    // Heading should lead with human-readable vendor and number
    const heading = screen.getByRole("heading", { level: 1 });
    expect(heading).toHaveTextContent(
      "Match Evaluation for Invoice Gulf Line IT Trading · INV-2291"
    );

    // Should not lead with truncated UUID in heading
    expect(heading.textContent).not.toContain("939d451f...");
  });

  it("renders gracefully when only invoice_document_number is available", () => {
    const mockMatch: MatchResult = {
      id: "m-002",
      invoice_document_id: "939d451f-b52b-4dbd-8869-7c87c0ff7930",
      po_id: "po-001",
      overall_status: "matched",
      lines: [],
      exceptions: [],
      tolerances_snapshot: {},
      created_at: new Date().toISOString(),
      invoice_document_number: "INV-2291",
      vendor_name: null,
    };

    render(<MatchDetail match={mockMatch} userRoles={["buyer"]} />);

    const heading = screen.getByRole("heading", { level: 1 });
    expect(heading).toHaveTextContent("Match Evaluation for Invoice INV-2291");
  });
});
