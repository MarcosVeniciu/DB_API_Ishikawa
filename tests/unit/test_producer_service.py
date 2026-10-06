from datetime import datetime, timezone
from unittest.mock import MagicMock
import uuid
import pytest
from app.core.errors import (
    ConcurrencyConflictError,
    DuplicateEmailError,
    InvalidCredentialsError,
    NotFoundError,
)
from app.db.models import Consultant, Producer
from app.schemas.auth import AuthVerifyRequest
from app.schemas.consultant import ConsultantDTO
from app.schemas.producer import ProducerCreateDTO, ProducerUpdateDTO
from app.services.consultant_service import ConsultantService
from app.services.producer_service import ProducerService


@pytest.fixture
def mock_repo():
    return MagicMock()


@pytest.fixture
def mock_consultant_repo():
    return MagicMock()


@pytest.fixture
def service(mock_repo, mock_consultant_repo):
    return ProducerService(repository=mock_repo, consultant_repository=mock_consultant_repo)


def test_create_producer_success(service, mock_repo, mock_consultant_repo):
    pid = uuid.uuid4()
    cid = uuid.uuid4()
    now = datetime.now(timezone.utc)
    dto = ProducerCreateDTO(
        id=pid,
        email="fazenda@educampo.com.br",
        password="SenhaSegura123",
        nome="Fazenda Horizonte",
        id_fazenda="FZ-99",
        dados={"cafe": 100},
        consultant_id=cid,
    )

    mock_repo.get_by_email.return_value = None
    mock_consultant_repo.get_by_id.return_value = Consultant(id=cid, nome="Consultor", email="c@e.com", hashed_password="h")
    mock_repo.create.side_effect = lambda p: Producer(
        id=p.id,
        email=p.email,
        hashed_password=p.hashed_password,
        nome=p.nome,
        id_fazenda=p.id_fazenda,
        dados=p.dados,
        consultant_id=p.consultant_id,
        version=p.version,
        created_at=now,
        updated_at=now,
    )

    result = service.create_producer(dto)

    assert result.id == pid
    assert result.email == "fazenda@educampo.com.br"
    assert result.nome == "Fazenda Horizonte"
    assert result.version == 1
    mock_repo.create.assert_called_once()


def test_create_producer_duplicate_email(service, mock_repo):
    dto = ProducerCreateDTO(
        email="duplicado@educampo.com.br",
        password="SenhaSegura123",
        nome="Fazenda Duplicada",
    )
    mock_repo.get_by_email.return_value = Producer(id=uuid.uuid4(), email="duplicado@educampo.com.br", hashed_password="h", nome="F")

    with pytest.raises(DuplicateEmailError) as exc:
        service.create_producer(dto)
    assert exc.value.status_code == 409


def test_create_producer_invalid_consultant(service, mock_repo, mock_consultant_repo):
    cid = uuid.uuid4()
    dto = ProducerCreateDTO(
        email="novo@educampo.com.br",
        password="SenhaSegura123",
        nome="Fazenda Nova",
        consultant_id=cid,
    )
    mock_repo.get_by_email.return_value = None
    mock_consultant_repo.get_by_id.return_value = None

    with pytest.raises(NotFoundError) as exc:
        service.create_producer(dto)
    assert exc.value.status_code == 404


def test_get_producer_by_id_found(service, mock_repo):
    pid = uuid.uuid4()
    now = datetime.now(timezone.utc)
    producer = Producer(
        id=pid,
        email="teste@educampo.com.br",
        hashed_password="h",
        nome="Fazenda Teste",
        id_fazenda=None,
        dados={},
        consultant_id=None,
        version=1,
        created_at=now,
        updated_at=now,
    )
    mock_repo.get_by_id.return_value = producer

    result = service.get_producer_by_id(pid)
    assert result.id == pid
    assert result.nome == "Fazenda Teste"


def test_get_producer_by_id_not_found(service, mock_repo):
    pid = uuid.uuid4()
    mock_repo.get_by_id.return_value = None

    with pytest.raises(NotFoundError) as exc:
        service.get_producer_by_id(pid)
    assert exc.value.status_code == 404


