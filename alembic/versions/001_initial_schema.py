"""Initial database schema.

Revision ID: 001
Revises: 
Create Date: 2026-01-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create run_status enum using raw SQL with IF NOT EXISTS
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'runstatus') THEN
                CREATE TYPE runstatus AS ENUM ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED');
            END IF;
        END
        $$;
    """)

    # Create discovery_runs table
    op.create_table(
        "discovery_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "status",
            postgresql.ENUM("PENDING", "RUNNING", "COMPLETED", "FAILED", name="runstatus", create_type=False),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("config", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("result_summary", postgresql.JSONB, nullable=True),
        sa.Column("error_message", sa.String, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_discovery_runs_created_at", "discovery_runs", ["created_at"])

    # Create molecules table
    op.create_table(
        "molecules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("discovery_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("smiles", sa.String(1000), nullable=False),
        sa.Column("is_valid", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("round_generated", sa.Integer, nullable=False, server_default="1"),
        sa.Column("mw", sa.Float, nullable=True),
        sa.Column("logp", sa.Float, nullable=True),
        sa.Column("hbd", sa.Integer, nullable=True),
        sa.Column("hba", sa.Integer, nullable=True),
        sa.Column("tpsa", sa.Float, nullable=True),
        sa.Column("rotb", sa.Integer, nullable=True),
        sa.Column("qed", sa.Float, nullable=True),
        sa.Column("violations", sa.Integer, nullable=True),
        sa.Column("passed_screening", sa.Boolean, nullable=True),
        sa.Column("score", sa.Float, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_molecules_run_id", "molecules", ["run_id"])
    op.create_index("ix_molecules_score", "molecules", ["score"])
    op.create_unique_constraint("uq_run_smiles", "molecules", ["run_id", "smiles"])

    # Create agent_traces table
    op.create_table(
        "agent_traces",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("discovery_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("agent_name", sa.String(100), nullable=False),
        sa.Column("action", sa.String(200), nullable=False),
        sa.Column("input_data", postgresql.JSONB, nullable=True),
        sa.Column("output_data", postgresql.JSONB, nullable=True),
        sa.Column("duration_ms", sa.Float, nullable=True),
    )
    op.create_index("ix_agent_traces_run_id", "agent_traces", ["run_id"])
    op.create_index("ix_agent_traces_timestamp", "agent_traces", ["timestamp"])


def downgrade() -> None:
    op.drop_table("agent_traces")
    op.drop_table("molecules")
    op.drop_table("discovery_runs")
    
    # Drop enum
    run_status_enum = postgresql.ENUM(
        "PENDING", "RUNNING", "COMPLETED", "FAILED",
        name="runstatus",
    )
    run_status_enum.drop(op.get_bind(), checkfirst=True)
