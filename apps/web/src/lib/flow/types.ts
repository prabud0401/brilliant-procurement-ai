export interface PRLine {
  id: string;
  pr_id: string;
  product_id?: string | null;
  description: string;
  qty: number | string;
  uom: string;
  est_unit_price: number | string;
}

export interface PurchaseRequest {
  id: string;
  number: string;
  requester_id: string;
  department_id: string;
  title: string;
  status: "draft" | "submitted" | "approved" | "rejected" | string;
  total_aed: number | string;
  currency: string;
  submitted_at?: string | null;
  created_at: string;
  lines: PRLine[];
  current_approver_id?: string | null;
  current_approver?: string | null;
}

export interface PRCreateLinePayload {
  product_id?: string | null;
  description: string;
  qty: number;
  uom: string;
  est_unit_price: number;
}

export interface PRCreatePayload {
  title: string;
  department_id?: string | null;
  lines: PRCreateLinePayload[];
}

export interface ComparisonQuote {
  document_id: string;
  vendor_id?: string | null;
  vendor_name?: string | null;
  included: boolean;
  include_reason?: string | null;
  is_expired: boolean;
  currency: string;
  total_aed: number | string;
  lead_time_days?: number | null;
  payment_terms_days?: number | null;
}

export interface ComparisonPairing {
  id: string;
  pr_line_id: string;
  document_id: string;
  extracted_line_id?: string | null;
  method: string;
}

export interface Comparison {
  id: string;
  pr_id: string;
  created_by: string;
  status: "draft" | "scored" | "decided" | string;
  weights: {
    cost: number;
    delivery: number;
    payment: number;
    completeness: number;
  };
  scores?: {
    vendors?: Record<
      string,
      {
        cost_score?: number;
        delivery_score?: number;
        payment_score?: number;
        completeness_score?: number;
        final_score?: number;
        vendor_name?: string;
      }
    >;
    recommended_vendor_id?: string;
    is_close?: boolean;
    margin?: number;
    explanation?: string;
    [key: string]: unknown;
  } | null;
  recommended_vendor_id?: string | null;
  chosen_vendor_id?: string | null;
  override_reason?: string | null;
  explanation?: string | null;
  created_at: string;
  quotes: ComparisonQuote[];
  pairings: ComparisonPairing[];
  flags: string[];
}

export interface POLine {
  id: string;
  po_id: string;
  line_no: number;
  product_id?: string | null;
  description: string;
  qty: number | string;
  uom: string;
  unit_price: number | string;
  vat_rate: number | string;
  line_total: number | string;
}

export interface PurchaseOrder {
  id: string;
  number: string;
  comparison_id?: string | null;
  vendor_id: string;
  vendor_name?: string;
  department_id: string;
  created_by: string;
  status: "draft" | "submitted" | "approved" | "rejected" | "sent_to_vendor" | string;
  subtotal: number | string;
  vat: number | string;
  total: number | string;
  currency: string;
  odoo_ref?: string | null;
  idempotency_key?: string | null;
  created_at: string;
  lines: POLine[];
  current_approver_id?: string | null;
  current_approver?: string | null;
}

export interface InboxItem {
  step_id: string;
  subject_type: "pr" | "po" | string;
  subject_id: string;
  subject_number: string;
  title: string;
  total_aed: number | string;
  requester_id: string;
  requester_name: string;
  department_id: string;
  department_name?: string | null;
  tier: number;
  sequence: number;
  created_at: string;
}

export interface EarlierDecision {
  step_id: string;
  sequence: number;
  tier: number;
  assigned_to?: string | null;
  decided_by?: string | null;
  decided_by_name?: string | null;
  status: string;
  comment?: string | null;
  decided_at?: string | null;
}

export interface ApprovalBundle {
  step_id: string;
  subject_type: "pr" | "po" | string;
  subject_id: string;
  sequence: number;
  tier: number;
  step_status: string;
  assigned_to?: string | null;
  subject: {
    id: string;
    number: string;
    title?: string;
    total_aed?: number | string;
    total?: number | string;
    subtotal?: number | string;
    vat?: number | string;
    requester_id?: string;
    created_by?: string;
    created_at?: string;
    requester_name?: string;
    department_id?: string;
    department_name?: string;
    status: string;
    lines?: Array<{
      id?: string;
      line_no?: number;
      description: string;
      qty: number | string;
      uom: string;
      unit_price?: number | string;
      est_unit_price?: number | string;
      line_total?: number | string;
    }>;
  };
  earlier_decisions: EarlierDecision[];
  comparison?: {
    id: string;
    recommended_vendor_id?: string;
    chosen_vendor_id?: string;
    override_reason?: string;
    explanation?: string;
    weights?: Record<string, number>;
    scores?: Record<string, unknown>;
    quotes?: ComparisonQuote[];
  } | null;
  match?: unknown;
}

export interface MatchLine {
  id?: string;
  line_no: number;
  description: string;
  ordered_qty: number | string;
  received_qty: number | string;
  invoiced_qty: number | string;
  po_unit_price: number | string;
  invoice_unit_price: number | string;
  variance_aed: number | string;
  status: "matched" | "within_tolerance" | "exception" | string;
}

export interface MatchException {
  id: string;
  match_id: string;
  match_line_id?: string | null;
  kind: string;
  reason: string;
  amount_impact_aed: number | string;
  status: "open" | "escalated" | "accepted" | "rejected" | string;
  assigned_to?: string | null;
  resolved_by?: string | null;
  resolution?: string | null;
  resolution_reason?: string | null;
  created_at: string;
}

export interface MatchResult {
  id: string;
  invoice_document_id: string;
  po_id?: string | null;
  overall_status: "matched" | "within_tolerance" | "exception" | "incomplete" | string;
  missing_document?: string | null;
  lines: MatchLine[];
  exceptions: MatchException[];
  tolerances_snapshot: Record<string, unknown>;
  created_at: string;
}
