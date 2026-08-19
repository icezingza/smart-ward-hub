"""add device trust credentials

Revision ID: 2c3d7e4f9a10
Revises: 9e9c98c2eb7f
Create Date: 2026-08-19 13:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2c3d7e4f9a10"
down_revision: Union[str, None] = "9e9c98c2eb7f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "device_credentials",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("device_id", sa.String(), nullable=False),
        sa.Column("key_id", sa.String(), nullable=False),
        sa.Column("algorithm", sa.String(), nullable=False),
        sa.Column("public_key_b64", sa.String(), nullable=False),
        sa.Column("certificate_fingerprint", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("issued_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.device_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key_id"),
    )
    op.create_index("ix_device_credentials_device_id", "device_credentials", ["device_id"], unique=False)
    op.create_index("ix_device_credentials_key_id", "device_credentials", ["key_id"], unique=True)
    op.create_index("ix_device_credentials_status", "device_credentials", ["status"], unique=False)
    op.create_index("ix_device_credentials_created_at", "device_credentials", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_device_credentials_created_at", table_name="device_credentials")
    op.drop_index("ix_device_credentials_status", table_name="device_credentials")
    op.drop_index("ix_device_credentials_key_id", table_name="device_credentials")
    op.drop_index("ix_device_credentials_device_id", table_name="device_credentials")
    op.drop_table("device_credentials")
