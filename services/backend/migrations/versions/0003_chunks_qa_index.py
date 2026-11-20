"""chunks qa unique index and content_hash column

Revision ID: 0003_chunks_qa_index
Revises: 0002_suspicious_ack
Create Date: 2026-11-20 04:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_chunks_qa_index"
down_revision: Union[str, None] = "0002_suspicious_ack"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("chunks", sa.Column("content_hash", sa.String(length=64), nullable=True))
    op.create_unique_constraint(
        "uq_chunks_document_chunk_no", "chunks", ["document_id", "chunk_no"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_chunks_document_chunk_no", "chunks", type_="unique")
    op.drop_column("chunks", "content_hash")
