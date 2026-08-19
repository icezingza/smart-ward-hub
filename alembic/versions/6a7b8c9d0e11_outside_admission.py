"""outside admission availability

Revision ID: 6a7b8c9d0e11
Revises: 4f1a2c7d8e90
Create Date: 2026-08-19 15:10:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "6a7b8c9d0e11"
down_revision: Union[str, None] = "4f1a2c7d8e90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "beds",
        sa.Column("availability_state", sa.String(), nullable=False, server_default="AVAILABLE"),
    )
    op.add_column(
        "beds",
        sa.Column("availability_revision", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "beds",
        sa.Column("availability_updated_at", sa.DateTime(), nullable=False, server_default=sa.text("(CURRENT_TIMESTAMP)")),
    )
    op.create_index("ix_beds_availability_state", "beds", ["availability_state"], unique=False)
    op.create_index("ix_beds_availability_updated_at", "beds", ["availability_updated_at"], unique=False)

    op.create_table(
        "admission_preparations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("admission_id", sa.String(), nullable=False),
        sa.Column("bed_no", sa.String(), nullable=False),
        sa.Column("patient_token", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("idempotency_key", sa.String(), nullable=False),
        sa.Column("source_console_id", sa.String(), nullable=False),
        sa.Column("prepared_by", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("committed_session_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("(CURRENT_TIMESTAMP)")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("(CURRENT_TIMESTAMP)")),
        sa.ForeignKeyConstraint(["bed_no"], ["beds.bed_no"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("admission_id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index("ix_admission_preparations_admission_id", "admission_preparations", ["admission_id"], unique=True)
    op.create_index("ix_admission_preparations_bed_no", "admission_preparations", ["bed_no"], unique=False)
    op.create_index("ix_admission_preparations_patient_token", "admission_preparations", ["patient_token"], unique=False)
    op.create_index("ix_admission_preparations_status", "admission_preparations", ["status"], unique=False)
    op.create_index("ix_admission_preparations_idempotency_key", "admission_preparations", ["idempotency_key"], unique=True)
    op.create_index("ix_admission_preparations_source_console_id", "admission_preparations", ["source_console_id"], unique=False)
    op.create_index("ix_admission_preparations_prepared_by", "admission_preparations", ["prepared_by"], unique=False)
    op.create_index("ix_admission_preparations_expires_at", "admission_preparations", ["expires_at"], unique=False)
    op.create_index("ix_admission_preparations_committed_session_id", "admission_preparations", ["committed_session_id"], unique=False)
    op.create_index("ix_admission_preparations_created_at", "admission_preparations", ["created_at"], unique=False)
    op.create_index("ix_admission_preparations_updated_at", "admission_preparations", ["updated_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_admission_preparations_updated_at", table_name="admission_preparations")
    op.drop_index("ix_admission_preparations_created_at", table_name="admission_preparations")
    op.drop_index("ix_admission_preparations_committed_session_id", table_name="admission_preparations")
    op.drop_index("ix_admission_preparations_expires_at", table_name="admission_preparations")
    op.drop_index("ix_admission_preparations_prepared_by", table_name="admission_preparations")
    op.drop_index("ix_admission_preparations_source_console_id", table_name="admission_preparations")
    op.drop_index("ix_admission_preparations_idempotency_key", table_name="admission_preparations")
    op.drop_index("ix_admission_preparations_status", table_name="admission_preparations")
    op.drop_index("ix_admission_preparations_patient_token", table_name="admission_preparations")
    op.drop_index("ix_admission_preparations_bed_no", table_name="admission_preparations")
    op.drop_index("ix_admission_preparations_admission_id", table_name="admission_preparations")
    op.drop_table("admission_preparations")
    op.drop_index("ix_beds_availability_updated_at", table_name="beds")
    op.drop_index("ix_beds_availability_state", table_name="beds")
    op.drop_column("beds", "availability_updated_at")
    op.drop_column("beds", "availability_revision")
    op.drop_column("beds", "availability_state")
