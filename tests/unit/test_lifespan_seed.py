"""
Testes unitários para o ciclo de vida (lifespan) da aplicação e integração do seed (Lote 4).
Ref: Obsidian SDD [[sdd-db-api-seed-hardening]]
"""

from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.main import app, lifespan


@pytest.mark.anyio
async def test_lifespan_triggers_seed_when_enabled():
    """Valida que o lifespan aciona o seed quando SEED_ON_STARTUP é verdadeiro."""
    # Arrange
    with patch("app.main.settings.SEED_ON_STARTUP", True):
        with patch("app.main.run_seed") as mock_run_seed:
            with patch("app.main.SessionLocal") as mock_session_local:
                mock_db = MagicMock()
                mock_session_local.return_value = mock_db

                # Act
                async with lifespan(app):
                    pass

                # Assert - AAA
                mock_run_seed.assert_called_once_with(mock_db)
                mock_db.close.assert_called_once()


@pytest.mark.anyio
async def test_lifespan_skips_seed_when_disabled():
    """Valida que o lifespan ignora a importação de seed quando SEED_ON_STARTUP é falso."""
    # Arrange
    with patch("app.main.settings.SEED_ON_STARTUP", False):
        with patch("app.main.run_seed") as mock_run_seed:
            # Act
            async with lifespan(app):
                pass

            # Assert - AAA
            mock_run_seed.assert_not_called()


def test_health_live_endpoint():
    """Valida que o endpoint /health/live responde HTTP 200 OK com status alive."""
    # Arrange
    client = TestClient(app)

    # Act
    response = client.get("/health/live")

    # Assert
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


from app.db.session import get_db


def test_health_ready_endpoint_connected():
    """Valida que /health/ready responde HTTP 200 OK quando o banco de dados está acessível."""
    # Arrange
    client = TestClient(app)
    mock_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        # Act
        response = client.get("/health/ready")

        # Assert
        assert response.status_code == 200
        assert response.json() == {"status": "ready", "database": "connected"}
        assert mock_db.execute.called
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_health_ready_endpoint_disconnected():
    """Valida que /health/ready responde HTTP 503 quando há falha de conexão com o banco."""
    # Arrange
    client = TestClient(app)
    mock_db = MagicMock()
    mock_db.execute.side_effect = Exception("Conexão recusada pelo PostgreSQL")
    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        # Act
        response = client.get("/health/ready")

        # Assert
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unready"
        assert data["database"] == "disconnected"
        assert "Conexão recusada" in data["detail"]
    finally:
        app.dependency_overrides.pop(get_db, None)
