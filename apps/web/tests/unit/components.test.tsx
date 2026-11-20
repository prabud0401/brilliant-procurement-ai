import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ConfidenceBadge } from "@/components/ui/ConfidenceBadge";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";

describe("Shared UI Components", () => {
  describe("ConfidenceBadge", () => {
    it("renders high confidence (>= 0.80) with green styling", () => {
      render(<ConfidenceBadge confidence={0.92} />);
      const badge = screen.getByRole("status");
      expect(badge).toHaveTextContent("92%");
      expect(badge.className).toContain("bg-emerald-50");
      expect(badge.className).toContain("text-emerald-700");
    });

    it("renders medium confidence (0.60 - 0.79) as Needs Review with amber styling", () => {
      render(<ConfidenceBadge confidence={0.75} />);
      const badge = screen.getByRole("status");
      expect(badge).toHaveTextContent("75%");
      expect(badge).toHaveTextContent("Review");
      expect(badge.className).toContain("bg-amber-50");
      expect(badge.className).toContain("text-amber-800");

      const marker = screen.getByText("(Review)");
      expect(marker.className).not.toMatch(/opacity/);
      expect(marker.className).toContain("text-current");
      expect(marker.className).not.toContain("text-amber-700");
    });

    it("renders low confidence (< 0.60) as Needs Review with red styling", () => {
      render(<ConfidenceBadge confidence={0.45} />);
      const badge = screen.getByRole("status");
      expect(badge).toHaveTextContent("45%");
      expect(badge).toHaveTextContent("Review");
      expect(badge.className).toContain("bg-rose-50");
      expect(badge.className).toContain("text-rose-700");

      const marker = screen.getByText("(Review)");
      expect(marker.className).not.toMatch(/opacity/);
      expect(marker.className).toContain("text-current");
      expect(marker.className).not.toContain("text-amber-700");
    });

    it("ensures (Review) marker has no opacity and uses badge text color for medium and low confidence", () => {
      const { rerender } = render(<ConfidenceBadge confidence={0.70} />);
      let marker = screen.getByText("(Review)");
      expect(marker.className).not.toMatch(/opacity/);
      expect(marker.className).toContain("text-current");

      rerender(<ConfidenceBadge confidence={0.35} />);
      marker = screen.getByText("(Review)");
      expect(marker.className).not.toMatch(/opacity/);
      expect(marker.className).toContain("text-current");
    });

    it("renders dash for null or undefined confidence", () => {
      render(<ConfidenceBadge confidence={null} />);
      expect(screen.getByText("—")).toBeInTheDocument();
    });
  });

  describe("StatusBadge", () => {
    it("renders approved status with green color", () => {
      render(<StatusBadge status="approved" />);
      const badge = screen.getByRole("status");
      expect(badge).toHaveTextContent("Approved");
      expect(badge.className).toContain("text-emerald-700");
    });

    it("renders needs_review status with amber color", () => {
      render(<StatusBadge status="needs_review" />);
      const badge = screen.getByRole("status");
      expect(badge).toHaveTextContent("Needs Review");
      expect(badge.className).toContain("text-amber-800");
    });

    it("renders exception status with rose color", () => {
      render(<StatusBadge status="exception" />);
      const badge = screen.getByRole("status");
      expect(badge).toHaveTextContent("Exception");
      expect(badge.className).toContain("text-rose-700");
    });
  });

  describe("EmptyState", () => {
    it("renders title, description and calls action button", () => {
      const handleClick = vi.fn();
      render(
        <EmptyState
          title="No Documents Found"
          description="Upload your first quotation or invoice to get started."
          action={{ label: "Upload Document", onClick: handleClick }}
        />
      );

      expect(screen.getByText("No Documents Found")).toBeInTheDocument();
      expect(
        screen.getByText(
          "Upload your first quotation or invoice to get started."
        )
      ).toBeInTheDocument();

      const btn = screen.getByRole("button", { name: "Upload Document" });
      fireEvent.click(btn);
      expect(handleClick).toHaveBeenCalledTimes(1);
    });
  });

  describe("ErrorState", () => {
    it("renders RFC 9457 ProblemDetails with title, detail, code, request_id and retry", () => {
      const handleRetry = vi.fn();
      const problem = {
        title: "Validation Failed",
        detail: "VAT amount does not match 5% taxable total.",
        code: "VAT_MISMATCH",
        request_id: "req-xyz-999",
        status: 422,
      };

      render(
        <ErrorState
          error={problem}
          onRetry={handleRetry}
        />
      );

      expect(screen.getByText("Validation Failed")).toBeInTheDocument();
      expect(
        screen.getByText("VAT amount does not match 5% taxable total.")
      ).toBeInTheDocument();
      expect(screen.getByText("VAT_MISMATCH")).toBeInTheDocument();
      expect(screen.getByText("HTTP 422")).toBeInTheDocument();
      expect(screen.getByText("req-xyz-999")).toBeInTheDocument();

      const retryBtn = screen.getByRole("button", { name: /retry/i });
      fireEvent.click(retryBtn);
      expect(handleRetry).toHaveBeenCalledTimes(1);
    });
  });
});
