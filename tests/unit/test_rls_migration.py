"""
Testes unitários para a migração Alembic 004 de habilitação do Row Level Security (RLS) (Lote 2).
Ref: Obsidian SDD [[sdd-db-api-seed-hardening]]
"""

import importlib.util
from pathlib import Path
from unittest.mock import call, patch
import pytest


def get_migration_004_module():
    """Carrega dinamicamente o módulo da migration 004."""
    migration_path = (
        Path(__file__).resolve().parent.parent.parent
        / "alembic"
        / "versions"
        / "004_enable_rls.py"
    )
    if not migration_path.exists():
        pytest.fail("Migration 004_enable_rls.py must exist")

    spec = importlib.util.spec_from_file_location("migration_004", str(migration_path))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_migration_004_metadata():
    """Valida identificadores e integridade do encadeamento da migration 004."""
    # Arrange & Act
    mod = get_migration_004_module()

    # Assert
    assert mod.revision == "004_enable_rls"
    assert mod.down_revision == "003_add_diagnostic_results"
    assert hasattr(mod, "upgrade")
    assert hasattr(mod, "downgrade")


@patch("alembic.op.execute")
def test_migration_004_upgrade_enables_rls(mock_execute):
    """Valida que o upgrade ativa RLS nas 3 tabelas existentes (consultants, producers, diagnostic_results)."""
    # Arrange
    mod = get_migration_004_module()

    # Act
    mod.upgrade()

    # Assert - AAA
    expected_calls = [
        call("ALTER TABLE consultants ENABLE ROW LEVEL SECURITY;"),
        call("ALTER TABLE producers ENABLE ROW LEVEL SECURITY;"),
        call("ALTER TABLE diagnostic_results ENABLE ROW LEVEL SECURITY;"),
    ]
    mock_execute.assert_has_calls(expected_calls, any_order=False)
    assert mock_execute.call_count == 3


@patch("alembic.op.execute")
def test_migration_004_downgrade_disables_rls(mock_execute):
    """Valida que o downgrade desativa RLS nas 3 tabelas em ordem reversa."""
    # Arrange
    mod = get_migration_004_module()

    # Act
    mod.downgrade()

    # Assert - AAA
    expected_calls = [
        call("ALTER TABLE diagnostic_results DISABLE ROW LEVEL SECURITY;"),
        call("ALTER TABLE producers DISABLE ROW LEVEL SECURITY;"),
        call("ALTER TABLE consultants DISABLE ROW LEVEL SECURITY;"),
    ]
    mock_execute.assert_has_calls(expected_calls, any_order=False)
    assert mock_execute.call_count == 3
