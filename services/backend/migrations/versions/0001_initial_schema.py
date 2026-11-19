"""initial_schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-11-19 22:30:00.000000

"""

import os
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Extensions
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "vector"')

    # 2. Tables
    # departments
    op.create_table(
        "departments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    # users
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("external_oid", sa.String(length=255), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("department_id", sa.UUID(), nullable=True),
        sa.Column("approval_limit_aed", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("external_oid"),
    )

    # user_roles
    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "role IN ('requester', 'buyer', 'manager', 'admin')", name="ck_user_roles_role"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "role"),
    )

    # vendors
    op.create_table(
        "vendors",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("odoo_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("trn", sa.String(length=50), nullable=True),
        sa.Column("payment_terms_days", sa.Integer(), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("odoo_id"),
    )

    # products
    op.create_table(
        "products",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("odoo_id", sa.Integer(), nullable=True),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("uom", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
        sa.UniqueConstraint("odoo_id"),
    )

    # purchase_requests
    op.create_table(
        "purchase_requests",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("number", sa.String(length=100), nullable=False),
        sa.Column("requester_id", sa.UUID(), nullable=False),
        sa.Column("department_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("total_aed", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False),
        sa.Column("rule_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('draft', 'submitted', 'under_review', 'approved', 'rejected', 'cancelled')",
            name="ck_purchase_requests_status",
        ),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"]),
        sa.ForeignKeyConstraint(["requester_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("number"),
    )

    # pr_lines
    op.create_table(
        "pr_lines",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("pr_id", sa.UUID(), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("qty", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("uom", sa.String(length=50), nullable=False),
        sa.Column("est_unit_price", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["pr_id"], ["purchase_requests.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    # comparisons
    op.create_table(
        "comparisons",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("pr_id", sa.UUID(), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("weights", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("scores", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("recommended_vendor_id", sa.UUID(), nullable=True),
        sa.Column("chosen_vendor_id", sa.UUID(), nullable=True),
        sa.Column("override_reason", sa.Text(), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("llm_model", sa.String(length=100), nullable=True),
        sa.Column("prompt_version", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('draft', 'ready', 'decided', 'cancelled')",
            name="ck_comparisons_status",
        ),
        sa.ForeignKeyConstraint(["chosen_vendor_id"], ["vendors.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["pr_id"], ["purchase_requests.id"]),
        sa.ForeignKeyConstraint(["recommended_vendor_id"], ["vendors.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    # purchase_orders
    op.create_table(
        "purchase_orders",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("number", sa.String(length=100), nullable=False),
        sa.Column("comparison_id", sa.UUID(), nullable=True),
        sa.Column("vendor_id", sa.UUID(), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column("department_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("subtotal", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("vat", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("total", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False),
        sa.Column("rule_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("odoo_ref", sa.String(length=100), nullable=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('draft', 'submitted', 'approved', 'rejected', "
            "'sent_to_vendor', 'completed', 'cancelled')",
            name="ck_purchase_orders_status",
        ),
        sa.ForeignKeyConstraint(["comparison_id"], ["comparisons.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"]),
        sa.ForeignKeyConstraint(["vendor_id"], ["vendors.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
        sa.UniqueConstraint("number"),
    )

    # po_lines
    op.create_table(
        "po_lines",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("po_id", sa.UUID(), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("qty", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("uom", sa.String(length=50), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("vat_rate", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["po_id"], ["purchase_orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    # documents
    op.create_table(
        "documents",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column("department_id", sa.UUID(), nullable=True),
        sa.Column("pr_id", sa.UUID(), nullable=True),
        sa.Column("po_id", sa.UUID(), nullable=True),
        sa.Column("vendor_id", sa.UUID(), nullable=True),
        sa.Column("doc_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("file_sha256", sa.String(length=64), nullable=False),
        sa.Column("blob_path", sa.Text(), nullable=False),
        sa.Column("mime", sa.String(length=100), nullable=False),
        sa.Column("pages", sa.Integer(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("duplicate_of", sa.UUID(), nullable=True),
        sa.Column("duplicate_cleared_reason", sa.Text(), nullable=True),
        sa.Column("suspicious", sa.Boolean(), nullable=False),
        sa.Column("retain_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "doc_type IN ('quote', 'purchase_order', 'delivery_note', 'invoice', 'other')",
            name="ck_documents_doc_type",
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'processing', 'needs_review', 'confirmed', 'failed', 'rejected')",
            name="ck_documents_status",
        ),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["duplicate_of"], ["documents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["po_id"], ["purchase_orders.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["pr_id"], ["purchase_requests.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["vendor_id"], ["vendors.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("file_sha256"),
    )

    # comparison_quotes
    op.create_table(
        "comparison_quotes",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("comparison_id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("included", sa.Boolean(), nullable=False),
        sa.Column("include_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["comparison_id"], ["comparisons.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("comparison_id", "document_id", name="uq_comparison_quotes"),
    )

    # extractions
    op.create_table(
        "extractions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("di_model", sa.String(length=100), nullable=True),
        sa.Column("llm_model", sa.String(length=100), nullable=True),
        sa.Column("prompt_version", sa.String(length=50), nullable=True),
        sa.Column("raw_ocr_path", sa.Text(), nullable=True),
        sa.Column("tokens_in", sa.Integer(), nullable=True),
        sa.Column("tokens_out", sa.Integer(), nullable=True),
        sa.Column("est_cost", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'completed', 'failed')",
            name="ck_extractions_status",
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # extracted_fields
    op.create_table(
        "extracted_fields",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("extraction_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("value_raw", sa.Text(), nullable=True),
        sa.Column("value_norm", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("confidence", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("page", sa.Integer(), nullable=False),
        sa.Column("bbox", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("validation_msg", sa.Text(), nullable=True),
        sa.Column("confirmed_by", sa.UUID(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('ok', 'needs_review', 'validation_failed', 'confirmed', 'corrected')",
            name="ck_extracted_fields_status",
        ),
        sa.ForeignKeyConstraint(["confirmed_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["extraction_id"], ["extractions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # extracted_lines
    op.create_table(
        "extracted_lines",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("extraction_id", sa.UUID(), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("item_code", sa.String(length=100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("qty", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("uom", sa.String(length=50), nullable=True),
        sa.Column("unit_price", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("discount", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("vat_rate", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("line_total", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("confidence", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("page", sa.Integer(), nullable=False),
        sa.Column("bbox", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('ok', 'needs_review', 'validation_failed', 'confirmed', 'corrected')",
            name="ck_extracted_lines_status",
        ),
        sa.ForeignKeyConstraint(["extraction_id"], ["extractions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # comparison_pairings
    op.create_table(
        "comparison_pairings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("comparison_id", sa.UUID(), nullable=False),
        sa.Column("pr_line_id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("extracted_line_id", sa.UUID(), nullable=True),
        sa.Column("method", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "method IN ('code', 'similarity', 'manual')",
            name="ck_comparison_pairings_method",
        ),
        sa.ForeignKeyConstraint(["comparison_id"], ["comparisons.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["extracted_line_id"], ["extracted_lines.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["pr_line_id"], ["pr_lines.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # approval_steps
    op.create_table(
        "approval_steps",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("subject_type", sa.String(length=50), nullable=False),
        sa.Column("subject_id", sa.UUID(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("tier", sa.Integer(), nullable=False),
        sa.Column("assigned_to", sa.UUID(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("decided_by", sa.UUID(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("subject_type IN ('pr', 'po')", name="ck_approval_steps_subject_type"),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'skipped')",
            name="ck_approval_steps_status",
        ),
        sa.ForeignKeyConstraint(["assigned_to"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["decided_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_approval_steps_pending",
        "approval_steps",
        ["subject_type", "subject_id", "sequence"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )

    # matches
    op.create_table(
        "matches",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("invoice_document_id", sa.UUID(), nullable=False),
        sa.Column("po_id", sa.UUID(), nullable=False),
        sa.Column("run_by", sa.UUID(), nullable=False),
        sa.Column("tolerance_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("overall_status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "overall_status IN ('matched', 'within_tolerance', 'exception', 'pending')",
            name="ck_matches_overall_status",
        ),
        sa.ForeignKeyConstraint(["invoice_document_id"], ["documents.id"]),
        sa.ForeignKeyConstraint(["po_id"], ["purchase_orders.id"]),
        sa.ForeignKeyConstraint(["run_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # match_lines
    op.create_table(
        "match_lines",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("match_id", sa.UUID(), nullable=False),
        sa.Column("po_line_id", sa.UUID(), nullable=True),
        sa.Column("invoice_line_id", sa.UUID(), nullable=True),
        sa.Column("ordered_qty", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("received_qty", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("invoiced_qty", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("po_unit_price", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("inv_unit_price", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("variance_aed", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('matched', 'within_tolerance', 'exception')",
            name="ck_match_lines_status",
        ),
        sa.ForeignKeyConstraint(["invoice_line_id"], ["extracted_lines.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["match_id"], ["matches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["po_line_id"], ["po_lines.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    # match_exceptions
    op.create_table(
        "match_exceptions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("match_id", sa.UUID(), nullable=False),
        sa.Column("match_line_id", sa.UUID(), nullable=True),
        sa.Column("kind", sa.String(length=50), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("amount_impact_aed", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("assigned_to", sa.UUID(), nullable=True),
        sa.Column("resolved_by", sa.UUID(), nullable=True),
        sa.Column("resolution", sa.Text(), nullable=True),
        sa.Column("resolution_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind IN ('price_variance', 'qty_variance', 'missing_goods_receipt', "
            "'unmatched_item', 'vat_mismatch', 'other')",
            name="ck_match_exceptions_kind",
        ),
        sa.CheckConstraint(
            "status IN ('open', 'escalated', 'accepted', 'rejected', 'waiting')",
            name="ck_match_exceptions_status",
        ),
        sa.ForeignKeyConstraint(["assigned_to"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["match_id"], ["matches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["match_line_id"], ["match_lines.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["resolved_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    # chunks
    op.create_table(
        "chunks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("page", sa.Integer(), nullable=False),
        sa.Column("chunk_no", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("tsv", postgresql.TSVECTOR(), nullable=True),
        sa.Column("owner_id", sa.UUID(), nullable=True),
        sa.Column("department_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_chunks_embedding_hnsw ON chunks "
        "USING hnsw (embedding vector_cosine_ops)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_chunks_tsv_gin ON chunks USING gin (tsv)")

    # injection_flags
    op.create_table(
        "injection_flags",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("page", sa.Integer(), nullable=False),
        sa.Column("detector", sa.String(length=50), nullable=False),
        sa.Column("score", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("snippet_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("detector IN ('rule', 'model')", name="ck_injection_flags_detector"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # qa_logs
    op.create_table(
        "qa_logs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("question_redacted", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("citations", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("refused", sa.Boolean(), nullable=False),
        sa.Column("llm_model", sa.String(length=100), nullable=True),
        sa.Column("prompt_version", sa.String(length=50), nullable=True),
        sa.Column("tokens_in", sa.Integer(), nullable=True),
        sa.Column("tokens_out", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # settings
    op.create_table(
        "settings",
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("key"),
    )

    # outbox
    op.create_table(
        "outbox",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed')",
            name="ck_outbox_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )

    # jobs
    op.create_table(
        "jobs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("type", sa.String(length=100), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("run_after", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locked_by", sa.String(length=100), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed')",
            name="ck_jobs_status",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # audit_log
    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_id", sa.UUID(), nullable=True),
        sa.Column("actor_roles", sa.ARRAY(sa.String()), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("entity_id", sa.UUID(), nullable=True),
        sa.Column("before", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("ai_model", sa.String(length=100), nullable=True),
        sa.Column("prompt_version", sa.String(length=50), nullable=True),
        sa.Column("request_id", sa.String(length=100), nullable=True),
        sa.Column("prev_hash", sa.LargeBinary(), nullable=True),
        sa.Column("hash", sa.LargeBinary(), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    # 3. Triggers on audit_log
    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_audit_log_modification()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_log is append-only';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_audit_log_no_update_delete
        BEFORE UPDATE OR DELETE ON audit_log
        FOR EACH ROW
        EXECUTE FUNCTION prevent_audit_log_modification();
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_audit_log_no_truncate
        BEFORE TRUNCATE ON audit_log
        FOR EACH STATEMENT
        EXECUTE FUNCTION prevent_audit_log_modification();
        """
    )

    # 4. Roles and permissions
    app_env = os.environ.get("APP_ENV", "local").lower()
    app_db_password = os.environ.get("APP_DB_PASSWORD")
    if not app_db_password:
        try:
            from app.core.config import settings

            app_db_password = settings.APP_DB_PASSWORD
        except Exception:
            pass

    if not app_db_password:
        if app_env in ("local", "test"):
            app_db_password = "app_user"
        else:
            raise ValueError(
                "APP_DB_PASSWORD environment variable must be set for migrations "
                f"in '{app_env}' environment."
            )

    escaped_password = app_db_password.replace("'", "''")

    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'app_user') THEN
                CREATE ROLE app_user WITH LOGIN PASSWORD '{escaped_password}';
            ELSE
                ALTER ROLE app_user WITH PASSWORD '{escaped_password}';
            END IF;
        END
        $$;
        """
    )
    op.execute("GRANT USAGE ON SCHEMA public TO app_user;")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_user;")
    op.execute("REVOKE UPDATE, DELETE, TRUNCATE ON audit_log FROM app_user;")
    op.execute("GRANT SELECT, INSERT ON audit_log TO app_user;")
    op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_user;")
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_user;"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO app_user;"
    )


def downgrade() -> None:
    # 1. Triggers and functions
    op.execute("DROP TRIGGER IF EXISTS trg_audit_log_no_truncate ON audit_log")
    op.execute("DROP TRIGGER IF EXISTS trg_audit_log_no_update_delete ON audit_log")
    op.execute("DROP FUNCTION IF EXISTS prevent_audit_log_modification")

    # 2. Permissions
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'app_user') THEN
                REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM app_user;
                REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM app_user;
                REVOKE ALL PRIVILEGES ON SCHEMA public FROM app_user;
            END IF;
        END
        $$;
        """
    )

    # 3. Special indices
    op.execute("DROP INDEX IF EXISTS idx_chunks_tsv_gin")
    op.execute("DROP INDEX IF EXISTS idx_chunks_embedding_hnsw")
    op.drop_index("idx_approval_steps_pending", table_name="approval_steps")

    # 4. Tables in reverse order
    op.drop_table("audit_log")
    op.drop_table("jobs")
    op.drop_table("outbox")
    op.drop_table("settings")
    op.drop_table("qa_logs")
    op.drop_table("injection_flags")
    op.drop_table("chunks")
    op.drop_table("match_exceptions")
    op.drop_table("match_lines")
    op.drop_table("matches")
    op.drop_table("approval_steps")
    op.drop_table("comparison_pairings")
    op.drop_table("extracted_lines")
    op.drop_table("extracted_fields")
    op.drop_table("extractions")
    op.drop_table("comparison_quotes")
    op.drop_table("documents")
    op.drop_table("po_lines")
    op.drop_table("purchase_orders")
    op.drop_table("comparisons")
    op.drop_table("pr_lines")
    op.drop_table("purchase_requests")
    op.drop_table("products")
    op.drop_table("vendors")
    op.drop_table("user_roles")
    op.drop_table("users")
    op.drop_table("departments")
