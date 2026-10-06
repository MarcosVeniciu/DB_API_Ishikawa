from datetime import datetime, timezone
from unittest.mock import MagicMock
import uuid
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.errors import (
    ConcurrencyConflictError,
    DuplicateEmailError,
    InvalidCredentialsError,
    NotFoundError,
)
from app.main import app
from app.schemas.auth import AuthVerifyResponse
from app.schemas.consultant import ConsultantDTO
from app.services.consultant_service import ConsultantService


@pytest.fixture
def mock_service():
    return MagicMock(spec=ConsultantService)


@pytest.fixture
def client(mock_service):
    from app.api.v1.consultants import get_consultant_service
    from app.api.v1.auth import get_auth_service

    app.dependency_overrides[get_consultant_service] = lambda: mock_service
    app.dependency_overrides[get_auth_service] = lambda: mock_service
    yield TestClient(app)
    app.dependency_overrides.clear()


AUTH_HEADERS = {"X-Service-Token": settings.SERVICE_TOKEN}


def test_health_live(client):
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "alive"


def test_missing_service_token_returns_401(client):
    response = client.get("/v1/consultants")
    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")
    data = response.json()
    assert data["type"] == "unauthorized"


def test_create_consultant_endpoint_success(client, mock_service):
    cid = uuid.uuid4()
    mock_service.create_consultant.return_value = ConsultantDTO(
        id=cid,
        nome="Consultor API",
        email="api@educampo.com.br",
        version=1,
        created_at=datetime.now(timezone.utc),
    )

    payload = {
        "id": str(cid),
        "nome": "Consultor API",
        "email": "api@educampo.com.br",
        "password": "SenhaSegura123",
    }
    response = client.post("/v1/consultants", json=payload, headers=AUTH_HEADERS)

    assert response.status_code == 201
    data = response.json()
    assert data["id"] == str(cid)
    assert data["nome"] == "Consultor API"
    assert "password" not in data
    assert "hashed_password" not in data


def test_create_consultant_endpoint_duplicate_email(client, mock_service):
    mock_service.create_consultant.side_effect = DuplicateEmailError("E-mail ja cadastrado")

    payload = {
        "nome": "Consultor Duplicado",
        "email": "duplicado@educampo.com.br",
        "password": "SenhaSegura123",
    }
    response = client.post("/v1/consultants", json=payload, headers=AUTH_HEADERS)

    assert response.status_code == 409
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["type"] == "conflict-email"


def test_list_consultants_endpoint(client, mock_service):
    cid = uuid.uuid4()
    mock_service.list_consultants.return_value = (
        [
            ConsultantDTO(
                id=cid,
                nome="Consultor Listado",
                email="listado@educampo.com.br",
                version=1,
                created_at=datetime.now(timezone.utc),
            )
        ],
        1,
    )

    response = client.get("/v1/consultants?limit=10&offset=0", headers=AUTH_HEADERS)

    assert response.status_code == 200
    assert response.headers["X-Total-Count"] == "1"
    items = response.json()
    assert len(items) == 1
    assert items[0]["id"] == str(cid)


def test_list_consultants_limit_exceeded(client):
    response = client.get("/v1/consultants?limit=201", headers=AUTH_HEADERS)
    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")


def test_get_consultant_by_id_endpoint_not_found(client, mock_service):
    cid = uuid.uuid4()
    mock_service.get_consultant_by_id.side_effect = NotFoundError("Nao encontrado")

    response = client.get(f"/v1/consultants/{cid}", headers=AUTH_HEADERS)

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["type"] == "not-found"


def test_update_consultant_endpoint_optimistic_lock_412(client, mock_service):
    cid = uuid.uuid4()
    mock_service.update_consultant.side_effect = ConcurrencyConflictError("Versao antiga")

    headers = {**AUTH_HEADERS, "If-Match": "1"}
    response = client.put(
        f"/v1/consultants/{cid}",
        json={"nome": "Novo Nome"},
        headers=headers,
    )

    assert response.status_code == 412
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["type"] == "version-mismatch"


def test_auth_verify_endpoint_success(client, mock_service):
    cid = uuid.uuid4()
    mock_service.verify_credentials.return_value = AuthVerifyResponse(
        id=cid,
        role="consultant",
    )

    payload = {
        "email": "login@educampo.com.br",
        "password": "SenhaValida123",
        "role": "consultant",
    }
    response = client.post("/v1/auth/verify", json=payload, headers=AUTH_HEADERS)

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(cid)
    assert data["role"] == "consultant"


def test_auth_verify_endpoint_invalid_credentials(client, mock_service):
    mock_service.verify_credentials.side_effect = InvalidCredentialsError("Credenciais invalidas")

    payload = {
        "email": "login@educampo.com.br",
        "password": "SenhaInvalida",
        "role": "consultant",
    }
    response = client.post("/v1/auth/verify", json=payload, headers=AUTH_HEADERS)

    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["type"] == "invalid-credentials"
