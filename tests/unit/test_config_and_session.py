"""
Testes unitários para configurações de pool e conexão SQLAlchemy (Lote 1).
Ref: Obsidian SDD [[sdd-db-api-seed-hardening]]
"""

from unittest.mock import patch
import pytest
from sqlalchemy.pool import QueuePool

from app.core.config import Settings
from app.db.session import build_engine_connect_args, create_db_engine


def test_settings_default_values():
    """Valida valores padrão das novas configurações de infraestrutura e seed."""
    # Arrange & Act
    cfg = Settings(
        DATABASE_URL="postgresql+psycopg://user:pass@localhost:5432/test_db",
        SERVICE_TOKEN="test-token",
    )

    # Assert
    assert cfg.SEED_ON_STARTUP is False
    assert cfg.SEED_DATA_PATH == "app/resources/test_data/farms.json"
    assert cfg.DB_POOL_SIZE == 5
    assert cfg.DB_MAX_OVERFLOW == 10
    assert cfg.DB_POOL_TIMEOUT == 30
    assert cfg.DB_PREPARE_THRESHOLD is None


def test_settings_custom_overrides():
    """Valida sobrescrita de configurações via injeção de parâmetros."""
    # Arrange & Act
    cfg = Settings(
        DATABASE_URL="postgresql+psycopg://user:pass@localhost:5432/test_db",
        SERVICE_TOKEN="test-token",
        SEED_ON_STARTUP=True,
        SEED_DATA_PATH="custom/path/farms.json",
        DB_POOL_SIZE=15,
        DB_MAX_OVERFLOW=20,
        DB_POOL_TIMEOUT=45,
        DB_PREPARE_THRESHOLD=0,
    )

    # Assert
    assert cfg.SEED_ON_STARTUP is True
    assert cfg.SEED_DATA_PATH == "custom/path/farms.json"
    assert cfg.DB_POOL_SIZE == 15
    assert cfg.DB_MAX_OVERFLOW == 20
    assert cfg.DB_POOL_TIMEOUT == 45
    assert cfg.DB_PREPARE_THRESHOLD == 0


def test_build_engine_connect_args_with_custom_threshold():
    """Valida connect_args quando DB_PREPARE_THRESHOLD é explicitamente configurado."""
    # Arrange
    cfg = Settings(
        DATABASE_URL="postgresql+psycopg://user:pass@localhost:5432/test_db",
        SERVICE_TOKEN="test-token",
        DB_PREPARE_THRESHOLD=5,
    )

    # Act
    args = build_engine_connect_args(cfg)

    # Assert
    assert args == {"prepare_threshold": 5}


def test_build_engine_connect_args_for_supabase_pooler():
    """Valida desativação de prepared statements server-side para Supavisor."""
    # Arrange
    cfg = Settings(
        DATABASE_URL="postgresql+psycopg://postgres.ref:pass@aws-0-sa-east-1.pooler.supabase.com:6543/postgres",
        SERVICE_TOKEN="test-token",
        DB_PREPARE_THRESHOLD=None,
    )

    # Act
    args = build_engine_connect_args(cfg)

    # Assert: Obrigatório None para modo transaction do Supavisor
    assert args == {"prepare_threshold": None}


def test_build_engine_connect_args_default_local():
    """Valida que em ambiente local sem Supabase e sem threshold definido o connect_args fica vazio."""
    # Arrange
    cfg = Settings(
        DATABASE_URL="postgresql+psycopg://user:pass@localhost:5432/test_db",
        SERVICE_TOKEN="test-token",
        ENVIRONMENT="development",
        DB_PREPARE_THRESHOLD=None,
    )

    # Act
    args = build_engine_connect_args(cfg)

    # Assert
    assert args == {}


@patch("app.db.session.create_engine")
def test_create_db_engine_passes_pool_and_connect_args(mock_create_engine):
    """Valida que a fábrica do engine repassa os parâmetros de pool e connect_args corretamente."""
    # Arrange
    cfg = Settings(
        DATABASE_URL="postgresql+psycopg://user:pass@localhost:5432/test_db",
        SERVICE_TOKEN="test-token",
        ENVIRONMENT="production",
        DB_POOL_SIZE=8,
        DB_MAX_OVERFLOW=12,
        DB_POOL_TIMEOUT=25,
        DB_PREPARE_THRESHOLD=None,
    )

    # Act
    create_db_engine(cfg)

    # Assert
    mock_create_engine.assert_called_once_with(
        cfg.DATABASE_URL,
        pool_pre_ping=True,
        pool_size=8,
        max_overflow=12,
        pool_timeout=25,
        connect_args={"prepare_threshold": None},
        echo=False,
    )
