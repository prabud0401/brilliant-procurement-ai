import { describe, it, expect, vi } from "vitest";
import React from "react";
import { render, screen, fireEvent, act } from "@testing-library/react";
import { ComparisonView } from "@/components/flow/ComparisonView";
import type { Comparison } from "@/lib/flow/types";

// Mock next/navigation
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    refresh: vi.fn(),
  }),
}));

describe("ComparisonView Component", () => {
  const mockComparison: Comparison = {
    id: "comp-101",
    pr_id: "pr-101",
    created_by: "user-1",
    status: "scored",
    weights: {
      cost: 60,
      delivery: 20,
      payment: 10,
      completeness: 10,
    },
    scores: {
      vendors: {
        "vendor-1": {
          cost_score: 100,
          delivery_score: 80,
          payment_score: 90,
          completeness_score: 100,
          final_score: 94.0,
          vendor_name: "Gulf Line IT",
        },
        "vendor-2": {
          cost_score: 85,
          delivery_score: 100,
          payment_score: 70,
          completeness_score: 100,
          final_score: 88.0,
          vendor_name: "Falcon Supplies",
        },
      },
      recommended_vendor_id: "vendor-1",
      is_close: false,
      margin: 6.0,
      explanation: "Gulf Line IT is recommended based on the lowest overall cost.",
    },
    recommended_vendor_id: "vendor-1",
    chosen_vendor_id: null,
    override_reason: null,
    explanation: "Gulf Line IT is recommended based on the lowest overall cost.",
    created_at: new Date().toISOString(),
    quotes: [
      {
        document_id: "doc-1",
        vendor_id: "vendor-1",
        vendor_name: "Gulf Line IT",
        included: true,
        is_expired: false,
        currency: "AED",
        total_aed: 35000,
        lead_time_days: 5,
        payment_terms_days: 30,
      },
      {
        document_id: "doc-2",
        vendor_id: "vendor-2",
        vendor_name: "Falcon Supplies",
        included: true,
        is_expired: false,
        currency: "AED",
        total_aed: 38000,
        lead_time_days: 3,
        payment_terms_days: 30,
      },
    ],
    pairings: [],
    flags: [],
  };

  it("enforces weights must total exactly 100%", async () => {
    render(
      <ComparisonView
        comparison={mockComparison}
        userRoles={["buyer"]}
        onToast={vi.fn()}
      />
    );

    const costInput = screen.getByLabelText("Cost Weight (%)");
    const saveBtn = screen.getByTestId("save-weights-btn");

    expect(screen.getByTestId("weights-total")).toHaveTextContent("Total: 100%");
    expect(saveBtn).not.toBeDisabled();

    // Change cost to 70% -> Total becomes 110%
    fireEvent.change(costInput, { target: { value: "70" } });

    expect(screen.getByTestId("weights-total")).toHaveTextContent("Total: 110%");
    expect(saveBtn).toBeDisabled();
  });

  it("requires an override reason of at least 10 characters when choosing non-recommended vendor (US-10)", async () => {
    render(
      <ComparisonView
        comparison={mockComparison}
        userRoles={["buyer"]}
        onToast={vi.fn()}
      />
    );

    // Open vendor decision modal
    const decisionBtn = screen.getByTestId("vendor-decision-btn");
    fireEvent.click(decisionBtn);

    // Select vendor-2 (non-recommended, vendor-1 was recommended)
    const falconRadio = screen.getByDisplayValue("vendor-2");
    fireEvent.click(falconRadio);

    // Override reason textarea appears
    const reasonTextarea = screen.getByTestId("override-reason-input");
    expect(reasonTextarea).toBeInTheDocument();

    const confirmBtn = screen.getByTestId("confirm-decision-btn");
    expect(confirmBtn).toBeDisabled();

    // Type short reason (< 10 chars)
    fireEvent.change(reasonTextarea, { target: { value: "Short" } });
    expect(confirmBtn).toBeDisabled();

    // Type valid reason (>= 10 chars)
    fireEvent.change(reasonTextarea, {
      target: { value: "Immediate delivery urgently needed for project rollout" },
    });
    expect(confirmBtn).not.toBeDisabled();
  });

  it("shows '5 days' when lead_time_days is 5 and 'Not specified' when null", () => {
    const compWithLeadTimes: Comparison = {
      ...mockComparison,
      quotes: [
        {
          ...mockComparison.quotes![0],
          lead_time_days: 5,
        },
        {
          ...mockComparison.quotes![1],
          lead_time_days: null,
        },
      ],
    };

    render(
      <ComparisonView
        comparison={compWithLeadTimes}
        userRoles={["buyer"]}
        onToast={vi.fn()}
      />
    );

    expect(screen.getByText("5 days")).toBeInTheDocument();
    expect(screen.getByText("Not specified")).toBeInTheDocument();
  });

  it("renders customer-facing headings without US-xx identifiers", () => {
    render(
      <ComparisonView
        comparison={mockComparison}
        userRoles={["buyer"]}
        onToast={vi.fn()}
      />
    );

    // Representative heading checks
    expect(
      screen.getByRole("heading", { name: "Side-by-Side Comparison Matrix" })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Scoring Weights Configuration" })
    ).toBeInTheDocument();
    expect(screen.queryByText(/US-\d+/)).not.toBeInTheDocument();
  });
});
