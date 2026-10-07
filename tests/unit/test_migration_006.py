"""
Testes unitários para a migração Alembic 006 de remoção de índices duplicados e hardening de RLS.
Ref: Supabase Linter hardening (0009_duplicate_index, 0008_rls_enabled_no_policy, 0013_rls_disabled_in_public).
"""

import importlib.util
from pathlib import Path
from unittest.mock import call, patch
import pytest


def get_migration_006_module():
    """Carrega dinamicamente o módulo da migration 006."""
    migration_path = (
        Path(__file__).resolve().parent.parent.parent
        / "alembic"
        / "versions"
        / "006_fix_dup_indexes_and_rls.py"
    )
    if not migration_path.exists():
        pytest.fail("Migration 006_fix_dup_indexes_and_rls.py must exist")

    spec = importlib.util.spec_from_file_location("migration_006", str(migration_path))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_migration_006_metadata():
    """Valida identificadores e integridade do encadeamento da migration 006."""
    # Arrange & Act
    mod = get_migration_006_module()

    # Assert - AAA
    assert mod.revision == "006_fix_dup_indexes_and_rls"
    assert len(mod.revision) <= 32, "Revision ID must fit in alembic_version.version_num VARCHAR(32)"
    assert mod.down_revision == "005_move_citext_to_extensions"
    assert hasattr(mod, "upgrade")
    assert hasattr(mod, "downgrade")


@patch("alembic.op.execute")
@patch("alembic.op.drop_index")
def test_migration_006_upgrade(mock_drop_index, mock_execute):
    """Valida que o upgrade remove índices duplicados e aplica políticas explícitas de deny RLS."""
    # Arrange
    mod = get_migration_006_module()

    # Act
    mod.upgrade()

    # Assert - AAA
    mock_drop_index.assert_has_calls(
        [
            call("ix_consultants_email", table_name="consultants", if_exists=True),
            call("ix_producers_email", table_name="producers", if_exists=True),
        ],
        any_order=False,
    )
    assert mock_drop_index.call_count == 2

    # Verifica que as 4 tabelas recebem RLS ENABLE, DROP POLICY e CREATE POLICY
    tables = ["consultants", "producers", "diagnostic_results", "alembic_version"]
    for table in tables:
        assert call(f"ALTER TABLE IF EXISTS {table} ENABLE ROW LEVEL SECURITY;") in mock_execute.call_args_list
        assert call(f'DROP POLICY IF EXISTS "deny_all_anon_authenticated" ON {table};') in mock_execute.call_args_list
        assert call(f'CREATE POLICY "deny_all_anon_authenticated" ON {table} FOR ALL USING (false);') in mock_execute.call_args_list


@patch("alembic.op.execute")
@patch("alembic.op.create_index")
def test_migration_006_downgrade(mock_create_index, mock_execute):
    """Valida que o downgrade recria índices duplicados e remove as políticas RLS."""
    # Arrange
    mod = get_migration_006_module()

    # Act
    mod.downgrade()

    # Assert - AAA
    mock_create_index.assert_has_calls(
        [
            call("ix_producers_email", "producers", ["email"], unique=True),
            call("ix_consultants_email", "consultants", ["email"], unique=True),
        ],
        any_order=False,
    )
    assert mock_create_index.call_count == 2

    tables = ["consultants", "producers", "diagnostic_results", "alembic_version"]
    for table in tables:
        assert call(f'DROP POLICY IF EXISTS "deny_all_anon_authenticated" ON {table};') in mock_execute.call_args_list

    assert call("ALTER TABLE IF EXISTS alembic_version DISABLE ROW LEVEL SECURITY;") in mock_execute.call_args_list
