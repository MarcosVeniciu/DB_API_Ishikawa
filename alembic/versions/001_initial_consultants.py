"""001_initial_consultants

Revision ID: 001_initial_consultants
Revises: 
Create Date: 2026-10-06 15:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001_initial_consultants"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Habilita extensao CITEXT para emails case-insensitive
    op.execute("CREATE EXTENSION IF NOT EXISTS citext;")

    # 2. Cria tabela consultants
    op.create_table(
        "consultants",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("nome", sa.String(length=255), nullable=False),
        sa.Column("email", postgresql.CITEXT(), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_consultants")),
        sa.UniqueConstraint("email", name=op.f("uq_consultants_email")),
    )
    op.create_index(op.f("ix_consultants_email"), "consultants", ["email"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_consultants_email"), table_name="consultants")
    op.drop_table("consultants")
    op.execute("DROP EXTENSION IF EXISTS citext;")
