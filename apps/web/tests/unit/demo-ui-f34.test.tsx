import { describe, it, expect, vi, beforeEach } from "vitest";
import React from "react";
import { render, screen, act } from "@testing-library/react";
import { ToastProvider } from "@/components/ui/Toast";
import { DocumentListTable } from "@/components/documents/DocumentListTable";
import { ReviewClient } from "@/components/documents/ReviewClient";
import { PRDetail } from "@/components/flow/PRDetail";
import { PODetail } from "@/components/flow/PODetail";
import { MatchDetail } from "@/components/flow/MatchDetail";
import { ExceptionQueue } from "@/components/flow/ExceptionQueue";
import AuditPage from "@/app/(dashboard)/audit/page";
import MatchesPage from "@/app/(dashboard)/matches/page";
import type { DocumentSummary, DocumentResponse } from "@/lib/documents/types";
import type { PurchaseRequest, PurchaseOrder, MatchResult, MatchException } from "@/lib/flow/types";

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    refresh: vi.fn(),
  }),
}));

describe("F34 Demo UI Tests", () => {
  const docId = "939d451f-b52b-4dbd-8869-7c87c0ff7930";
  const docId2 = "a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d";

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  describe("1. Hide UUIDs across components", () => {
    it("documents table does not render secondary full-UUID line", async () => {
      const mockDoc: DocumentSummary = {
        id: docId,
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

      vi.spyOn(global, "fetch").mockImplementation(async (url) => {
        const u = String(url);
        if (u.includes("/api/v1/documents")) {
          return {
            ok: true,
            status: 200,
            json: async () => [mockDoc],
          } as unknown as Response;
        }
        return {
          ok: true,
          status: 200,
          json: async () => [],
        } as unknown as Response;
      });

      await act(async () => {
        render(<DocumentListTable userRoles={["buyer"]} onToast={vi.fn()} />);
      });

      // Human title is visible
      expect(screen.getByRole("link", { name: "Gulf Line IT Trading · Q-1042" })).toBeInTheDocument();

      // Full UUID should NOT be rendered in the document cell
      expect(screen.queryByText(docId)).toBeNull();
    });

    it("document review header does not render 'ID: {uuid}' line", () => {
      const mockDoc: DocumentResponse = {
        id: docId,
        owner_id: "user-1",
        department_id: "dept-1",
        pr_id: null,
        po_id: null,
        vendor_id: null,
        doc_type: "invoice",
        status: "ready",
        file_sha256: "sha256-dummy",
        mime: "application/pdf",
        pages: 3,
        size_bytes: 12288,
        source: "upload",
        duplicate_of: null,
        duplicate_cleared_reason: null,
        suspicious: false,
        suspicious_ack_reason: null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };

      render(
        <ToastProvider>
          <ReviewClient
            initialDocument={mockDoc}
            initialExtraction={null}
            userRoles={["buyer"]}
          />
        </ToastProvider>
      );

      // The ID line should NOT contain the uuid
      expect(screen.queryByText(new RegExp(`ID: ${docId}`))).toBeNull();
      // Pages and size are preserved
      expect(screen.getByText(/3 page\(s\) • 12 KB/)).toBeInTheDocument();
    });

    it("PR linked quotes do not render truncated UUID suffix", async () => {
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
        id: docId,
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

      await act(async () => {
        render(
          <PRDetail pr={mockPr} userRoles={["buyer"]} userId="user-1" onToast={vi.fn()} />
        );
      });

      expect(screen.getByRole("link", { name: "Gulf Line IT Trading · Q-1042" })).toBeInTheDocument();
      // Should not contain (939d451f...)
      expect(screen.queryByText(/\(939d451f\.\.\.\)/)).toBeNull();
    });

    it("MatchDetail heading does not render truncated invoice UUID", () => {
      const mockMatch: MatchResult = {
        id: "m-001",
        invoice_document_id: docId,
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

      expect(screen.getByText("Match Evaluation for Invoice Gulf Line IT Trading · INV-2291")).toBeInTheDocument();
      // Should not contain (939d451f...)
      expect(screen.queryByText(/\(939d451f\.\.\.\)/)).toBeNull();
    });

    it("ExceptionQueue renders 'View match' without truncated match UUID", async () => {
      const mockException: MatchException = {
        id: "exc-001",
        match_id: docId,
        kind: "price_variance",
        reason: "Unit price exceeds PO agreed rate",
        amount_impact_aed: "250.00",
        status: "open",
        created_at: new Date().toISOString(),
      };

      vi.spyOn(global, "fetch").mockImplementation(async () => ({
        ok: true,
        status: 200,
        json: async () => [mockException],
      } as unknown as Response));

      await act(async () => {
        render(<ExceptionQueue userRoles={["buyer"]} onToast={vi.fn()} />);
      });

      const viewMatchLink = screen.getByRole("link", { name: "View match" });
      expect(viewMatchLink).toBeInTheDocument();
      expect(viewMatchLink).toHaveAttribute("href", `/matches/${docId}`);
      // Should not show Match ID: 939d451f...
      expect(screen.queryByText(/939d451f\.\.\./)).toBeNull();
    });

    it("Audit table renders human entity_label or type em-dash without UUIDs", async () => {
      const mockLogs = [
        {
          id: 1,
          occurred_at: new Date().toISOString(),
          action: "document.uploaded",
          entity_type: "document",
          entity_id: docId,
          entity_label: "Gulf Line IT Trading · Q-1042",
          actor_roles: ["buyer"],
          reason: "Uploaded quote",
          hash: "abcdef1234567890abcdef1234567890",
        },
        {
          id: 2,
          occurred_at: new Date().toISOString(),
          action: "user.login",
          entity_type: "auth",
          entity_id: docId2,
          entity_label: null,
          actor_roles: ["admin"],
          reason: "Login",
          hash: "123456abcdef123456abcdef123456ab",
        },
      ];

      vi.spyOn(global, "fetch").mockImplementation(async (url) => {
        const u = String(url);
        if (u.includes("/api/v1/audit")) {
          return {
            ok: true,
            status: 200,
            json: async () => ({ items: mockLogs, next_cursor: null }),
          } as unknown as Response;
        }
        return {
          ok: true,
          status: 200,
          json: async () => ({ roles: ["admin"] }),
        } as unknown as Response;
      });

      await act(async () => {
        render(<AuditPage />);
      });

      // Resolved entity label
      expect(screen.getByText("Gulf Line IT Trading · Q-1042")).toBeInTheDocument();
      // Unresolved fallback: entity type and em dash
      expect(screen.getByText("auth —")).toBeInTheDocument();
      // No sliced UUIDs in table
      expect(screen.queryByText(/939d451f\.\.\./)).toBeNull();
      expect(screen.queryByText(/a1b2c3d4\.\.\./)).toBeNull();
    });
  });

  describe("2. PO Title formatting", () => {
    it("renders vendor · PO number when both vendor and number exist", () => {
      const mockPo: PurchaseOrder = {
        id: "po-1",
        number: "PO-2026-6D79D3",
        vendor_id: "vendor-1",
        vendor_name: "Gulf Line IT Trading",
        department_id: "dept-1",
        created_by: "user-1",
        status: "approved",
        subtotal: "27500.00",
        vat: "1375.00",
        total: "28875.00",
        currency: "AED",
        created_at: new Date().toISOString(),
        lines: [],
      };

      render(<PODetail po={mockPo} userRoles={["buyer"]} userId="user-1" />);

      const heading = screen.getByRole("heading", { level: 1 });
      expect(heading).toHaveTextContent("Gulf Line IT Trading · PO-2026-6D79D3");
      expect(heading.textContent).not.toContain("Awarded Vendor");
    });

    it("falls back to PO number when vendor_name is absent and never Awarded Vendor", () => {
      const mockPo: PurchaseOrder = {
        id: "po-2",
        number: "PO-2026-1C8000",
        vendor_id: "vendor-2",
        department_id: "dept-1",
        created_by: "user-1",
        status: "approved",
        subtotal: "62800.00",
        vat: "147.50",
        total: "62947.50",
        currency: "AED",
        created_at: new Date().toISOString(),
        lines: [],
      };

      render(<PODetail po={mockPo} userRoles={["buyer"]} userId="user-1" />);

      const heading = screen.getByRole("heading", { level: 1 });
      expect(heading).toHaveTextContent("PO-2026-1C8000");
      expect(heading.textContent).not.toContain("Awarded Vendor");
    });
  });

  describe("3. Approval history on PR and PO detail", () => {
    it("renders two named approval steps with timestamps on PODetail", () => {
      const mockPo: PurchaseOrder = {
        id: "po-1C8000",
        number: "PO-2026-1C8000",
        vendor_id: "vendor-1",
        vendor_name: "Al Futtaim Engineering",
        department_id: "dept-facilities",
        created_by: "user-1",
        status: "approved",
        subtotal: "62800.00",
        vat: "147.50",
        total: "62947.50",
        currency: "AED",
        created_at: new Date().toISOString(),
        lines: [],
        approval_steps: [
          {
            id: "step-1",
            sequence: 1,
            tier: 2,
            status: "approved",
            approver_name: "Mariam Demo-Manager",
            department_name: "Facilities",
            decided_at: "2026-11-20T10:30:00Z",
            comment: "Approved within Facilities budget",
          },
          {
            id: "step-2",
            sequence: 2,
            tier: 3,
            status: "approved",
            approver_name: "Khalid Demo-Manager",
            department_name: "Projects",
            decided_at: "2026-11-20T14:15:00Z",
            comment: "Tier 3 secondary approval granted",
          },
        ],
      };

      render(<PODetail po={mockPo} userRoles={["buyer"]} userId="user-1" />);

      expect(screen.getByTestId("approval-history-section")).toBeInTheDocument();
      expect(screen.getByText("Mariam Demo-Manager")).toBeInTheDocument();
      expect(screen.getByText("Khalid Demo-Manager")).toBeInTheDocument();
      expect(screen.getByText("Facilities")).toBeInTheDocument();
      expect(screen.getByText("Projects")).toBeInTheDocument();

      const step1 = screen.getByTestId("approval-step-1");
      expect(step1).toHaveTextContent("Mariam Demo-Manager");
      expect(step1).toHaveTextContent("Approved within Facilities budget");

      const step2 = screen.getByTestId("approval-step-2");
      expect(step2).toHaveTextContent("Khalid Demo-Manager");
      expect(step2).toHaveTextContent("Tier 3 secondary approval granted");
    });

    it("omits approval history section when record has no steps", () => {
      const mockPo: PurchaseOrder = {
        id: "po-draft",
        number: "PO-2026-DRAFT1",
        vendor_id: "vendor-1",
        department_id: "dept-1",
        created_by: "user-1",
        status: "draft",
        subtotal: "1000.00",
        vat: "50.00",
        total: "1050.00",
        currency: "AED",
        created_at: new Date().toISOString(),
        lines: [],
        approval_steps: [],
      };

      render(<PODetail po={mockPo} userRoles={["buyer"]} userId="user-1" />);

      expect(screen.queryByTestId("approval-history-section")).toBeNull();
    });

    it("renders approval steps on PRDetail", async () => {
      const mockPr: PurchaseRequest = {
        id: "pr-427C5B",
        number: "PR-2026-427C5B",
        title: "Facilities Fit-out Package",
        department_id: "dept-facilities",
        requester_id: "user-1",
        status: "approved",
        currency: "AED",
        total_aed: "62800.00",
        created_at: new Date().toISOString(),
        lines: [],
        approval_steps: [
          {
            id: "pr-step-1",
            sequence: 1,
            tier: 2,
            status: "approved",
            approver_name: "Mariam Demo-Manager",
            department_name: "Facilities",
            decided_at: "2026-11-20T10:00:00Z",
          },
          {
            id: "pr-step-2",
            sequence: 2,
            tier: 3,
            status: "approved",
            approver_name: "Khalid Demo-Manager",
            department_name: "Projects",
            decided_at: "2026-11-20T11:00:00Z",
          },
        ],
      };

      vi.spyOn(global, "fetch").mockImplementation(async () => ({
        ok: true,
        status: 200,
        json: async () => [],
      } as unknown as Response));

      await act(async () => {
        render(<PRDetail pr={mockPr} userRoles={["buyer"]} userId="user-1" />);
      });

      expect(screen.getByTestId("approval-history-section")).toBeInTheDocument();
      expect(screen.getByText("Mariam Demo-Manager")).toBeInTheDocument();
      expect(screen.getByText("Khalid Demo-Manager")).toBeInTheDocument();
    });
  });

  describe("4. Match invoice dropdown filtering", () => {
    it("excludes suspicious and unconfirmed invoices and includes confirmed ones", async () => {
      const confirmedInv: DocumentSummary = {
        id: "inv-5510",
        doc_type: "invoice",
        status: "confirmed",
        pages: 2,
        size_bytes: 4096,
        created_at: new Date().toISOString(),
        duplicate_of: null,
        suspicious: false,
        vendor_name: "Gulf Line IT Trading",
        document_number: "INV-5510",
      };

      const suspiciousInv: DocumentSummary = {
        id: "inv-7001",
        doc_type: "invoice",
        status: "needs_review",
        pages: 1,
        size_bytes: 2048,
        created_at: new Date().toISOString(),
        duplicate_of: null,
        suspicious: true,
        vendor_name: "Apex Office Solutions",
        document_number: "INV-7001",
      };

      const unconfirmedInv: DocumentSummary = {
        id: "inv-8888",
        doc_type: "invoice",
        status: "ready",
        pages: 1,
        size_bytes: 1024,
        created_at: new Date().toISOString(),
        duplicate_of: null,
        suspicious: false,
        vendor_name: "Tech Solutions",
        document_number: "INV-8888",
      };

      vi.spyOn(global, "fetch").mockImplementation(async (url) => {
        const u = String(url);
        if (u.includes("/api/v1/me")) {
          return {
            ok: true,
            status: 200,
            json: async () => ({ roles: ["buyer"] }),
          } as unknown as Response;
        }
        if (u.includes("/api/v1/documents")) {
          // Verify fetch URL contains confirmed and suspicious=false
          expect(u).toContain("status=confirmed");
          expect(u).toContain("suspicious=false");
          return {
            ok: true,
            status: 200,
            json: async () => [confirmedInv, suspiciousInv, unconfirmedInv],
          } as unknown as Response;
        }
        return {
          ok: true,
          status: 200,
          json: async () => [],
        } as unknown as Response;
      });

      await act(async () => {
        render(<MatchesPage />);
      });

      // Confirmed invoice should be in the select dropdown
      expect(screen.getByRole("option", { name: "Gulf Line IT Trading · INV-5510" })).toBeInTheDocument();

      // Suspicious and unconfirmed invoices must NOT appear
      expect(screen.queryByRole("option", { name: /INV-7001/ })).toBeNull();
      expect(screen.queryByRole("option", { name: /INV-8888/ })).toBeNull();
      // Dropdown option text should NOT contain raw UUID suffix
      expect(screen.queryByRole("option", { name: /inv-5510/ })).toBeNull();
    });
  });
});
