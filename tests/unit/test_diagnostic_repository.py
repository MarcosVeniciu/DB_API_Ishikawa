from datetime import datetime, timezone
from unittest.mock import MagicMock
import uuid
import pytest
from pydantic import ValidationError
from app.db.models import DiagnosticResult
from app.db.repositories.diagnostic_result_repo import DiagnosticResultRepository
from app.schemas.diagnostic_result import DiagnosticResultDTO, DiagnosticResultSaveDTO


def test_diagnostic_save_dto_valid():
    # Arrange & Act
    dto = DiagnosticResultSaveDTO(
        input_data={"area": 120.0, "safra": "2026/2027"},
        diagnostico={"potencial": "Alto", "gargalos": ["adubacao"]},
        simulacao={"cenario_base": {"retorno": 45000}},
    )

    # Assert
    assert dto.input_data == {"area": 120.0, "safra": "2026/2027"}
    assert dto.diagnostico["potencial"] == "Alto"
    assert dto.simulacao["cenario_base"]["retorno"] == 45000

    # Act - Optional fields omitted
    dto_minimal = DiagnosticResultSaveDTO(input_data={"area": 50.0})
    assert dto_minimal.input_data == {"area": 50.0}
    assert dto_minimal.diagnostico is None
    assert dto_minimal.simulacao is None


def test_diagnostic_save_dto_invalid_fields():
    # Missing input_data
    with pytest.raises(ValidationError):
        DiagnosticResultSaveDTO()  # type: ignore

    # Extra fields forbidden
    with pytest.raises(ValidationError):
        DiagnosticResultSaveDTO(
            input_data={"area": 50.0},
            campo_desconhecido="invalido",
        )


def test_diagnostic_dto_from_attributes():
    pid = uuid.uuid4()
    now = datetime.now(timezone.utc)
    model = DiagnosticResult(
        producer_id=pid,
        input_data={"coleta": "ok"},
        diagnostico={"analise": "concluida"},
        simulacao={"simulacao": "completa"},
        version=2,
        updated_at=now,
    )

    dto = DiagnosticResultDTO.model_validate(model)
    assert dto.producer_id == pid
    assert dto.input_data == {"coleta": "ok"}
    assert dto.diagnostico == {"analise": "concluida"}
    assert dto.simulacao == {"simulacao": "completa"}
    assert dto.version == 2
    assert dto.updated_at == now


def test_diagnostic_repo_create():
    mock_session = MagicMock()
    repo = DiagnosticResultRepository(mock_session)

    pid = uuid.uuid4()
    model = DiagnosticResult(
        producer_id=pid,
        input_data={"area": 10},
        version=1,
    )

    result = repo.create(model)

    mock_session.add.assert_called_once_with(model)
    mock_session.commit.assert_called_once()
    mock_session.refresh.assert_called_once_with(model)
    assert result == model


def test_diagnostic_repo_get_by_producer_id_found():
    mock_session = MagicMock()
    repo = DiagnosticResultRepository(mock_session)

    pid = uuid.uuid4()
    model = DiagnosticResult(producer_id=pid, input_data={"area": 10}, version=1)

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = model
    mock_session.execute.return_value = mock_result

    result = repo.get_by_producer_id(pid)
    assert result == model
    mock_session.execute.assert_called_once()


def test_diagnostic_repo_get_by_producer_id_not_found():
    mock_session = MagicMock()
    repo = DiagnosticResultRepository(mock_session)

    pid = uuid.uuid4()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    result = repo.get_by_producer_id(pid)
    assert result is None


def test_diagnostic_repo_update_atomic_success():
    mock_session = MagicMock()
    repo = DiagnosticResultRepository(mock_session)

    pid = uuid.uuid4()
    dto = DiagnosticResultSaveDTO(
        input_data={"area": 20},
        diagnostico={"status": "atualizado"},
    )

    updated_model = DiagnosticResult(
        producer_id=pid,
        input_data={"area": 20},
        diagnostico={"status": "atualizado"},
        version=2,
    )

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = updated_model
    mock_session.execute.return_value = mock_result

    result = repo.update_atomic(pid, dto, expected_version=1)

    assert result == updated_model
    mock_session.commit.assert_called_once()


def test_diagnostic_repo_update_atomic_conflict():
    mock_session = MagicMock()
    repo = DiagnosticResultRepository(mock_session)

    pid = uuid.uuid4()
    dto = DiagnosticResultSaveDTO(input_data={"area": 20})

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    result = repo.update_atomic(pid, dto, expected_version=1)

    assert result is None
    mock_session.commit.assert_not_called()


def test_diagnostic_repo_delete_success():
    mock_session = MagicMock()
    repo = DiagnosticResultRepository(mock_session)

    pid = uuid.uuid4()
    mock_result = MagicMock()
    mock_result.rowcount = 1
    mock_session.execute.return_value = mock_result

    result = repo.delete_by_producer_id(pid)

    assert result is True
    mock_session.commit.assert_called_once()


def test_diagnostic_repo_delete_not_found():
    mock_session = MagicMock()
    repo = DiagnosticResultRepository(mock_session)

    pid = uuid.uuid4()
    mock_result = MagicMock()
    mock_result.rowcount = 0
    mock_session.execute.return_value = mock_result

    result = repo.delete_by_producer_id(pid)

    assert result is False
    mock_session.commit.assert_not_called()
