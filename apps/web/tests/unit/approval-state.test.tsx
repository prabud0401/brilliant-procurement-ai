import { describe, it, expect, vi } from "vitest";
import React from "react";
import { render, screen, fireEvent, act } from "@testing-library/react";
import { ApprovalDetail } from "@/components/flow/ApprovalDetail";
import type { ApprovalBundle } from "@/lib/flow/types";

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    back: vi.fn(),
    refresh: vi.fn(),
  }),
}));

const mockBaseBundle: ApprovalBundle = {
  step_id: "step-101",
  subject_type: "pr",
  subject_id: "pr-101",
  tier: 1,
  sequence: 1,
  step_status: "pending",
  assigned_to: "manager-1",
  subject: {
    id: "pr-101",
    number: "PR-2026-0001",
    status: "pending",
    title: "IT Laptops Equipment",
    requester_id: "user-requester",
    requester_name: "Tariq Mansoor",
    department_name: "Information Technology",
    total_aed: "15000.00",
    created_at: "2026-02-15T10:00:00Z",
    lines: [
      {
        id: "line-1",
        description: "ThinkPad P16 Workstation",
        qty: 3,
        uom: "unit",
        est_unit_price: "5000.00",
      },
    ],
  },
  earlier_decisions: [],
};

describe("ApprovalDetail - Decision State & Governance", () => {
  it("enforces Segregation of Duties (US-23): blocks creator from approving own commitment", async () => {
    // Current user is the requester
    const bundleWithCreator = {
      ...mockBaseBundle,
      subject: {
        ...mockBaseBundle.subject,
        requester_id: "current-user-123",
      },
    };

    await act(async () => {
      render(
        <ApprovalDetail
          bundle={bundleWithCreator}
          currentUserId="current-user-123"
          userRoles={["manager"]}
          userLimit={50000}
        />
      );
    });

    // SoD banner is shown
    expect(screen.getByTestId("sod-warning-banner")).toBeInTheDocument();
    expect(
      screen.getByText(/Segregation of Duties Enforced/i)
    ).toBeInTheDocument();

    // Decision buttons must NOT be rendered
    expect(screen.queryByTestId("approve-btn")).not.toBeInTheDocument();
    expect(screen.queryByTestId("reject-btn")).not.toBeInTheDocument();
  });

  it("blocks approval when commitment amount exceeds manager financial delegation limit", async () => {
    // Limit is 10,000 AED but commitment is 15,000 AED
    await act(async () => {
      render(
        <ApprovalDetail
          bundle={mockBaseBundle}
          currentUserId="manager-1"
          userRoles={["manager"]}
          userLimit={10000}
        />
      );
    });

    // Limit warning banner is shown
    expect(screen.getByTestId("limit-warning-banner")).toBeInTheDocument();
    expect(
      screen.getByText(/Approval Limit Exceeded/i)
    ).toBeInTheDocument();

    // Decision buttons must NOT be rendered
    expect(screen.queryByTestId("approve-btn")).not.toBeInTheDocument();
    expect(screen.queryByTestId("reject-btn")).not.toBeInTheDocument();
  });

  it("allows eligible manager to approve or reject, requiring a comment on rejection", async () => {
    await act(async () => {
      render(
        <ApprovalDetail
          bundle={mockBaseBundle}
          currentUserId="manager-1"
          userRoles={["manager"]}
          userLimit={50000}
        />
      );
    });

    // Both action buttons should be available
    const approveBtn = screen.getByTestId("approve-btn");
    const rejectBtn = screen.getByTestId("reject-btn");
    expect(approveBtn).toBeInTheDocument();
    expect(rejectBtn).toBeInTheDocument();

    // Click Reject to open rejection reason modal
    await act(async () => {
      fireEvent.click(rejectBtn);
    });

    // Modal title should be visible
    expect(
      screen.getByText(/Reject Commitment/i)
    ).toBeInTheDocument();

    // Confirm button must be disabled until comment is provided
    const confirmRejectBtn = screen.getByTestId("confirm-reject-btn");
    expect(confirmRejectBtn).toBeDisabled();

    // Enter comment
    const commentInput = screen.getByTestId("reject-comment-input");
    await act(async () => {
      fireEvent.change(commentInput, {
        target: { value: "Pricing exceeds departmental budget allocation for Q1." },
      });
    });

    // Confirm button is now enabled
    expect(confirmRejectBtn).toBeEnabled();
  });
});
