"""add intake role to user_roles check constraint

Revision ID: 0004_add_intake_role
Revises: 0003_chunks_qa_index
Create Date: 2026-11-20 05:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

revision: str = "0004_add_intake_role"
down_revision: Union[str, None] = "0003_chunks_qa_index"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("ck_user_roles_role", "user_roles", type_="check")
    op.create_check_constraint(
        "ck_user_roles_role",
        "user_roles",
        "role IN ('requester', 'buyer', 'manager', 'admin', 'intake')",
    )


def downgrade() -> None:
    op.execute("DELETE FROM user_roles WHERE role = 'intake'")
    op.drop_constraint("ck_user_roles_role", "user_roles", type_="check")
    op.create_check_constraint(
        "ck_user_roles_role",
        "user_roles",
        "role IN ('requester', 'buyer', 'manager', 'admin')",
    )
