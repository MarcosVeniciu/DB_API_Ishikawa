"""002_add_producers

Revision ID: 002_add_producers
Revises: 001_initial_consultants
Create Date: 2026-10-06 16:10:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "002_add_producers"
down_revision: Union[str, None] = "001_initial_consultants"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "producers",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("email", postgresql.CITEXT(), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("nome", sa.String(length=255), nullable=False),
        sa.Column("id_fazenda", sa.String(length=100), nullable=True),
        sa.Column(
            "dados",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("consultant_id", sa.UUID(), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["consultant_id"],
            ["consultants.id"],
            name=op.f("fk_producers_consultant_id_consultants"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_producers")),
        sa.UniqueConstraint("email", name=op.f("uq_producers_email")),
    )
    op.create_index(op.f("ix_producers_email"), "producers", ["email"], unique=True)
    op.create_index(op.f("ix_producers_consultant_id"), "producers", ["consultant_id"], unique=False)
    op.create_index(
        "ix_producers_lower_nome",
        "producers",
        [sa.text("lower(nome)")],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_producers_lower_nome", table_name="producers")
    op.drop_index(op.f("ix_producers_consultant_id"), table_name="producers")
    op.drop_index(op.f("ix_producers_email"), table_name="producers")
    op.drop_table("producers")
