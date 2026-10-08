from datetime import datetime, timezone
from unittest.mock import MagicMock
import uuid
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.errors import (
    ConcurrencyConflictError,
    NotFoundError,
    PreconditionRequiredError,
)
from app.main import app
from app.schemas.diagnostic_result import DiagnosticResultDTO
from app.services.diagnostic_result_service import DiagnosticResultService


@pytest.fixture
def mock_diagnostic_service():
    return MagicMock(spec=DiagnosticResultService)


@pytest.fixture
def client(mock_diagnostic_service):
    from app.api.v1.diagnostic_results import get_diagnostic_service

    app.dependency_overrides[get_diagnostic_service] = lambda: mock_diagnostic_service
    yield TestClient(app)
    app.dependency_overrides.clear()


AUTH_HEADERS = {"X-Service-Token": settings.SERVICE_TOKEN}


def test_missing_service_token_diagnostic_results_returns_401(client):
    pid = uuid.uuid4()
    response = client.get(f"/v1/diagnostic-results/{pid}")
    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["type"] == "unauthorized"


def test_get_diagnostic_result_endpoint_found(client, mock_diagnostic_service):
    pid = uuid.uuid4()
    now = datetime.now(timezone.utc)
    mock_diagnostic_service.get_by_producer_id.return_value = DiagnosticResultDTO(
        producer_id=pid,
        input_data={"area": 100},
        diagnostico={"status": "bom"},
        simulacao={"lucro": 50000},
        version=1,
        updated_at=now,
    )

    response = client.get(f"/v1/diagnostic-results/{pid}", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["producer_id"] == str(pid)
    assert data["input_data"] == {"area": 100}
    assert data["version"] == 1


def test_get_diagnostic_result_endpoint_not_found(client, mock_diagnostic_service):
    pid = uuid.uuid4()
    mock_diagnostic_service.get_by_producer_id.side_effect = NotFoundError(
        f"Diagnostic result for producer '{pid}' not found."
    )

    response = client.get(f"/v1/diagnostic-results/{pid}", headers=AUTH_HEADERS)
    assert response.status_code == 404
    assert response.json()["type"] == "not-found"


def test_put_diagnostic_result_endpoint_create_201(client, mock_diagnostic_service):
    pid = uuid.uuid4()
    now = datetime.now(timezone.utc)
    mock_diagnostic_service.save_diagnostic_result.return_value = (
        DiagnosticResultDTO(
            producer_id=pid,
            input_data={"area": 100},
            diagnostico=None,
            simulacao=None,
            version=1,
            updated_at=now,
        ),
        True,
    )

    payload = {"input_data": {"area": 100}}
    response = client.put(f"/v1/diagnostic-results/{pid}", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 201
    data = response.json()
    assert data["producer_id"] == str(pid)
    assert data["version"] == 1


def test_put_diagnostic_result_endpoint_update_200(client, mock_diagnostic_service):
    pid = uuid.uuid4()
    now = datetime.now(timezone.utc)
    mock_diagnostic_service.save_diagnostic_result.return_value = (
        DiagnosticResultDTO(
            producer_id=pid,
            input_data={"area": 150},
            diagnostico={"status": "atualizado"},
            simulacao=None,
            version=2,
            updated_at=now,
        ),
        False,
    )

    payload = {"input_data": {"area": 150}, "diagnostico": {"status": "atualizado"}}
    headers = {**AUTH_HEADERS, "If-Match": "1"}
    response = client.put(f"/v1/diagnostic-results/{pid}", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["version"] == 2


def test_put_diagnostic_result_endpoint_optimistic_lock_412(client, mock_diagnostic_service):
    pid = uuid.uuid4()
    mock_diagnostic_service.save_diagnostic_result.side_effect = ConcurrencyConflictError(
        "Version mismatch"
    )

    payload = {"input_data": {"area": 150}}
    headers = {**AUTH_HEADERS, "If-Match": "1"}
    response = client.put(f"/v1/diagnostic-results/{pid}", json=payload, headers=headers)
    assert response.status_code == 412
    assert response.json()["type"] == "version-mismatch"


def test_put_diagnostic_result_endpoint_missing_if_match_428(client, mock_diagnostic_service):
    pid = uuid.uuid4()
    mock_diagnostic_service.save_diagnostic_result.side_effect = PreconditionRequiredError(
        "Header 'If-Match' is required"
    )

    payload = {"input_data": {"area": 150}}
    response = client.put(f"/v1/diagnostic-results/{pid}", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 428
    assert response.json()["type"] == "precondition-required"


def test_put_diagnostic_result_endpoint_producer_not_found_404(client, mock_diagnostic_service):
    pid = uuid.uuid4()
    mock_diagnostic_service.save_diagnostic_result.side_effect = NotFoundError(
        f"Producer with id '{pid}' not found."
    )

    payload = {"input_data": {"area": 150}}
    response = client.put(f"/v1/diagnostic-results/{pid}", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 404
    assert response.json()["type"] == "not-found"


def test_put_diagnostic_result_endpoint_invalid_payload_422(client):
    pid = uuid.uuid4()
    response = client.put(f"/v1/diagnostic-results/{pid}", json={}, headers=AUTH_HEADERS)
    assert response.status_code == 422


def test_put_diagnostic_result_endpoint_invalid_if_match_400(client):
    pid = uuid.uuid4()
    payload = {"input_data": {"area": 150}}
    headers = {**AUTH_HEADERS, "If-Match": "invalido"}
    response = client.put(f"/v1/diagnostic-results/{pid}", json=payload, headers=headers)
    assert response.status_code == 400
