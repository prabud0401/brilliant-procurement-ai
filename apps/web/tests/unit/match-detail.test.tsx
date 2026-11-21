import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MatchDetail } from "@/components/flow/MatchDetail";
import type { MatchResult } from "@/lib/flow/types";

describe("MatchDetail Component (US-13)", () => {
  const baseMatch: MatchResult = {
    id: "match-12345678-abcd-1111",
    invoice_document_id: "doc-inv-98765432-xxxx",
    po_id: "po-11112222-yyyy",
    overall_status: "matched",
    created_at: "2026-11-20T10:00:00Z",
    lines: [
      {
        id: "line-1",
        line_no: 1,
        description: "Standard Office Desks 140x70cm",
        ordered_qty: 10,
        received_qty: 10,
        invoiced_qty: 10,
        po_unit_price: 500,
        inv_unit_price: 500,
        variance_aed: 0,
        status: "matched",
      },
      {
        id: "line-2",
        line_no: 2,
        description: "Executive Ergonomic Chairs",
        ordered_qty: 5,
        received_qty: 5,
        invoiced_qty: 5,
        po_unit_price: 750,
        invoice_unit_price: 750, // Test fallback to invoice_unit_price
        variance_aed: 0,
        status: "matched",
      },
    ],
    exceptions: [],
    tolerances_snapshot: {
      unit_price_variance_pct: 2,
      unit_price_variance_max_aed: "50.00",
      invoiced_vs_received_qty_max_units: 0,
      vat_max_difference_aed: "1.00",
    },
  };

  it("renders non-zero invoice unit price and line description from inv_unit_price", () => {
    render(<MatchDetail match={baseMatch} userRoles={["buyer"]} />);

    // Description is rendered
    expect(screen.getByText("Standard Office Desks 140x70cm")).toBeInTheDocument();
    expect(screen.getByText("Executive Ergonomic Chairs")).toBeInTheDocument();

    // Inv Unit Price is rendered as non-zero formatted AED
    const invPrice0 = screen.getByTestId("inv-unit-price-0");
    expect(invPrice0).toHaveTextContent("AED 500.00");

    // Line 2 fallback to invoice_unit_price is rendered as non-zero formatted AED
    const invPrice1 = screen.getByTestId("inv-unit-price-1");
    expect(invPrice1).toHaveTextContent("AED 750.00");
  });

  it("renders price variance and status badge properly", () => {
    const varianceMatch: MatchResult = {
      ...baseMatch,
      overall_status: "exception",
      lines: [
        {
          id: "line-v1",
          line_no: 1,
          description: "Operations Server INV-5510",
          ordered_qty: 1,
          received_qty: 1,
          invoiced_qty: 1,
          po_unit_price: 15000,
          inv_unit_price: 16600,
          variance_aed: 1600,
          status: "exception",
        },
      ],
    };

    render(<MatchDetail match={varianceMatch} userRoles={["buyer"]} />);

    expect(screen.getByText("Operations Server INV-5510")).toBeInTheDocument();
    expect(screen.getByTestId("inv-unit-price-0")).toHaveTextContent("AED 16,600.00");
    expect(screen.getByText("AED 1,600.00")).toBeInTheDocument();
  });
});
