from datetime import datetime, timezone
from unittest.mock import MagicMock
import uuid
import pytest
from pydantic import ValidationError
from app.db.models import Consultant, Producer
from app.db.repositories.consultant_repo import ConsultantRepository
from app.db.repositories.producer_repo import ProducerRepository
from app.schemas.producer import ProducerCreateDTO, ProducerDTO, ProducerUpdateDTO


def test_producer_create_dto_valid():
    pid = uuid.uuid4()
    cid = uuid.uuid4()
    dto = ProducerCreateDTO(
        id=pid,
        email="fazenda@educampo.com.br",
        password="MinhaSenhaForte123",
        nome="Fazenda Esperança",
        id_fazenda="FAZ-100",
        dados={"area_total": 500, "irrigado": True},
        consultant_id=cid,
    )
    assert dto.id == pid
    assert str(dto.email) == "fazenda@educampo.com.br"
    assert dto.password.get_secret_value() == "MinhaSenhaForte123"
    assert dto.nome == "Fazenda Esperança"
    assert dto.id_fazenda == "FAZ-100"
    assert dto.dados["area_total"] == 500
    assert dto.consultant_id == cid


def test_producer_create_dto_invalid_fields():
    # Password too short
    with pytest.raises(ValidationError):
        ProducerCreateDTO(
            email="valido@educampo.com.br",
            password="123",  # min 6
            nome="Fazenda",
        )

    # Extra fields forbidden
    with pytest.raises(ValidationError):
        ProducerCreateDTO(
            email="valido@educampo.com.br",
            password="SenhaValida123",
            nome="Fazenda",
            campo_desconhecido="invalido",
        )


def test_producer_update_dto_immutability():
    # Valid update
    dto = ProducerUpdateDTO(
        nome="Fazenda Renomeada",
        id_fazenda="NOVO-01",
        dados={"status": "ativo"},
    )
    assert dto.nome == "Fazenda Renomeada"

    # Email cannot be updated (extra field forbidden)
    with pytest.raises(ValidationError):
        ProducerUpdateDTO(
            nome="Novo Nome",
            email="tentativa@educampo.com.br",
        )

    # Password cannot be updated in PUT (extra field forbidden)
    with pytest.raises(ValidationError):
        ProducerUpdateDTO(
            nome="Novo Nome",
            password="NovaSenha123",
        )


def test_producer_dto_from_attributes():
    pid = uuid.uuid4()
    now = datetime.now(timezone.utc)
    model = Producer(
        id=pid,
        email="produtor@educampo.com.br",
        hashed_password="secret_hash_value",
        nome="Fazenda Sol Nascente",
        id_fazenda="FAZ-01",
        dados={"hectares": 200},
        consultant_id=None,
        version=1,
        created_at=now,
        updated_at=now,
    )

    dto = ProducerDTO.model_validate(model)
    assert dto.id == pid
    assert dto.email == "produtor@educampo.com.br"
    assert dto.nome == "Fazenda Sol Nascente"
    assert dto.version == 1
    assert not hasattr(dto, "hashed_password")


def test_producer_repo_create():
    session = MagicMock()
    repo = ProducerRepository(session)
    producer = Producer(
        id=uuid.uuid4(),
        email="test@educampo.com.br",
        hashed_password="hash",
        nome="Fazenda Teste",
    )

    result = repo.create(producer)
    session.add.assert_called_once_with(producer)
    session.commit.assert_called_once()
    session.refresh.assert_called_once_with(producer)
    assert result == producer


def test_producer_repo_get_by_id():
    session = MagicMock()
    repo = ProducerRepository(session)
    pid = uuid.uuid4()
    expected_producer = Producer(id=pid, email="a@b.com", hashed_password="h", nome="F")

    session.execute.return_value.scalar_one_or_none.return_value = expected_producer
    result = repo.get_by_id(pid)

    assert result == expected_producer
    session.execute.assert_called_once()


def test_producer_repo_find_by_name_deterministic():
    session = MagicMock()
    repo = ProducerRepository(session)
    expected_producer = Producer(
        id=uuid.uuid4(),
        email="antigo@educampo.com.br",
        hashed_password="h",
        nome="Fazenda Modelo",
    )

    session.execute.return_value.scalar_one_or_none.return_value = expected_producer
    result = repo.find_by_name("Fazenda Modelo")

    assert result == expected_producer
    session.execute.assert_called_once()


def test_producer_repo_update_atomic_success():
    session = MagicMock()
    repo = ProducerRepository(session)
    pid = uuid.uuid4()
    updated_producer = Producer(
        id=pid,
        email="a@b.com",
        hashed_password="h",
        nome="Novo Nome",
        version=2,
    )

    session.execute.return_value.scalar_one_or_none.return_value = updated_producer
    result = repo.update_atomic(
        producer_id=pid,
        nome="Novo Nome",
        id_fazenda="FZ-02",
        dados={"area": 300},
        consultant_id=None,
        expected_version=1,
    )

    assert result == updated_producer
    session.commit.assert_called_once()


def test_producer_repo_delete_success():
    session = MagicMock()
    repo = ProducerRepository(session)
    pid = uuid.uuid4()
    producer = Producer(id=pid, email="a@b.com", hashed_password="h", nome="F")

    session.execute.return_value.scalar_one_or_none.return_value = producer
    result = repo.delete(pid)

    assert result is True
    session.delete.assert_called_once_with(producer)
    session.commit.assert_called_once()


def test_producer_repo_get_producers_managed_by_consultant():
    session = MagicMock()
    repo = ProducerRepository(session)
    cid = uuid.uuid4()
    id1 = uuid.uuid4()
    id2 = uuid.uuid4()

    session.execute.return_value.scalars.return_value.all.return_value = [id1, id2]
    result = repo.get_producers_managed_by_consultant(cid)

    assert result == [id1, id2]


def test_consultant_repo_get_producers_managed():
    session = MagicMock()
    repo = ConsultantRepository(session)
    cid = uuid.uuid4()
    id1 = uuid.uuid4()

    session.execute.return_value.scalars.return_value.all.return_value = [id1]
    result = repo.get_producers_managed(cid)

    assert result == [id1]
