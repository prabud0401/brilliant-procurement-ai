import type { BoundingBox } from "./bbox";

export type DocumentType =
  | "quote"
  | "purchase_order"
  | "delivery_note"
  | "invoice"
  | "other";

export type DocumentStatus =
  | "queued"
  | "processing"
  | "needs_review"
  | "ready"
  | "confirmed"
  | "failed";

export interface DocumentSummary {
  id: string;
  doc_type: string;
  status: string;
  pages: number;
  size_bytes: number;
  created_at: string;
  duplicate_of: string | null;
  suspicious: boolean;
}

export interface DocumentResponse {
  id: string;
  owner_id: string;
  department_id: string | null;
  pr_id: string | null;
  po_id: string | null;
  vendor_id: string | null;
  doc_type: string;
  status: string;
  file_sha256: string;
  mime: string;
  pages: number;
  size_bytes: number;
  source: string;
  duplicate_of: string | null;
  duplicate_cleared_reason: string | null;
  suspicious: boolean;
  suspicious_ack_reason: string | null;
  created_at: string;
  updated_at: string;
}

export interface ExtractedField {
  id: string;
  name: string;
  value_raw: string | null;
  value_norm: Record<string, unknown> | null;
  confidence: number | null;
  page: number;
  bbox: BoundingBox | null;
  status: string; // 'extracted' | 'needs_review' | 'validation_failed' | 'confirmed' | 'corrected'
  validation_msg: string | null;
  confirmed_by: string | null;
  confirmed_at: string | null;
}

export interface ExtractedLine {
  id: string;
  line_no: number;
  item_code: string | null;
  description: string | null;
  qty: number | null;
  uom: string | null;
  unit_price: number | null;
  discount: number | null;
  vat_rate: number | null;
  line_total: number | null;
  confidence: number | null;
  page: number;
  bbox: BoundingBox | null;
  status: string;
}

export interface ExtractionResponse {
  id: string;
  document_id: string;
  version: number;
  di_model: string | null;
  llm_model: string | null;
  prompt_version: string | null;
  status: string;
  created_at: string;
  fields: ExtractedField[];
  lines: ExtractedLine[];
}

export interface HighlightTarget {
  id?: string;
  name?: string;
  page: number;
  bbox: BoundingBox | null;
  label?: string;
}
