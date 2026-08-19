"""roaming commands

Revision ID: 7b8c9d0e1f22
Revises: 6a7b8c9d0e11
Create Date: 2026-08-19 15:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7b8c9d0e1f22"
down_revision: Union[str, None] = "6a7b8c9d0e11"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("alerts", sa.Column("acknowledged", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("alerts", sa.Column("acknowledged_by", sa.String(), nullable=True))
    op.add_column("alerts", sa.Column("acknowledged_at", sa.DateTime(), nullable=True))
    op.create_index("ix_alerts_acknowledged", "alerts", ["acknowledged"], unique=False)
    op.create_index("ix_alerts_acknowledged_by", "alerts", ["acknowledged_by"], unique=False)

    op.create_table(
        "roaming_commands",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("command_id", sa.String(), nullable=False),
        sa.Column("idempotency_key", sa.String(), nullable=False),
        sa.Column("command_type", sa.String(), nullable=False),
        sa.Column("actor_id", sa.String(), nullable=False),
        sa.Column("tablet_id", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=True),
        sa.Column("alert_id", sa.Integer(), nullable=True),
        sa.Column("admission_id", sa.String(), nullable=True),
        sa.Column("expected_revision", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("outcome_json", sa.String(), nullable=True),
        sa.Column("error_code", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("(CURRENT_TIMESTAMP)")),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("command_id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index("ix_roaming_commands_command_id", "roaming_commands", ["command_id"], unique=True)
    op.create_index("ix_roaming_commands_idempotency_key", "roaming_commands", ["idempotency_key"], unique=True)
    op.create_index("ix_roaming_commands_command_type", "roaming_commands", ["command_type"], unique=False)
    op.create_index("ix_roaming_commands_actor_id", "roaming_commands", ["actor_id"], unique=False)
    op.create_index("ix_roaming_commands_tablet_id", "roaming_commands", ["tablet_id"], unique=False)
    op.create_index("ix_roaming_commands_session_id", "roaming_commands", ["session_id"], unique=False)
    op.create_index("ix_roaming_commands_alert_id", "roaming_commands", ["alert_id"], unique=False)
    op.create_index("ix_roaming_commands_admission_id", "roaming_commands", ["admission_id"], unique=False)
    op.create_index("ix_roaming_commands_status", "roaming_commands", ["status"], unique=False)
    op.create_index("ix_roaming_commands_created_at", "roaming_commands", ["created_at"], unique=False)
    op.create_index("ix_roaming_commands_processed_at", "roaming_commands", ["processed_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_roaming_commands_processed_at", table_name="roaming_commands")
    op.drop_index("ix_roaming_commands_created_at", table_name="roaming_commands")
    op.drop_index("ix_roaming_commands_status", table_name="roaming_commands")
    op.drop_index("ix_roaming_commands_admission_id", table_name="roaming_commands")
    op.drop_index("ix_roaming_commands_alert_id", table_name="roaming_commands")
    op.drop_index("ix_roaming_commands_session_id", table_name="roaming_commands")
    op.drop_index("ix_roaming_commands_tablet_id", table_name="roaming_commands")
    op.drop_index("ix_roaming_commands_actor_id", table_name="roaming_commands")
    op.drop_index("ix_roaming_commands_command_type", table_name="roaming_commands")
    op.drop_index("ix_roaming_commands_idempotency_key", table_name="roaming_commands")
    op.drop_index("ix_roaming_commands_command_id", table_name="roaming_commands")
    op.drop_table("roaming_commands")
    op.drop_index("ix_alerts_acknowledged_by", table_name="alerts")
    op.drop_index("ix_alerts_acknowledged", table_name="alerts")
    op.drop_column("alerts", "acknowledged_at")
    op.drop_column("alerts", "acknowledged_by")
    op.drop_column("alerts", "acknowledged")
