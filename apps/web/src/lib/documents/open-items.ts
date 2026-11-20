import type { DocumentResponse, ExtractedField, ExtractedLine } from "./types";

export interface OpenItem {
  id: string;
  type: "field" | "line" | "suspicious" | "duplicate";
  name: string;
  title: string;
  message: string;
  status?: string;
}

export interface OpenItemsSummary {
  isOpen: boolean;
  count: number;
  items: OpenItem[];
}

/**
 * Calculates all open flags that block confirmation of a document per US-03, US-06, US-29.
 *
 * A document cannot be confirmed if:
 * 1. Any header field is 'needs_review' or 'validation_failed'
 * 2. Any line item is 'needs_review' or 'validation_failed'
 * 3. Document has suspicious content not yet acknowledged
 * 4. Document is a possible duplicate not yet cleared
 */
export function getOpenItems(
  doc: DocumentResponse | null | undefined,
  fields: ExtractedField[] = [],
  lines: ExtractedLine[] = []
): OpenItemsSummary {
  const items: OpenItem[] = [];

  if (!doc) {
    return { isOpen: false, count: 0, items: [] };
  }

  // 1. Suspicious content flag (US-29)
  if (doc.suspicious && !doc.suspicious_ack_reason) {
    items.push({
      id: "flag-suspicious",
      type: "suspicious",
      name: "suspicious",
      title: "Suspicious Content Flagged",
      message:
        "Document contains instructions to the AI that were ignored. Buyer acknowledgement with a reason is required before confirmation.",
    });
  }

  // 2. Duplicate flag (US-06)
  if (doc.duplicate_of && !doc.duplicate_cleared_reason) {
    items.push({
      id: "flag-duplicate",
      type: "duplicate",
      name: "duplicate_of",
      title: "Possible Duplicate Document",
      message: `Document is flagged as a duplicate of ${doc.duplicate_of}. Buyer must verify and record a reason to clear this flag.`,
    });
  }

  // 3. Header fields needing review or with validation errors
  for (const field of fields) {
    if (field.status === "needs_review" || field.status === "validation_failed") {
      const reason =
        field.validation_msg ||
        (field.confidence !== null && field.confidence < 0.8
          ? `Confidence score (${Math.round((field.confidence || 0) * 100)}%) is below 80% threshold`
          : "Field requires human verification");

      items.push({
        id: field.id,
        type: "field",
        name: field.name,
        title: `Field: ${formatFieldName(field.name)}`,
        message: reason,
        status: field.status,
      });
    }
  }

  // 4. Line items needing review or with validation errors
  for (const line of lines) {
    if (line.status === "needs_review" || line.status === "validation_failed") {
      items.push({
        id: line.id,
        type: "line",
        name: `line_${line.line_no}`,
        title: `Line Item #${line.line_no}: ${line.description || line.item_code || "Item"}`,
        message: "Line item values require review or confirmation",
        status: line.status,
      });
    }
  }

  return {
    isOpen: items.length > 0,
    count: items.length,
    items,
  };
}

export function formatFieldName(name: string): string {
  const labels: Record<string, string> = {
    vendor_name: "Vendor Name",
    vendor_trn: "Vendor TRN",
    document_number: "Document Number",
    document_date: "Document Date",
    po_number: "Purchase Order #",
    currency: "Currency",
    payment_terms: "Payment Terms",
    due_date: "Due Date",
    subtotal: "Subtotal",
    vat_amount: "VAT Amount",
    total: "Total Amount",
  };
  return labels[name] || name.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
