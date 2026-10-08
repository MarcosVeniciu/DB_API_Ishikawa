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
from app.schemas.producer import ProducerDTO
from app.services.producer_service import ProducerService


@pytest.fixture
def mock_producer_service():
    return MagicMock(spec=ProducerService)


@pytest.fixture
def client(mock_producer_service):
    from app.api.v1.auth import get_auth_service
    from app.api.v1.producers import get_producer_service

    app.dependency_overrides[get_producer_service] = lambda: mock_producer_service
    app.dependency_overrides[get_auth_service] = lambda: mock_producer_service
    yield TestClient(app)
    app.dependency_overrides.clear()


AUTH_HEADERS = {"X-Service-Token": settings.SERVICE_TOKEN}


def test_missing_service_token_producers_returns_401(client):
    response = client.get("/v1/producers")
    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["type"] == "unauthorized"


def test_create_producer_endpoint_success(client, mock_producer_service):
    pid = uuid.uuid4()
    now = datetime.now(timezone.utc)
    mock_producer_service.create_producer.return_value = ProducerDTO(
        id=pid,
        nome="Fazenda Modelo",
        email="modelo@educampo.com.br",
        id_fazenda="FAZ-01",
        dados={"hectares": 120},
        consultant_id=None,
        version=1,
        created_at=now,
        updated_at=now,
    )

    payload = {
        "id": str(pid),
        "nome": "Fazenda Modelo",
        "email": "modelo@educampo.com.br",
        "password": "SenhaSegura123",
        "id_fazenda": "FAZ-01",
        "dados": {"hectares": 120},
    }
    response = client.post("/v1/producers", json=payload, headers=AUTH_HEADERS)

    assert response.status_code == 201
    data = response.json()
    assert data["id"] == str(pid)
    assert data["nome"] == "Fazenda Modelo"
    assert "password" not in data
    assert "hashed_password" not in data


def test_create_producer_endpoint_duplicate_email(client, mock_producer_service):
    mock_producer_service.create_producer.side_effect = DuplicateEmailError("E-mail duplicado")

    payload = {
        "nome": "Fazenda Duplicada",
        "email": "duplicado@educampo.com.br",
        "password": "SenhaSegura123",
    }
    response = client.post("/v1/producers", json=payload, headers=AUTH_HEADERS)

    assert response.status_code == 409
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["type"] == "conflict-email"


def test_list_producers_endpoint(client, mock_producer_service):
    pid = uuid.uuid4()
    now = datetime.now(timezone.utc)
    mock_producer_service.list_producers.return_value = (
        [
            ProducerDTO(
                id=pid,
                nome="Fazenda Listada",
                email="listada@educampo.com.br",
                version=1,
                created_at=now,
                updated_at=now,
            )
        ],
        1,
    )

    response = client.get("/v1/producers?limit=10&offset=0", headers=AUTH_HEADERS)

    assert response.status_code == 200
    assert response.headers["X-Total-Count"] == "1"
    items = response.json()
    assert len(items) == 1
    assert items[0]["id"] == str(pid)


def test_list_producers_limit_exceeded(client):
    response = client.get("/v1/producers?limit=201", headers=AUTH_HEADERS)
    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")


def test_get_producer_by_id_endpoint_found(client, mock_producer_service):
    pid = uuid.uuid4()
    now = datetime.now(timezone.utc)
    mock_producer_service.get_producer_by_id.return_value = ProducerDTO(
        id=pid,
        nome="Fazenda Unica",
        email="unica@educampo.com.br",
        version=1,
        created_at=now,
        updated_at=now,
    )

    response = client.get(f"/v1/producers/{pid}", headers=AUTH_HEADERS)

    assert response.status_code == 200
    assert response.json()["id"] == str(pid)


def test_get_producer_by_id_endpoint_not_found(client, mock_producer_service):
    pid = uuid.uuid4()
    mock_producer_service.get_producer_by_id.side_effect = NotFoundError("Nao encontrado")

    response = client.get(f"/v1/producers/{pid}", headers=AUTH_HEADERS)

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["type"] == "not-found"


def test_update_producer_endpoint_success(client, mock_producer_service):
    pid = uuid.uuid4()
    now = datetime.now(timezone.utc)
    mock_producer_service.update_producer.return_value = ProducerDTO(
        id=pid,
        nome="Fazenda Atualizada",
        email="atualizada@educampo.com.br",
        version=2,
        created_at=now,
        updated_at=now,
    )

    headers = {**AUTH_HEADERS, "If-Match": "1"}
    response = client.put(
        f"/v1/producers/{pid}",
        json={"nome": "Fazenda Atualizada"},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["version"] == 2


def test_update_producer_endpoint_optimistic_lock_412(client, mock_producer_service):
    pid = uuid.uuid4()
    mock_producer_service.update_producer.side_effect = ConcurrencyConflictError("Versao antiga")

    headers = {**AUTH_HEADERS, "If-Match": "1"}
    response = client.put(
        f"/v1/producers/{pid}",
        json={"nome": "Tentativa"},
        headers=headers,
    )

    assert response.status_code == 412
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["type"] == "version-mismatch"


def test_delete_producer_endpoint_success(client, mock_producer_service):
    pid = uuid.uuid4()
    mock_producer_service.delete_producer.return_value = None

    response = client.delete(f"/v1/producers/{pid}", headers=AUTH_HEADERS)

    assert response.status_code == 204
    assert not response.content


def test_delete_producer_endpoint_not_found(client, mock_producer_service):
    pid = uuid.uuid4()
    mock_producer_service.delete_producer.side_effect = NotFoundError("Nao encontrado")

    response = client.delete(f"/v1/producers/{pid}", headers=AUTH_HEADERS)

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["type"] == "not-found"


def test_auth_verify_endpoint_producer_success(client, mock_producer_service):
    pid = uuid.uuid4()
    mock_producer_service.verify_credentials.return_value = AuthVerifyResponse(
        id=pid,
        role="producer",
    )

    payload = {
        "email": "produtor@educampo.com.br",
        "password": "SenhaCerta123",
        "role": "producer",
    }
    response = client.post("/v1/auth/verify", json=payload, headers=AUTH_HEADERS)

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(pid)
    assert data["role"] == "producer"
