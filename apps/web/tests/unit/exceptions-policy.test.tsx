import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import React from "react";
import { render, screen, act } from "@testing-library/react";
import { ExceptionQueue } from "@/components/flow/ExceptionQueue";
import type { MatchException } from "@/lib/flow/types";

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    back: vi.fn(),
    refresh: vi.fn(),
  }),
}));

const mockExceptions: MatchException[] = [
  {
    id: "exc-1",
    match_id: "match-001-abc",
    kind: "qty_variance",
    amount_impact_aed: "240.00",
    reason: "Invoiced qty 12 exceeds ordered qty 10",
    status: "open",
    created_at: "2026-02-15T12:00:00Z",
  },
  {
    id: "exc-2",
    match_id: "match-002-xyz",
    kind: "price_variance",
    amount_impact_aed: "750.00",
    reason: "Unit price AED 375 exceeds PO price AED 300",
    status: "open",
    created_at: "2026-02-15T12:10:00Z",
  },
  {
    id: "exc-3",
    match_id: "match-003-def",
    kind: "price_variance",
    amount_impact_aed: "120.00",
    reason: "Unit price AED 310 exceeds PO price AED 300 within threshold",
    status: "open",
    created_at: "2026-02-15T12:20:00Z",
  },
];

describe("ExceptionQueue - Buyer & Manager Policy Enforcement (US-15)", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((url: string) => {
        if (url.includes("/api/v1/exceptions")) {
          return Promise.resolve({
            ok: true,
            json: async () => mockExceptions,
          });
        }
        return Promise.reject(new Error("Unhandled route"));
      })
    );
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("enforces Buyer policy: blocks accepting over-billed qty and variance > AED 500", async () => {
    await act(async () => {
      render(<ExceptionQueue userRoles={["buyer"]} />);
    });

    // Check that 3 exceptions are loaded
    expect(await screen.findByText(/Invoiced qty 12 exceeds ordered qty 10/i)).toBeInTheDocument();
    expect(screen.getByText(/Unit price AED 375 exceeds PO price AED 300/i)).toBeInTheDocument();
    expect(screen.getByText(/Unit price AED 310 exceeds PO price AED 300 within threshold/i)).toBeInTheDocument();

    const acceptButtons = screen.getAllByTestId("buyer-accept-exception-btn");
    expect(acceptButtons).toHaveLength(3);

    // Exception 1: qty_variance -> disabled
    expect(acceptButtons[0]).toBeDisabled();
    expect(acceptButtons[0].getAttribute("title")).toContain("Over-billed quantity cannot be accepted");

    // Exception 2: price_variance with AED 750 (> 500) -> disabled
    expect(acceptButtons[1]).toBeDisabled();
    expect(acceptButtons[1].getAttribute("title")).toContain("exceeds Buyer AED 500 tolerance policy");

    // Exception 3: price_variance with AED 120 (<= 500) -> enabled
    expect(acceptButtons[2]).toBeEnabled();

    // All open exceptions have escalate button enabled for Buyer
    const escalateButtons = screen.getAllByTestId("buyer-escalate-exception-btn");
    expect(escalateButtons).toHaveLength(3);
    escalateButtons.forEach((btn) => expect(btn).toBeEnabled());
  });

  it("allows Manager to decide escalated exceptions", async () => {
    const escalatedExceptions: MatchException[] = [
      {
        id: "exc-escalated",
        match_id: "match-esc-999",
        kind: "qty_variance",
        amount_impact_aed: "1500.00",
        reason: "Invoiced qty 15 exceeds PO qty 10 (escalated by buyer)",
        status: "escalated",
        created_at: "2026-02-15T12:00:00Z",
      },
    ];

    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((url: string) => {
        if (url.includes("/api/v1/exceptions")) {
          return Promise.resolve({
            ok: true,
            json: async () => escalatedExceptions,
          });
        }
        return Promise.reject(new Error("Unhandled route"));
      })
    );

    await act(async () => {
      render(<ExceptionQueue userRoles={["manager"]} />);
    });

    expect(await screen.findByText(/Invoiced qty 15 exceeds PO qty 10/i)).toBeInTheDocument();

    // Manager accept & reject buttons are visible and active
    const managerAcceptBtn = screen.getByTestId("manager-accept-exception-btn");
    const managerRejectBtn = screen.getByTestId("manager-reject-exception-btn");

    expect(managerAcceptBtn).toBeInTheDocument();
    expect(managerAcceptBtn).toBeEnabled();
    expect(managerRejectBtn).toBeInTheDocument();
    expect(managerRejectBtn).toBeEnabled();
  });
});
