"""004_enable_rls

Revision ID: 004_enable_rls
Revises: 003_add_diagnostic_results
Create Date: 2026-10-07 14:15:00.000000

"""
from typing import Sequence, Union
from alembic import op

revision: str = "004_enable_rls"
down_revision: Union[str, None] = "003_add_diagnostic_results"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Ativação de Row Level Security (RLS) nas 3 tabelas (D19)
    op.execute("ALTER TABLE consultants ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE producers ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE diagnostic_results ENABLE ROW LEVEL SECURITY;")


def downgrade() -> None:
    op.execute("ALTER TABLE diagnostic_results DISABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE producers DISABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE consultants DISABLE ROW LEVEL SECURITY;")
