import uuid
from unittest.mock import MagicMock
import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.errors import InvalidCredentialsError
from app.core.security import hash_password
from app.db.models import Consultant, Producer
from app.db.repositories.consultant_repo import ConsultantRepository
from app.db.repositories.producer_repo import ProducerRepository
from app.main import app
from app.schemas.auth import (
    AuthChangePasswordRequest,
    AuthChangePasswordResponse,
)
from app.api.v1.auth import AuthService, get_auth_service
from app.services.consultant_service import ConsultantService
from app.services.producer_service import ProducerService

AUTH_HEADERS = {"X-Service-Token": settings.SERVICE_TOKEN}


# ==============================================================================
# 1. DTO Validation Tests
# ==============================================================================


def test_auth_change_password_request_valid_with_id():
    uid = uuid.uuid4()
    req = AuthChangePasswordRequest(
        role="producer",
        id=uid,
        current_password="oldPassword123",
        new_password="newPassword456",
    )
    assert req.role == "producer"
    assert req.id == uid
    assert req.email is None
    assert req.current_password.get_secret_value() == "oldPassword123"
    assert req.new_password.get_secret_value() == "newPassword456"


def test_auth_change_password_request_valid_with_email():
    req = AuthChangePasswordRequest(
        role="consultant",
        email="consultor@educampo.com",
        current_password="oldPassword123",
        new_password="newPassword456",
    )
    assert req.role == "consultant"
    assert req.email == "consultor@educampo.com"
    assert req.id is None


def test_auth_change_password_request_fails_without_identifier():
    with pytest.raises(ValidationError) as exc:
        AuthChangePasswordRequest(
            role="producer",
            current_password="oldPassword123",
            new_password="newPassword456",
        )
    assert "identificar o usuário" in str(exc.value)


def test_auth_change_password_request_fails_when_new_password_too_short():
    with pytest.raises(ValidationError):
        AuthChangePasswordRequest(
            role="producer",
            id=uuid.uuid4(),
            current_password="oldPassword123",
            new_password="12345",  # less than 6 chars
        )


def test_auth_change_password_request_fails_on_invalid_role():
    with pytest.raises(ValidationError):
        AuthChangePasswordRequest(
            role="admin",  # invalid
            id=uuid.uuid4(),
            current_password="oldPassword123",
            new_password="newPassword456",
        )


# ==============================================================================
# 2. ProducerService.change_password Unit Tests
# ==============================================================================


def test_producer_service_change_password_success_by_id():
    # Arrange
    pid = uuid.uuid4()
    hashed = hash_password("oldPass123")
    mock_producer = Producer(
        id=pid,
        email="prod@educampo.com",
        hashed_password=hashed,
        nome="Produtor Teste",
        version=1,
    )
    repo = MagicMock(spec=ProducerRepository)
    repo.get_by_id.return_value = mock_producer
    service = ProducerService(repository=repo)

    # Act
    res = service.change_password(
        current_password="oldPass123",
        new_password="newPass456",
        producer_id=pid,
    )

    # Assert
    assert isinstance(res, AuthChangePasswordResponse)
    assert res.id == pid
    assert res.role == "producer"
    repo.update_password.assert_called_once()
    call_args = repo.update_password.call_args[0]
    assert call_args[0] == pid
    assert call_args[1] != "newPass456"  # must be hashed


def test_producer_service_change_password_success_by_email():
    # Arrange
    pid = uuid.uuid4()
    email = "prod@educampo.com"
    hashed = hash_password("oldPass123")
    mock_producer = Producer(
        id=pid,
        email=email,
        hashed_password=hashed,
        nome="Produtor Teste",
        version=1,
    )
    repo = MagicMock(spec=ProducerRepository)
    repo.get_by_email.return_value = mock_producer
    service = ProducerService(repository=repo)

    # Act
    res = service.change_password(
        current_password="oldPass123",
        new_password="newPass456",
        email=email,
    )

    # Assert
    assert res.id == pid
    repo.update_password.assert_called_once()


def test_producer_service_change_password_fails_when_not_found():
    # Arrange
    repo = MagicMock(spec=ProducerRepository)
    repo.get_by_id.return_value = None
    service = ProducerService(repository=repo)

    # Act & Assert
    with pytest.raises(InvalidCredentialsError):
        service.change_password(
            current_password="oldPass123",
            new_password="newPass456",
            producer_id=uuid.uuid4(),
        )


def test_producer_service_change_password_fails_when_current_password_incorrect():
    # Arrange
    pid = uuid.uuid4()
    hashed = hash_password("correctPassword")
    mock_producer = Producer(
        id=pid,
        email="prod@educampo.com",
        hashed_password=hashed,
        nome="Produtor Teste",
        version=1,
    )
    repo = MagicMock(spec=ProducerRepository)
    repo.get_by_id.return_value = mock_producer
    service = ProducerService(repository=repo)

    # Act & Assert
    with pytest.raises(InvalidCredentialsError):
        service.change_password(
            current_password="wrongPassword",
            new_password="newPass456",
            producer_id=pid,
        )
    repo.update_password.assert_not_called()


