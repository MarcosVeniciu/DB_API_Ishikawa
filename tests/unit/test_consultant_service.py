from datetime import datetime, timezone
from unittest.mock import MagicMock
import uuid
import pytest
from pydantic import SecretStr

from app.core.errors import (
    DuplicateEmailError,
    ConcurrencyConflictError,
    NotFoundError,
    InvalidCredentialsError,
)
from app.core.security import hash_password
from app.db.models import Consultant
from app.schemas.auth import AuthVerifyRequest
from app.schemas.consultant import (
    ConsultantCreateDTO,
    ConsultantUpdateDTO,
)
from app.services.consultant_service import ConsultantService


@pytest.fixture
def mock_repo():
    return MagicMock()


@pytest.fixture
def service(mock_repo):
    return ConsultantService(repository=mock_repo)


def test_create_consultant_success(service, mock_repo):
    # Arrange
    cid = uuid.uuid4()
    dto = ConsultantCreateDTO(
        id=cid,
        nome="Consultor Exemplo",
        email="consultor@educampo.com.br",
        password=SecretStr("Segredo123"),
    )
    mock_repo.get_by_email.return_value = None

    def fake_create(model):
        model.created_at = datetime.now(timezone.utc)
        return model

    mock_repo.create.side_effect = fake_create

    # Act
    result = service.create_consultant(dto)

    # Assert
    assert result.id == cid
    assert result.nome == "Consultor Exemplo"
    assert result.email == "consultor@educampo.com.br"
    assert result.version == 1
    assert result.producers_managed == []
    assert not hasattr(result, "password")
    assert not hasattr(result, "hashed_password")
    mock_repo.create.assert_called_once()


def test_create_consultant_duplicate_email(service, mock_repo):
    # Arrange
    dto = ConsultantCreateDTO(
        nome="Consultor Duplicado",
        email="duplicado@educampo.com.br",
        password=SecretStr("Segredo123"),
    )
    mock_repo.get_by_email.return_value = Consultant(
        id=uuid.uuid4(),
        nome="Existente",
        email="duplicado@educampo.com.br",
        hashed_password="hash",
    )

    # Act & Assert
    with pytest.raises(DuplicateEmailError):
        service.create_consultant(dto)


def test_get_consultant_by_id_found(service, mock_repo):
    # Arrange
    cid = uuid.uuid4()
    model = Consultant(
        id=cid,
        nome="Consultor Cadastrado",
        email="cadastrado@educampo.com.br",
        hashed_password="hash",
        version=1,
        created_at=datetime.now(timezone.utc),
    )
    mock_repo.get_by_id.return_value = model

    # Act
    dto = service.get_consultant_by_id(cid)

    # Assert
    assert dto.id == cid
    assert dto.nome == "Consultor Cadastrado"


def test_get_consultant_by_id_not_found(service, mock_repo):
    # Arrange
    cid = uuid.uuid4()
    mock_repo.get_by_id.return_value = None

    # Act & Assert
    with pytest.raises(NotFoundError):
        service.get_consultant_by_id(cid)


def test_update_consultant_success(service, mock_repo):
    # Arrange
    cid = uuid.uuid4()
    dto = ConsultantUpdateDTO(nome="Nome Atualizado")
    mock_repo.get_by_id.return_value = Consultant(
        id=cid,
        nome="Nome Velho",
        email="c@educampo.com.br",
        hashed_password="hash",
        version=1,
        created_at=datetime.now(timezone.utc),
    )
    updated_model = Consultant(
        id=cid,
        nome="Nome Atualizado",
        email="c@educampo.com.br",
        hashed_password="hash",
        version=2,
        created_at=datetime.now(timezone.utc),
    )
    mock_repo.update_atomic.return_value = updated_model

    # Act
    result = service.update_consultant(cid, dto, expected_version=1)

    # Assert
    assert result.nome == "Nome Atualizado"
    assert result.version == 2
    mock_repo.update_atomic.assert_called_once_with(
        consultant_id=cid,
        nome="Nome Atualizado",
        expected_version=1,
    )


def test_update_consultant_version_conflict(service, mock_repo):
    # Arrange
    cid = uuid.uuid4()
    dto = ConsultantUpdateDTO(nome="Nome Atualizado")
    mock_repo.get_by_id.return_value = Consultant(
        id=cid,
        nome="Nome Velho",
        email="c@educampo.com.br",
        hashed_password="hash",
        version=2,
        created_at=datetime.now(timezone.utc),
    )
    # update_atomic devolve None quando version != expected_version
    mock_repo.update_atomic.return_value = None

    # Act & Assert
    with pytest.raises(ConcurrencyConflictError):
        service.update_consultant(cid, dto, expected_version=1)


def test_verify_credentials_success(service, mock_repo):
    # Arrange
    cid = uuid.uuid4()
    hashed = hash_password("SenhaCerta123")
    mock_repo.get_by_email.return_value = Consultant(
        id=cid,
        nome="Consultor Login",
        email="login@educampo.com.br",
        hashed_password=hashed,
    )
    req = AuthVerifyRequest(
        email="login@educampo.com.br",
        password=SecretStr("SenhaCerta123"),
        role="consultant",
    )

    # Act
    resp = service.verify_credentials(req)

    # Assert
    assert resp.id == cid
    assert resp.role == "consultant"


def test_verify_credentials_wrong_password_or_email(service, mock_repo):
    # Arrange: email inexistente
    mock_repo.get_by_email.return_value = None
    req1 = AuthVerifyRequest(
        email="inexistente@educampo.com.br",
        password=SecretStr("Senha123"),
        role="consultant",
    )

    with pytest.raises(InvalidCredentialsError):
        service.verify_credentials(req1)

    # Arrange: senha incorreta
    mock_repo.get_by_email.return_value = Consultant(
        id=uuid.uuid4(),
        nome="Consultor Login",
        email="login@educampo.com.br",
        hashed_password=hash_password("SenhaCerta123"),
    )
    req2 = AuthVerifyRequest(
        email="login@educampo.com.br",
        password=SecretStr("SenhaErrada"),
        role="consultant",
    )

    with pytest.raises(InvalidCredentialsError):
        service.verify_credentials(req2)
