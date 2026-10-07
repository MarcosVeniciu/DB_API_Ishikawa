"""006_fix_dup_indexes_and_rls

Revision ID: 006_fix_dup_indexes_and_rls
Revises: 005_move_citext_to_extensions
Create Date: 2026-10-07 17:15:00.000000

"""
from typing import Sequence, Union
from alembic import op

revision: str = "006_fix_dup_indexes_and_rls"
down_revision: Union[str, None] = "005_move_citext_to_extensions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Remove índices redundantes duplicados (mantendo as constraints UNIQUE uq_*)
    op.drop_index("ix_consultants_email", table_name="consultants", if_exists=True)
    op.drop_index("ix_producers_email", table_name="producers", if_exists=True)

    # 2. Hardening RLS (Decisão D19):
    # Assegura RLS habilitado e adiciona política restritiva (default deny)
    # para bloquear PostgREST/anon/authenticated e zerar avisos de linter do Supabase.
    tables = ["consultants", "producers", "diagnostic_results", "alembic_version"]
    for table in tables:
        op.execute(f"ALTER TABLE IF EXISTS {table} ENABLE ROW LEVEL SECURITY;")
        op.execute(f'DROP POLICY IF EXISTS "deny_all_anon_authenticated" ON {table};')
        op.execute(
            f'CREATE POLICY "deny_all_anon_authenticated" ON {table} FOR ALL USING (false);'
        )


def downgrade() -> None:
    # 1. Remove políticas restritivas
    tables = ["consultants", "producers", "diagnostic_results", "alembic_version"]
    for table in tables:
        op.execute(f'DROP POLICY IF EXISTS "deny_all_anon_authenticated" ON {table};')

    # Desativa RLS em alembic_version caso revertido
    op.execute("ALTER TABLE IF EXISTS alembic_version DISABLE ROW LEVEL SECURITY;")

    # 2. Recria os índices redundantes
    op.create_index(
        "ix_producers_email",
        "producers",
        ["email"],
        unique=True,
    )
    op.create_index(
        "ix_consultants_email",
        "consultants",
        ["email"],
        unique=True,
    )
