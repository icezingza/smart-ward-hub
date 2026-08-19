"""add workflow session and NFC pointer controls

Revision ID: 4f1a2c7d8e90
Revises: 2c3d7e4f9a10
Create Date: 2026-08-19 14:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "4f1a2c7d8e90"
down_revision: Union[str, None] = "2c3d7e4f9a10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "nfc_pointers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("nfc_uid", sa.String(), nullable=False),
        sa.Column("device_id", sa.String(), nullable=False),
        sa.Column("key_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["device_id"], ["devices.device_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("nfc_uid"),
    )
    op.create_index("ix_nfc_pointers_nfc_uid", "nfc_pointers", ["nfc_uid"], unique=True)
    op.create_index("ix_nfc_pointers_device_id", "nfc_pointers", ["device_id"], unique=False)
    op.create_index("ix_nfc_pointers_key_id", "nfc_pointers", ["key_id"], unique=False)
    op.create_index("ix_nfc_pointers_status", "nfc_pointers", ["status"], unique=False)
    op.create_index("ix_nfc_pointers_created_at", "nfc_pointers", ["created_at"], unique=False)

    op.create_table(
        "ward_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("device_id", sa.String(), nullable=False),
        sa.Column("patient_token", sa.String(), nullable=False),
        sa.Column("bed_no", sa.String(), nullable=False),
        sa.Column("handover_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("started_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("reset_pending_at", sa.DateTime(), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["bed_no"], ["beds.bed_no"]),
        sa.ForeignKeyConstraint(["device_id"], ["devices.device_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id"),
    )
    op.create_index("ix_ward_sessions_session_id", "ward_sessions", ["session_id"], unique=True)
    op.create_index("ix_ward_sessions_device_id", "ward_sessions", ["device_id"], unique=False)
    op.create_index("ix_ward_sessions_patient_token", "ward_sessions", ["patient_token"], unique=False)
    op.create_index("ix_ward_sessions_bed_no", "ward_sessions", ["bed_no"], unique=False)
    op.create_index("ix_ward_sessions_handover_id", "ward_sessions", ["handover_id"], unique=False)
    op.create_index("ix_ward_sessions_status", "ward_sessions", ["status"], unique=False)
    op.create_index("ix_ward_sessions_started_at", "ward_sessions", ["started_at"], unique=False)
    op.create_index("ix_ward_sessions_created_at", "ward_sessions", ["created_at"], unique=False)

    op.create_table(
        "session_close_digests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("device_id", sa.String(), nullable=False),
        sa.Column("patient_token", sa.String(), nullable=False),
        sa.Column("bed_no", sa.String(), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("first_sequence", sa.Integer(), nullable=True),
        sa.Column("last_sequence", sa.Integer(), nullable=True),
        sa.Column("digest_hash", sa.String(), nullable=False),
        sa.Column("previous_digest_hash", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.device_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id"),
        sa.UniqueConstraint("digest_hash"),
    )
    op.create_index("ix_session_close_digests_session_id", "session_close_digests", ["session_id"], unique=True)
    op.create_index("ix_session_close_digests_device_id", "session_close_digests", ["device_id"], unique=False)
    op.create_index("ix_session_close_digests_patient_token", "session_close_digests", ["patient_token"], unique=False)
    op.create_index("ix_session_close_digests_bed_no", "session_close_digests", ["bed_no"], unique=False)
    op.create_index("ix_session_close_digests_digest_hash", "session_close_digests", ["digest_hash"], unique=True)
    op.create_index("ix_session_close_digests_created_at", "session_close_digests", ["created_at"], unique=False)

    op.add_column("alerts", sa.Column("session_id", sa.String(), nullable=True))
    op.create_index("ix_alerts_session_id", "alerts", ["session_id"], unique=False)
    op.add_column("forensic_packages", sa.Column("session_id", sa.String(), nullable=True))
    op.create_index("ix_forensic_packages_session_id", "forensic_packages", ["session_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_forensic_packages_session_id", table_name="forensic_packages")
    op.drop_column("forensic_packages", "session_id")
    op.drop_index("ix_alerts_session_id", table_name="alerts")
    op.drop_column("alerts", "session_id")
    op.drop_index("ix_session_close_digests_created_at", table_name="session_close_digests")
    op.drop_index("ix_session_close_digests_digest_hash", table_name="session_close_digests")
    op.drop_index("ix_session_close_digests_session_id", table_name="session_close_digests")
    op.drop_index("ix_session_close_digests_bed_no", table_name="session_close_digests")
    op.drop_index("ix_session_close_digests_patient_token", table_name="session_close_digests")
    op.drop_index("ix_session_close_digests_device_id", table_name="session_close_digests")
    op.drop_table("session_close_digests")
    op.drop_index("ix_ward_sessions_created_at", table_name="ward_sessions")
    op.drop_index("ix_ward_sessions_started_at", table_name="ward_sessions")
    op.drop_index("ix_ward_sessions_status", table_name="ward_sessions")
    op.drop_index("ix_ward_sessions_handover_id", table_name="ward_sessions")
    op.drop_index("ix_ward_sessions_bed_no", table_name="ward_sessions")
    op.drop_index("ix_ward_sessions_patient_token", table_name="ward_sessions")
    op.drop_index("ix_ward_sessions_device_id", table_name="ward_sessions")
    op.drop_index("ix_ward_sessions_session_id", table_name="ward_sessions")
    op.drop_table("ward_sessions")
    op.drop_index("ix_nfc_pointers_created_at", table_name="nfc_pointers")
    op.drop_index("ix_nfc_pointers_status", table_name="nfc_pointers")
    op.drop_index("ix_nfc_pointers_key_id", table_name="nfc_pointers")
    op.drop_index("ix_nfc_pointers_device_id", table_name="nfc_pointers")
    op.drop_index("ix_nfc_pointers_nfc_uid", table_name="nfc_pointers")
    op.drop_table("nfc_pointers")
