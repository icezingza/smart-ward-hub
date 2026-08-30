"""add forensic package signatures

Revision ID: 8c9d0e1f2a33
Revises: 7b8c9d0e1f22
Create Date: 2026-08-31 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8c9d0e1f2a33"
down_revision: Union[str, None] = "7b8c9d0e1f22"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("forensic_packages", sa.Column("signature_algorithm", sa.String(), nullable=True))
    op.add_column("forensic_packages", sa.Column("signature_b64", sa.String(), nullable=True))
    op.add_column("forensic_packages", sa.Column("signing_key_fingerprint", sa.String(), nullable=True))
    op.add_column(
        "forensic_packages",
        sa.Column("signature_status", sa.String(), nullable=False, server_default="UNSIGNED"),
    )
    op.add_column("forensic_packages", sa.Column("signed_at", sa.DateTime(), nullable=True))
    op.create_index(
        "ix_forensic_packages_signing_key_fingerprint",
        "forensic_packages",
        ["signing_key_fingerprint"],
        unique=False,
    )
    op.create_index(
        "ix_forensic_packages_signature_status",
        "forensic_packages",
        ["signature_status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_forensic_packages_signature_status", table_name="forensic_packages")
    op.drop_index("ix_forensic_packages_signing_key_fingerprint", table_name="forensic_packages")
    op.drop_column("forensic_packages", "signed_at")
    op.drop_column("forensic_packages", "signature_status")
    op.drop_column("forensic_packages", "signing_key_fingerprint")
    op.drop_column("forensic_packages", "signature_b64")
    op.drop_column("forensic_packages", "signature_algorithm")
