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
});
