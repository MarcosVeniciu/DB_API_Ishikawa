"""
Testes unitários para o importador de seed de dados mock (Lote 3).
Ref: Obsidian SDD [[sdd-db-api-seed-hardening]]
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import uuid
import pytest

from app.db.models import Consultant, Producer
from app.seed.import_farms import (
    DEFAULT_CONSULTANT_EMAIL,
    DEFAULT_CONSULTANT_ID,
    SeedSummaryDTO,
    load_farms_json,
    parse_farm_item,
    run_seed,
    seed_default_consultant,
)
from app.core.security import verify_password


def test_load_farms_json_valid(tmp_path: Path):
    """Valida leitura e parsing de arquivo farms.json válido."""
    # Arrange
    test_data = [{"nome": "Fazenda Alpha", "id_fazenda": str(uuid.uuid4())}]
    file_path = tmp_path / "test_farms.json"
    file_path.write_text(json.dumps(test_data), encoding="utf-8")

    # Act
    farms = load_farms_json(file_path)

    # Assert
    assert len(farms) == 1
    assert farms[0]["nome"] == "Fazenda Alpha"


def test_load_farms_json_file_not_found():
    """Valida que FileNotFoundError é lançado quando o arquivo não existe."""
    # Arrange
    invalid_path = Path("caminho/inexistente/farms.json")

    # Act & Assert
    with pytest.raises(FileNotFoundError):
        load_farms_json(invalid_path)


def test_parse_farm_item_with_complete_fields():
    """Valida mapeamento de item do farms.json com todos os campos presentes."""
    # Arrange
    farm_id = str(uuid.uuid4())
    raw_item = {
        "id_fazenda": farm_id,
        "nome": "Fazenda Modelo",
        "email": "modelo@educampo.com",
        "dados": {"total_vacas": 120},
    }
    consultant_id = uuid.uuid4()

    # Act
    parsed = parse_farm_item(raw_item, consultant_id)

    # Assert - AAA
    assert parsed["id"] == uuid.UUID(farm_id)
    assert parsed["nome"] == "Fazenda Modelo"
    assert parsed["email"] == "modelo@educampo.com"
    assert parsed["consultant_id"] == consultant_id
    assert parsed["dados"] == {"total_vacas": 120}
    assert parsed["id_fazenda"] == farm_id
    assert verify_password("produtor123", parsed["hashed_password"])


def test_parse_farm_item_fallback_email_and_id():
    """Valida fallback de e-mail determinístico e geração de UUID quando ausentes."""
    # Arrange
    raw_item = {
        "nome": "Fazenda Sem Email",
    }
    consultant_id = uuid.uuid4()

    # Act
    parsed = parse_farm_item(raw_item, consultant_id)

    # Assert - AAA
    assert isinstance(parsed["id"], uuid.UUID)
    assert parsed["email"] == f"{parsed['id']}@educampo.mock"
    assert parsed["id_fazenda"] == str(parsed["id"])
    assert parsed["dados"] == {}
    assert verify_password("produtor123", parsed["hashed_password"])


def test_seed_default_consultant_creates_when_missing():
    """Valida criação do consultor padrão quando ele não existe no banco."""
    # Arrange
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None

    # Act
    consultant_id = seed_default_consultant(mock_db)

    # Assert
    assert consultant_id == DEFAULT_CONSULTANT_ID
    assert mock_db.add.called
    assert mock_db.flush.called
    added_obj = mock_db.add.call_args[0][0]
    assert isinstance(added_obj, Consultant)
    assert added_obj.id == DEFAULT_CONSULTANT_ID
    assert added_obj.email == DEFAULT_CONSULTANT_EMAIL
    assert verify_password("admin123", added_obj.hashed_password)


def test_seed_default_consultant_reuses_existing():
    """Valida que o consultor padrão existente é reutilizado sem duplicação."""
    # Arrange
    mock_db = MagicMock()
    existing_consultant = Consultant(
        id=DEFAULT_CONSULTANT_ID,
        nome="Consultor Educampo",
        email=DEFAULT_CONSULTANT_EMAIL,
        hashed_password="hash",
    )
    mock_db.query.return_value.filter.return_value.first.return_value = existing_consultant

    # Act
    consultant_id = seed_default_consultant(mock_db)

    # Assert
    assert consultant_id == DEFAULT_CONSULTANT_ID
    assert not mock_db.add.called


@patch("app.seed.import_farms.load_farms_json")
@patch("app.seed.import_farms.seed_default_consultant")
def test_run_seed_orchestration(mock_seed_consultant, mock_load_json):
    """Valida orquestração completa do seed retornando SeedSummaryDTO."""
    # Arrange
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None
    mock_db.execute.return_value.rowcount = 1
    consultant_id = uuid.uuid4()
    mock_seed_consultant.return_value = consultant_id
    mock_load_json.return_value = [
        {"nome": "F1", "id_fazenda": str(uuid.uuid4())},
        {"nome": "F2", "id_fazenda": str(uuid.uuid4())},
    ]

    # Act
    summary = run_seed(mock_db, "app/resources/test_data/farms.json")

    # Assert - AAA
    assert isinstance(summary, SeedSummaryDTO)
    assert summary.total_farms_processed == 2
    assert mock_db.execute.called
    assert mock_db.commit.called
