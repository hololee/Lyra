"""add worker servers and environment binding

Revision ID: f1a3b7c2d9e4
Revises: 8f2a1e4a9d3b
Create Date: 2026-02-17 22:55:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f1a3b7c2d9e4"
down_revision: Union[str, None] = "8f2a1e4a9d3b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("worker_servers"):
        op.create_table(
            "worker_servers",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("base_url", sa.Text(), nullable=False),
            sa.Column("api_token_encrypted", sa.Text(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("last_health_status", sa.String(length=32), nullable=False, server_default=sa.text("'unknown'")),
            sa.Column("last_health_checked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("name", name="uq_worker_servers_name"),
            sa.UniqueConstraint("base_url", name="uq_worker_servers_base_url"),
        )

    if inspector.has_table("environments"):
        columns = {col["name"] for col in inspector.get_columns("environments")}
        if "worker_server_id" not in columns:
            op.add_column("environments", sa.Column("worker_server_id", sa.UUID(), nullable=True))

        fk_names = {fk.get("name") for fk in inspector.get_foreign_keys("environments") if fk.get("name")}
        if "fk_environments_worker_server_id" not in fk_names:
            op.create_foreign_key(
                "fk_environments_worker_server_id",
                "environments",
                "worker_servers",
                ["worker_server_id"],
                ["id"],
                ondelete="SET NULL",
            )

        indexes = {idx.get("name") for idx in inspector.get_indexes("environments") if idx.get("name")}
        if "ix_environments_worker_server_id" not in indexes:
            op.create_index("ix_environments_worker_server_id", "environments", ["worker_server_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("environments"):
        fk_names = {fk.get("name") for fk in inspector.get_foreign_keys("environments") if fk.get("name")}
        if "fk_environments_worker_server_id" in fk_names:
            op.drop_constraint("fk_environments_worker_server_id", "environments", type_="foreignkey")

        indexes = {idx.get("name") for idx in inspector.get_indexes("environments") if idx.get("name")}
        if "ix_environments_worker_server_id" in indexes:
            op.drop_index("ix_environments_worker_server_id", table_name="environments")

        columns = {col["name"] for col in inspector.get_columns("environments")}
        if "worker_server_id" in columns:
            op.drop_column("environments", "worker_server_id")

    if inspector.has_table("worker_servers"):
        op.drop_table("worker_servers")
