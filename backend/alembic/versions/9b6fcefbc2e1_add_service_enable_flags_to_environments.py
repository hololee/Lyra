"""add service enable flags to environments

Revision ID: 9b6fcefbc2e1
Revises: da94cb80a42a
Create Date: 2026-02-15 14:52:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9b6fcefbc2e1"
down_revision: Union[str, None] = "da94cb80a42a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "environments",
        sa.Column("enable_jupyter", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.add_column(
        "environments",
        sa.Column("enable_code_server", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )


def downgrade() -> None:
    op.drop_column("environments", "enable_code_server")
    op.drop_column("environments", "enable_jupyter")
