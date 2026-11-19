"""documents.suspicious_ack_reason

Revision ID: 0002_suspicious_ack
Revises: 0001_initial_schema
Create Date: 2026-11-20 04:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_suspicious_ack"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("suspicious_ack_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "suspicious_ack_reason")
