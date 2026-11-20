import { describe, it, expect, vi } from "vitest";
import React from "react";
import { render, screen, fireEvent, act } from "@testing-library/react";
import { PRForm } from "@/components/flow/PRForm";

// Mock next/navigation
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    back: vi.fn(),
  }),
}));

describe("PRForm Component", () => {
  it("calculates line totals and overall request amount correctly in AED", async () => {
    await act(async () => {
      render(<PRForm userDepartmentId="dept-1" onToast={vi.fn()} />);
    });

    const qtyInput = screen.getByLabelText("Quantity for line 1");
    const priceInput = screen.getByLabelText("Est Unit Price for line 1");

    // Initially 1 * 0 = 0.00
    expect(screen.getByTestId("line-total-0")).toHaveTextContent("AED 0.00");
    expect(screen.getByTestId("pr-total-amount")).toHaveTextContent("AED 0.00");

    // Change Qty to 5 and price to 200
    await act(async () => {
      fireEvent.change(qtyInput, { target: { value: "5" } });
      fireEvent.change(priceInput, { target: { value: "200" } });
    });

    expect(screen.getByTestId("line-total-0")).toHaveTextContent("AED 1,000.00");
    expect(screen.getByTestId("pr-total-amount")).toHaveTextContent("AED 1,000.00");
  });

  it("validates required title before submission", async () => {
    const toastMock = vi.fn();
    await act(async () => {
      render(<PRForm userDepartmentId="dept-1" onToast={toastMock} />);
    });

    const form = screen.getByTestId("pr-form");
    await act(async () => {
      fireEvent.submit(form);
    });

    // Submitting without title displays error
    expect(screen.getByText("Request title is required.")).toBeInTheDocument();
  });
});
