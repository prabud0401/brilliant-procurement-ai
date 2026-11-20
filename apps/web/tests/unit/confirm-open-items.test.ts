import { describe, it, expect } from "vitest";
import { getOpenItems } from "@/lib/documents/open-items";
import type {
  DocumentResponse,
  ExtractedField,
  ExtractedLine,
} from "@/lib/documents/types";

describe("confirm-button state from open items (US-03, US-06, US-29)", () => {
  const baseDoc: DocumentResponse = {
    id: "doc-1",
    owner_id: "user-1",
    department_id: null,
    pr_id: null,
    po_id: null,
    vendor_id: "vendor-1",
    doc_type: "quote",
    status: "needs_review",
    file_sha256: "sha256",
    mime: "application/pdf",
    pages: 1,
    size_bytes: 5000,
    source: "upload",
    duplicate_of: null,
    duplicate_cleared_reason: null,
    suspicious: false,
    suspicious_ack_reason: null,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };

  const highConfField: ExtractedField = {
    id: "f-1",
    name: "vendor_name",
    value_raw: "Gulf Line IT Trading",
    value_norm: null,
    confidence: 0.95,
    page: 1,
    bbox: null,
    status: "extracted",
    validation_msg: null,
    confirmed_by: null,
    confirmed_at: null,
  };

  it("returns isOpen: false when all fields are valid and no security flags exist", () => {
    const summary = getOpenItems(baseDoc, [highConfField], []);
    expect(summary.isOpen).toBe(false);
    expect(summary.count).toBe(0);
    expect(summary.items).toHaveLength(0);
  });

  it("blocks confirmation (isOpen: true) when a field has status needs_review", () => {
    const flaggedField: ExtractedField = {
      ...highConfField,
      id: "f-2",
      name: "total",
      value_raw: "28875.00",
      confidence: 0.65, // Below 0.80 threshold
      status: "needs_review",
    };

    const summary = getOpenItems(baseDoc, [highConfField, flaggedField], []);
    expect(summary.isOpen).toBe(true);
    expect(summary.count).toBe(1);
    expect(summary.items[0].type).toBe("field");
    expect(summary.items[0].name).toBe("total");
    expect(summary.items[0].message).toContain("below 80% threshold");
  });

  it("blocks confirmation when a field has validation_failed message", () => {
    const validationFailedField: ExtractedField = {
      ...highConfField,
      id: "f-3",
      name: "subtotal",
      value_raw: "25000.00",
      confidence: 0.95,
      status: "validation_failed",
      validation_msg: "Validation failed: line items sum to AED 27,500.00",
    };

    const summary = getOpenItems(baseDoc, [validationFailedField], []);
    expect(summary.isOpen).toBe(true);
    expect(summary.count).toBe(1);
    expect(summary.items[0].message).toContain("line items sum to AED 27,500.00");
  });

  it("blocks confirmation when a line item has status needs_review", () => {
    const line: ExtractedLine = {
      id: "line-1",
      line_no: 1,
      item_code: "IT-LAP-14",
      description: "Laptop 14in",
      qty: 10,
      uom: "EA",
      unit_price: 1900,
      discount: 0,
      vat_rate: 5,
      line_total: 19000,
      confidence: 0.72,
      page: 1,
      bbox: null,
      status: "needs_review",
    };

    const summary = getOpenItems(baseDoc, [highConfField], [line]);
    expect(summary.isOpen).toBe(true);
    expect(summary.count).toBe(1);
    expect(summary.items[0].type).toBe("line");
    expect(summary.items[0].name).toBe("line_1");
  });

  it("blocks confirmation when document has unacknowledged suspicious flag (US-29)", () => {
    const suspiciousDoc: DocumentResponse = {
      ...baseDoc,
      suspicious: true,
      suspicious_ack_reason: null, // Not acknowledged yet
    };

    const summary = getOpenItems(suspiciousDoc, [highConfField], []);
    expect(summary.isOpen).toBe(true);
    expect(summary.count).toBe(1);
    expect(summary.items[0].type).toBe("suspicious");
    expect(summary.items[0].name).toBe("suspicious");
    expect(summary.items[0].message).toContain("Buyer acknowledgement with a reason is required");

    // Once acknowledged with a reason, open item is resolved
    const ackDoc: DocumentResponse = {
      ...suspiciousDoc,
      suspicious_ack_reason: "Verified physical paper invoice; ignored prompt injection instruction.",
    };

    const summaryAfterAck = getOpenItems(ackDoc, [highConfField], []);
    expect(summaryAfterAck.isOpen).toBe(false);
    expect(summaryAfterAck.count).toBe(0);
  });

  it("blocks confirmation when document has unacknowledged duplicate flag (US-06)", () => {
    const duplicateDoc: DocumentResponse = {
      ...baseDoc,
      duplicate_of: "doc-orig-999",
      duplicate_cleared_reason: null, // Not cleared yet
    };

    const summary = getOpenItems(duplicateDoc, [highConfField], []);
    expect(summary.isOpen).toBe(true);
    expect(summary.count).toBe(1);
    expect(summary.items[0].type).toBe("duplicate");
    expect(summary.items[0].message).toContain("doc-orig-999");

    // Once cleared with a reason, open item is resolved
    const clearedDoc: DocumentResponse = {
      ...duplicateDoc,
      duplicate_cleared_reason: "Verified revised quote from vendor with different terms.",
    };

    const summaryAfterClear = getOpenItems(clearedDoc, [highConfField], []);
    expect(summaryAfterClear.isOpen).toBe(false);
    expect(summaryAfterClear.count).toBe(0);
  });

  it("aggregates multiple open items correctly", () => {
    const complexDoc: DocumentResponse = {
      ...baseDoc,
      suspicious: true,
      duplicate_of: "doc-orig-1",
    };

    const badField: ExtractedField = {
      ...highConfField,
      status: "needs_review",
    };

    const badLine: ExtractedLine = {
      id: "l-1",
      line_no: 1,
      item_code: null,
      description: "Test",
      qty: 1,
      uom: "EA",
      unit_price: 100,
      discount: 0,
      vat_rate: 5,
      line_total: 100,
      confidence: 0.5,
      page: 1,
      bbox: null,
      status: "validation_failed",
    };

    const summary = getOpenItems(complexDoc, [badField], [badLine]);
    expect(summary.isOpen).toBe(true);
    expect(summary.count).toBe(4); // suspicious + duplicate + field + line
  });
});
