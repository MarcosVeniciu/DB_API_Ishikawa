"""005_move_citext_to_extensions

Revision ID: 005_move_citext_to_extensions
Revises: 004_enable_rls
Create Date: 2026-10-07 17:05:00.000000

"""
from typing import Sequence, Union
from alembic import op

revision: str = "005_move_citext_to_extensions"
down_revision: Union[str, None] = "004_enable_rls"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Move extensão citext para schema extensions se o schema existir (ex: Supabase)
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'extensions') THEN
                ALTER EXTENSION citext SET SCHEMA extensions;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'citext') THEN
                ALTER EXTENSION citext SET SCHEMA public;
            END IF;
        END $$;
    """)