def test_find_producer_by_name(service, mock_repo):
    now = datetime.now(timezone.utc)
    producer = Producer(
        id=uuid.uuid4(),
        email="antiga@educampo.com.br",
        hashed_password="h",
        nome="Fazenda Modelo",
        dados={},
        version=1,
        created_at=now,
        updated_at=now,
    )
    mock_repo.find_by_name.return_value = producer

    result = service.find_producer_by_name("Fazenda Modelo")
    assert result is not None
    assert result.email == "antiga@educampo.com.br"


def test_update_producer_success(service, mock_repo):
    pid = uuid.uuid4()
    now = datetime.now(timezone.utc)
    existing = Producer(
        id=pid,
        email="original@educampo.com.br",
        hashed_password="h",
        nome="Nome Velho",
        id_fazenda="OLD",
        dados={},
        consultant_id=None,
        version=1,
        created_at=now,
        updated_at=now,
    )
    updated = Producer(
        id=pid,
        email="original@educampo.com.br",
        hashed_password="h",
        nome="Nome Novo",
        id_fazenda="NEW",
        dados={"atualizado": True},
        consultant_id=None,
        version=2,
        created_at=now,
        updated_at=now,
    )

    mock_repo.get_by_id.return_value = existing
    mock_repo.update_atomic.return_value = updated

    dto = ProducerUpdateDTO(nome="Nome Novo", id_fazenda="NEW", dados={"atualizado": True})
    result = service.update_producer(pid, dto, expected_version=1)

    assert result.version == 2
    assert result.nome == "Nome Novo"


def test_update_producer_conflict(service, mock_repo):
    pid = uuid.uuid4()
    now = datetime.now(timezone.utc)
    existing = Producer(
        id=pid,
        email="orig@educampo.com.br",
        hashed_password="h",
        nome="Nome",
        dados={},
        version=2,
        created_at=now,
        updated_at=now,
    )
    mock_repo.get_by_id.return_value = existing
    mock_repo.update_atomic.return_value = None

    dto = ProducerUpdateDTO(nome="Tentativa")
    with pytest.raises(ConcurrencyConflictError) as exc:
        service.update_producer(pid, dto, expected_version=1)
    assert exc.value.status_code == 412


def test_delete_producer_success(service, mock_repo):
    pid = uuid.uuid4()
    mock_repo.get_by_id.return_value = Producer(id=pid, email="a@b.com", hashed_password="h", nome="F")
    mock_repo.delete.return_value = True

    service.delete_producer(pid)
    mock_repo.delete.assert_called_once_with(pid)


def test_delete_producer_not_found(service, mock_repo):
    pid = uuid.uuid4()
    mock_repo.get_by_id.return_value = None

    with pytest.raises(NotFoundError):
        service.delete_producer(pid)


def test_verify_credentials_producer_success(service, mock_repo):
    from app.core.security import hash_password
    pid = uuid.uuid4()
    hashed = hash_password("SenhaCerta123")
    producer = Producer(
        id=pid,
        email="produtor@educampo.com.br",
        hashed_password=hashed,
        nome="Produtor",
    )
    mock_repo.get_by_email.return_value = producer

    req = AuthVerifyRequest(
        email="produtor@educampo.com.br",
        password="SenhaCerta123",
        role="producer",
    )
    res = service.verify_credentials(req)
    assert res.id == pid
    assert res.role == "producer"


def test_verify_credentials_producer_invalid(service, mock_repo):
    mock_repo.get_by_email.return_value = None
    req = AuthVerifyRequest(
        email="inexistente@educampo.com.br",
        password="SenhaQualquer",
        role="producer",
    )
    with pytest.raises(InvalidCredentialsError):
        service.verify_credentials(req)


def test_consultant_service_derives_producers_managed():
    cid = uuid.uuid4()
    p1 = uuid.uuid4()
    p2 = uuid.uuid4()
    now = datetime.now(timezone.utc)
    consultant = Consultant(
        id=cid,
        nome="Consultor Especialista",
        email="consultor@educampo.com.br",
        hashed_password="h",
        version=1,
        created_at=now,
        updated_at=now,
    )

    c_repo = MagicMock()
    c_repo.get_by_id.return_value = consultant
    c_repo.get_producers_managed.return_value = [p1, p2]

    c_service = ConsultantService(repository=c_repo)
    result = c_service.get_consultant_by_id(cid)

    assert result.id == cid
    assert result.producers_managed == [p1, p2]
