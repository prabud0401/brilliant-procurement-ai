import { describe, it, expect, vi } from "vitest";
import React from "react";
import { render, screen, act } from "@testing-library/react";
import { DocumentListTable } from "@/components/documents/DocumentListTable";
import { ExtractionReview } from "@/components/documents/ExtractionReview";
import type {
  DocumentResponse,
  ExtractionResponse,
} from "@/lib/documents/types";

// Mock fetch for document list table
vi.spyOn(global, "fetch").mockImplementation(async () => ({
  ok: true,
  status: 200,
  json: async () => [],
}) as unknown as Response);

describe("Role-based action and UI visibility per Design 7.2", () => {
  const mockDoc: DocumentResponse = {
    id: "doc-100",
    owner_id: "user-1",
    department_id: null,
    pr_id: null,
    po_id: null,
    vendor_id: "02ccc52b-65a0-5878-807e-419178e7b553",
    doc_type: "quote",
    status: "needs_review",
    file_sha256: "hash123",
    mime: "application/pdf",
    pages: 1,
    size_bytes: 4096,
    source: "upload",
    duplicate_of: null,
    duplicate_cleared_reason: null,
    suspicious: false,
    suspicious_ack_reason: null,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };

  const mockExtraction: ExtractionResponse = {
    id: "ext-1",
    document_id: "doc-100",
    version: 1,
    di_model: "prebuilt-layout",
    llm_model: "gpt-4o-mini",
    prompt_version: "v1",
    status: "completed",
    created_at: new Date().toISOString(),
    fields: [
      {
        id: "f-1",
        name: "total",
        value_raw: "28875.00",
        value_norm: null,
        confidence: 0.75, // needs review
        page: 1,
        bbox: null,
        status: "needs_review",
        validation_msg: null,
        confirmed_by: null,
        confirmed_at: null,
      },
    ],
    lines: [],
  };

  describe("DocumentListTable role visibility", () => {
    it("Buyer sees 'Upload Document' button", async () => {
      await act(async () => {
        render(<DocumentListTable userRoles={["buyer"]} onToast={vi.fn()} />);
      });
      expect(screen.getByTestId("open-upload-modal-btn")).toBeInTheDocument();
    });

    it("Requester sees 'Upload Document' button (for own uploads)", async () => {
      await act(async () => {
        render(<DocumentListTable userRoles={["requester"]} onToast={vi.fn()} />);
      });
      expect(screen.getByTestId("open-upload-modal-btn")).toBeInTheDocument();
    });

    it("Manager does NOT see 'Upload Document' button", async () => {
      await act(async () => {
        render(<DocumentListTable userRoles={["manager"]} onToast={vi.fn()} />);
      });
      expect(screen.queryByTestId("open-upload-modal-btn")).not.toBeInTheDocument();
    });

    it("Admin does NOT see 'Upload Document' button", async () => {
      await act(async () => {
        render(<DocumentListTable userRoles={["admin"]} onToast={vi.fn()} />);
      });
      expect(screen.queryByTestId("open-upload-modal-btn")).not.toBeInTheDocument();
    });
  });

  describe("ExtractionReview role visibility", () => {
    it("Buyer sees review actions: Correct button, Confirm button, Change Vendor, and Confirm Document button", () => {
      render(
        <ExtractionReview
          document={mockDoc}
          extraction={mockExtraction}
          userRoles={["buyer"]}
          selectedHighlight={null}
          onSelectHighlight={vi.fn()}
          onRefresh={vi.fn()}
          onToast={vi.fn()}
        />
      );

      // Buyer actions
      expect(screen.getByText("Change Vendor")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Confirm" })).toBeInTheDocument();
      expect(screen.getByTestId("confirm-document-btn")).toBeInTheDocument();
    });

    it("Requester views document in read-only mode (no review/edit/confirm actions)", () => {
      render(
        <ExtractionReview
          document={mockDoc}
          extraction={mockExtraction}
          userRoles={["requester"]}
          selectedHighlight={null}
          onSelectHighlight={vi.fn()}
          onRefresh={vi.fn()}
          onToast={vi.fn()}
        />
      );

      // Read-only notification
      expect(screen.getByText(/You are viewing this document in read-only mode/i)).toBeInTheDocument();

      // Buyer-only buttons must NOT be present
      expect(screen.queryByText("Change Vendor")).not.toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "Confirm" })).not.toBeInTheDocument();
      expect(screen.queryByTestId("confirm-document-btn")).not.toBeInTheDocument();
    });

    it("Manager views document in read-only mode", () => {
      render(
        <ExtractionReview
          document={mockDoc}
          extraction={mockExtraction}
          userRoles={["manager"]}
          selectedHighlight={null}
          onSelectHighlight={vi.fn()}
          onRefresh={vi.fn()}
          onToast={vi.fn()}
        />
      );

      expect(screen.getByText(/You are viewing this document in read-only mode/i)).toBeInTheDocument();
      expect(screen.queryByTestId("confirm-document-btn")).not.toBeInTheDocument();
    });

    it("Admin views metadata only and cannot perform review actions", () => {
      render(
        <ExtractionReview
          document={mockDoc}
          extraction={mockExtraction}
          userRoles={["admin"]}
          selectedHighlight={null}
          onSelectHighlight={vi.fn()}
          onRefresh={vi.fn()}
          onToast={vi.fn()}
        />
      );

      expect(screen.getByText(/Admin View:/i)).toBeInTheDocument();
      expect(screen.queryByTestId("confirm-document-btn")).not.toBeInTheDocument();
    });
  });
});
