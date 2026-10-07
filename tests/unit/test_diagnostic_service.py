from datetime import datetime, timezone
from unittest.mock import MagicMock
import uuid
import pytest
from app.core.errors import ConcurrencyConflictError, NotFoundError, PreconditionRequiredError
from app.db.models import DiagnosticResult, Producer
from app.schemas.diagnostic_result import DiagnosticResultDTO, DiagnosticResultSaveDTO
from app.services.diagnostic_result_service import DiagnosticResultService


def test_save_diagnostic_result_creates_when_not_exists():
    mock_diagnostic_repo = MagicMock()
    mock_producer_repo = MagicMock()
    service = DiagnosticResultService(
        diagnostic_repo=mock_diagnostic_repo,
        producer_repo=mock_producer_repo,
    )

    pid = uuid.uuid4()
    mock_producer = Producer(id=pid, email="p@educampo.com.br", nome="Fazenda", version=1)
    mock_producer_repo.get_by_id.return_value = mock_producer

    mock_diagnostic_repo.get_by_producer_id.return_value = None

    created_model = DiagnosticResult(
        producer_id=pid,
        input_data={"area": 10},
        diagnostico={"status": "ok"},
        simulacao=None,
        version=1,
        updated_at=datetime.now(timezone.utc),
    )
    mock_diagnostic_repo.create.return_value = created_model

    dto = DiagnosticResultSaveDTO(input_data={"area": 10}, diagnostico={"status": "ok"})
    result_dto, created = service.save_diagnostic_result(pid, dto, expected_version=None)

    assert created is True
    assert result_dto.producer_id == pid
    assert result_dto.version == 1
    mock_diagnostic_repo.create.assert_called_once()


def test_save_diagnostic_result_updates_when_exists_and_version_matches():
    mock_diagnostic_repo = MagicMock()
    mock_producer_repo = MagicMock()
    service = DiagnosticResultService(
        diagnostic_repo=mock_diagnostic_repo,
        producer_repo=mock_producer_repo,
    )

    pid = uuid.uuid4()
    mock_producer = Producer(id=pid, email="p@educampo.com.br", nome="Fazenda", version=1)
    mock_producer_repo.get_by_id.return_value = mock_producer

    existing_model = DiagnosticResult(
        producer_id=pid,
        input_data={"area": 10},
        version=1,
        updated_at=datetime.now(timezone.utc),
    )
    mock_diagnostic_repo.get_by_producer_id.return_value = existing_model

    updated_model = DiagnosticResult(
        producer_id=pid,
        input_data={"area": 15},
        version=2,
        updated_at=datetime.now(timezone.utc),
    )
    mock_diagnostic_repo.update_atomic.return_value = updated_model

    dto = DiagnosticResultSaveDTO(input_data={"area": 15})
    result_dto, created = service.save_diagnostic_result(pid, dto, expected_version=1)

    assert created is False
    assert result_dto.producer_id == pid
    assert result_dto.version == 2
    mock_diagnostic_repo.update_atomic.assert_called_once_with(
        producer_id=pid,
        dto=dto,
        expected_version=1,
    )


def test_save_diagnostic_result_raises_428_when_exists_and_if_match_missing():
    mock_diagnostic_repo = MagicMock()
    mock_producer_repo = MagicMock()
    service = DiagnosticResultService(
        diagnostic_repo=mock_diagnostic_repo,
        producer_repo=mock_producer_repo,
    )

    pid = uuid.uuid4()
    mock_producer = Producer(id=pid, email="p@educampo.com.br", nome="Fazenda", version=1)
    mock_producer_repo.get_by_id.return_value = mock_producer

    existing_model = DiagnosticResult(
        producer_id=pid,
        input_data={"area": 10},
        version=1,
        updated_at=datetime.now(timezone.utc),
    )
    mock_diagnostic_repo.get_by_producer_id.return_value = existing_model

    dto = DiagnosticResultSaveDTO(input_data={"area": 15})
    with pytest.raises(PreconditionRequiredError):
        service.save_diagnostic_result(pid, dto, expected_version=None)


def test_save_diagnostic_result_raises_412_when_version_mismatch():
    mock_diagnostic_repo = MagicMock()
    mock_producer_repo = MagicMock()
    service = DiagnosticResultService(
        diagnostic_repo=mock_diagnostic_repo,
        producer_repo=mock_producer_repo,
    )

    pid = uuid.uuid4()
    mock_producer = Producer(id=pid, email="p@educampo.com.br", nome="Fazenda", version=1)
    mock_producer_repo.get_by_id.return_value = mock_producer

    existing_model = DiagnosticResult(
        producer_id=pid,
        input_data={"area": 10},
        version=2,
        updated_at=datetime.now(timezone.utc),
    )
    mock_diagnostic_repo.get_by_producer_id.return_value = existing_model
    mock_diagnostic_repo.update_atomic.return_value = None

    dto = DiagnosticResultSaveDTO(input_data={"area": 15})
    with pytest.raises(ConcurrencyConflictError):
        service.save_diagnostic_result(pid, dto, expected_version=1)


def test_save_diagnostic_result_raises_404_when_producer_not_found():
    mock_diagnostic_repo = MagicMock()
    mock_producer_repo = MagicMock()
    service = DiagnosticResultService(
        diagnostic_repo=mock_diagnostic_repo,
        producer_repo=mock_producer_repo,
    )

    pid = uuid.uuid4()
    mock_producer_repo.get_by_id.return_value = None

    dto = DiagnosticResultSaveDTO(input_data={"area": 15})
    with pytest.raises(NotFoundError) as exc_info:
        service.save_diagnostic_result(pid, dto, expected_version=None)

    assert "Producer" in str(exc_info.value)


def test_get_by_producer_id_found():
    mock_diagnostic_repo = MagicMock()
    mock_producer_repo = MagicMock()
    service = DiagnosticResultService(
        diagnostic_repo=mock_diagnostic_repo,
        producer_repo=mock_producer_repo,
    )

    pid = uuid.uuid4()
    existing_model = DiagnosticResult(
        producer_id=pid,
        input_data={"area": 10},
        diagnostico={"status": "ok"},
        simulacao=None,
        version=1,
        updated_at=datetime.now(timezone.utc),
    )
    mock_diagnostic_repo.get_by_producer_id.return_value = existing_model

    dto = service.get_by_producer_id(pid)
    assert dto.producer_id == pid
    assert dto.input_data == {"area": 10}
    assert dto.diagnostico == {"status": "ok"}


def test_get_by_producer_id_not_found():
    mock_diagnostic_repo = MagicMock()
    mock_producer_repo = MagicMock()
    service = DiagnosticResultService(
        diagnostic_repo=mock_diagnostic_repo,
        producer_repo=mock_producer_repo,
    )

    pid = uuid.uuid4()
    mock_diagnostic_repo.get_by_producer_id.return_value = None

    with pytest.raises(NotFoundError):
        service.get_by_producer_id(pid)
