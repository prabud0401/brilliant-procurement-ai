import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import {
  MetricsClient,
  AdminMetricsResponse,
} from "@/app/(dashboard)/admin/metrics/MetricsClient";
import { ToastProvider } from "@/components/ui/Toast";

const mockMetrics: AdminMetricsResponse = {
  documents_processed: 42,
  total_fields: 420,
  fields_needing_review_count: 55,
  share_of_fields_needing_review: 0.131,
  correction_rate_per_field: [
    {
      field_name: "vat_amount",
      total_count: 30,
      corrected_count: 3,
      correction_rate: 0.1,
    },
    {
      field_name: "vendor_name",
      total_count: 30,
      corrected_count: 1,
      correction_rate: 0.033,
    },
  ],
  match_exception_rate: 0.05,
  total_matches: 20,
  exception_matches: 1,
  approval_cycle_time_seconds: 7200,
  approval_cycle_time_hours: 2.0,
  ai_today: {
    calls_today: 18,
    tokens_today: 45000,
    tokens_in_today: 35000,
    tokens_out_today: 10000,
    estimated_cost_aed: 0.065,
    daily_budget_aed: 50.0,
    budget_utilization_pct: 0.13,
  },
  qa_refusal_rate: 0.08,
  qa_total_questions: 25,
  qa_refused_questions: 2,
  spend_by_department: [
    {
      department_id: "dept-1",
      department_name: "Facilities",
      purchase_requests_count: 3,
      purchase_requests_total_aed: 7500.0,
      purchase_orders_count: 2,
      purchase_orders_total_aed: 6000.0,
      pending_approvals_count: 1,
    },
    {
      department_id: "dept-2",
      department_name: "IT",
      purchase_requests_count: 5,
      purchase_requests_total_aed: 24000.0,
      purchase_orders_count: 4,
      purchase_orders_total_aed: 22000.0,
      pending_approvals_count: 0,
    },
    {
      department_id: "dept-3",
      department_name: "Projects",
      purchase_requests_count: 2,
      purchase_requests_total_aed: 150000.0,
      purchase_orders_count: 1,
      purchase_orders_total_aed: 120000.0,
      pending_approvals_count: 2,
    },
    {
      department_id: "dept-4",
      department_name: "Finance",
      purchase_requests_count: 0,
      purchase_requests_total_aed: 0.0,
      purchase_orders_count: 0,
      purchase_orders_total_aed: 0.0,
      pending_approvals_count: 0,
    },
    {
      department_id: "dept-5",
      department_name: "HR",
      purchase_requests_count: 0,
      purchase_requests_total_aed: 0.0,
      purchase_orders_count: 0,
      purchase_orders_total_aed: 0.0,
      pending_approvals_count: 0,
    },
    {
      department_id: "dept-6",
      department_name: "Operations",
      purchase_requests_count: 1,
      purchase_requests_total_aed: 3500.0,
      purchase_orders_count: 1,
      purchase_orders_total_aed: 3500.0,
      pending_approvals_count: 0,
    },
  ],
};

describe("MetricsClient Component (NFR-OBS-03, NFR-OBS-05)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  const renderWithToast = (ui: React.ReactElement) => {
    return render(<ToastProvider>{ui}</ToastProvider>);
  };

  it("renders all core KPI cards accurately", () => {
    renderWithToast(<MetricsClient initialData={mockMetrics} />);

    // Documents processed
    expect(screen.getByText("Documents Processed")).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();

    // Fields needing review
    expect(screen.getByText("Fields Needing Review")).toBeInTheDocument();
    expect(screen.getByText("13.1%")).toBeInTheDocument();

    // Match exception rate
    expect(screen.getByText("Match Exception Rate")).toBeInTheDocument();
    expect(screen.getByText("5.0%")).toBeInTheDocument();

    // Approval cycle time
    expect(screen.getByText("Approval Cycle Time")).toBeInTheDocument();
    expect(screen.getByText("2 hrs")).toBeInTheDocument();

    // Q&A refusal rate
    expect(screen.getByText("Q&A Refusal Rate")).toBeInTheDocument();
    expect(screen.getByText("8.0%")).toBeInTheDocument();
  });

  it("renders AI Budget and token consumption section", () => {
    renderWithToast(<MetricsClient initialData={mockMetrics} />);

    expect(
      screen.getByText("AI Budget & Token Consumption Today")
    ).toBeInTheDocument();
    expect(screen.getByText(/AED 50.00/)).toBeInTheDocument();
    expect(screen.getByText("45,000")).toBeInTheDocument();
    expect(screen.getByText(/0.1% utilized/i)).toBeInTheDocument();
  });

  it("renders field correction rates breakdown table", () => {
    renderWithToast(<MetricsClient initialData={mockMetrics} />);

    expect(screen.getByText("vat_amount")).toBeInTheDocument();
    expect(screen.getByText("vendor_name")).toBeInTheDocument();
    expect(screen.getByText("10.0%")).toBeInTheDocument();
    expect(screen.getByText("3.3%")).toBeInTheDocument();
  });

  it("refresh button fetches updated metrics from API", async () => {
    const updatedMetrics: AdminMetricsResponse = {
      ...mockMetrics,
      documents_processed: 45,
    };

    vi.spyOn(global, "fetch").mockResolvedValueOnce({
      ok: true,
      json: async () => updatedMetrics,
    } as Response);

    renderWithToast(<MetricsClient initialData={mockMetrics} />);
    const refreshBtn = screen.getByRole("button", { name: /Refresh Metrics/i });
    fireEvent.click(refreshBtn);

    await waitFor(() => {
      expect(screen.getByText("45")).toBeInTheDocument();
    });
  });

  it("renders Spend by Department card and department rows", () => {
    renderWithToast(<MetricsClient initialData={mockMetrics} />);

    expect(screen.getByText("Spend by Department")).toBeInTheDocument();
    expect(screen.getByText("Facilities")).toBeInTheDocument();
    expect(screen.getByText("Finance")).toBeInTheDocument();
    expect(screen.getByText("HR")).toBeInTheDocument();
    expect(screen.getByText("IT")).toBeInTheDocument();
    expect(screen.getByText("Operations")).toBeInTheDocument();
    expect(screen.getByText("Projects")).toBeInTheDocument();

    // Verify values rendered
    expect(screen.getByText("AED 7,500.00")).toBeInTheDocument();
    expect(screen.getByText("AED 150,000.00")).toBeInTheDocument();
  });

  it("renders empty state when spend_by_department is empty or absent", () => {
    const emptyMetrics: AdminMetricsResponse = {
      ...mockMetrics,
      spend_by_department: [],
    };
    renderWithToast(<MetricsClient initialData={emptyMetrics} />);

    expect(screen.getByText("Spend by Department")).toBeInTheDocument();
    expect(
      screen.getByText("No department spend data available.")
    ).toBeInTheDocument();
  });
});