# ==============================================================================
# 3. ConsultantService.change_password Unit Tests
# ==============================================================================


def test_consultant_service_change_password_success():
    # Arrange
    cid = uuid.uuid4()
    hashed = hash_password("oldSecret123")
    mock_consultant = Consultant(
        id=cid,
        email="consultant@educampo.com",
        hashed_password=hashed,
        nome="Consultor Teste",
        version=1,
    )
    repo = MagicMock(spec=ConsultantRepository)
    repo.get_by_id.return_value = mock_consultant
    service = ConsultantService(repository=repo)

    # Act
    res = service.change_password(
        current_password="oldSecret123",
        new_password="newSecret456",
        consultant_id=cid,
    )

    # Assert
    assert res.id == cid
    assert res.role == "consultant"
    repo.update_password.assert_called_once()


def test_consultant_service_change_password_fails_on_wrong_password():
    # Arrange
    cid = uuid.uuid4()
    hashed = hash_password("oldSecret123")
    mock_consultant = Consultant(
        id=cid,
        email="consultant@educampo.com",
        hashed_password=hashed,
        nome="Consultor Teste",
        version=1,
    )
    repo = MagicMock(spec=ConsultantRepository)
    repo.get_by_id.return_value = mock_consultant
    service = ConsultantService(repository=repo)

    # Act & Assert
    with pytest.raises(InvalidCredentialsError):
        service.change_password(
            current_password="wrongSecret",
            new_password="newSecret456",
            consultant_id=cid,
        )
    repo.update_password.assert_not_called()


# ==============================================================================
# 4. AuthService Delegation Tests
# ==============================================================================


def test_auth_service_delegates_to_producer_and_consultant():
    mock_db = MagicMock()
    auth_service = AuthService(mock_db)
    auth_service.producer_service = MagicMock()
    auth_service.consultant_service = MagicMock()

    uid = uuid.uuid4()

    # Producer
    req_prod = AuthChangePasswordRequest(
        role="producer",
        id=uid,
        current_password="old",
        new_password="newpassword123",
    )
    auth_service.change_password(req_prod)
    auth_service.producer_service.change_password.assert_called_once()

    # Consultant
    req_cons = AuthChangePasswordRequest(
        role="consultant",
        id=uid,
        current_password="old",
        new_password="newpassword123",
    )
    auth_service.change_password(req_cons)
    auth_service.consultant_service.change_password.assert_called_once()


# ==============================================================================
# 5. REST Endpoint POST /v1/auth/password Tests
# ==============================================================================


@pytest.fixture
def client_with_mock_auth():
    mock_service = MagicMock()
    app.dependency_overrides[get_auth_service] = lambda: mock_service
    yield TestClient(app), mock_service
    app.dependency_overrides.clear()


def test_change_password_endpoint_requires_service_token(client_with_mock_auth):
    client, _ = client_with_mock_auth
    payload = {
        "role": "producer",
        "id": str(uuid.uuid4()),
        "current_password": "oldPassword123",
        "new_password": "newPassword456",
    }
    # No header
    res = client.post("/v1/auth/password", json=payload)
    assert res.status_code == 401
    assert res.headers["content-type"].startswith("application/problem+json")


def test_change_password_endpoint_success(client_with_mock_auth):
    client, mock_auth = client_with_mock_auth
    uid = uuid.uuid4()
    mock_auth.change_password.return_value = AuthChangePasswordResponse(
        id=uid,
        role="producer",
        message="Senha atualizada com sucesso.",
    )

    payload = {
        "role": "producer",
        "id": str(uid),
        "current_password": "oldPassword123",
        "new_password": "newPassword456",
    }
    res = client.post("/v1/auth/password", json=payload, headers=AUTH_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == str(uid)
    assert data["role"] == "producer"
    assert "sucesso" in data["message"]


def test_change_password_endpoint_invalid_credentials_returns_401(client_with_mock_auth):
    client, mock_auth = client_with_mock_auth
    mock_auth.change_password.side_effect = InvalidCredentialsError("Credenciais invalidas.")

    payload = {
        "role": "producer",
        "id": str(uuid.uuid4()),
        "current_password": "wrongPassword",
        "new_password": "newPassword456",
    }
    res = client.post("/v1/auth/password", json=payload, headers=AUTH_HEADERS)
    assert res.status_code == 401
    data = res.json()
    assert data["type"] == "invalid-credentials"


def test_change_password_endpoint_validation_error_returns_422(client_with_mock_auth):
    client, _ = client_with_mock_auth
    # Missing id and email
    payload = {
        "role": "producer",
        "current_password": "oldPassword123",
        "new_password": "newPassword456",
    }
    res = client.post("/v1/auth/password", json=payload, headers=AUTH_HEADERS)
    assert res.status_code == 422
