"""003_add_diagnostic_results

Revision ID: 003_add_diagnostic_results
Revises: 002_add_producers
Create Date: 2026-10-07 12:45:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "003_add_diagnostic_results"
down_revision: Union[str, None] = "002_add_producers"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "diagnostic_results",
        sa.Column("producer_id", sa.UUID(), nullable=False),
        sa.Column(
            "input_data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "diagnostico",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "simulacao",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["producer_id"],
            ["producers.id"],
            name=op.f("fk_diagnostic_results_producer_id_producers"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("producer_id", name=op.f("pk_diagnostic_results")),
    )


def downgrade() -> None:
    op.drop_table("diagnostic_results")
