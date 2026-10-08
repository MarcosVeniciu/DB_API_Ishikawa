import importlib.util
from pathlib import Path
import uuid
from sqlalchemy import inspect
from app.db.models import DiagnosticResult, Producer


def test_diagnostic_result_model_attributes_and_relationships():
    # Arrange
    pid = uuid.uuid4()
    input_data = {"area_total": 45.0, "producao_anual": 1200}
    diagnostico = {"score": 8.5, "status": "Excelente"}
    simulacao = {"cenario_otimista": {"lucro": 150000}}

    # Act
    result = DiagnosticResult(
        producer_id=pid,
        input_data=input_data,
        diagnostico=diagnostico,
        simulacao=simulacao,
        version=1,
    )

    # Assert - AAA
    assert result.producer_id == pid
    assert result.input_data == input_data
    assert result.diagnostico == diagnostico
    assert result.simulacao == simulacao
    assert result.version == 1
    assert "DiagnosticResult" in repr(result)


def test_diagnostic_result_table_metadata_and_constraints():
    mapper = inspect(DiagnosticResult)
    columns = {col.key: col for col in mapper.columns}

    # Verify column existence and constraints
    assert "producer_id" in columns
    assert not columns["producer_id"].nullable
    assert columns["producer_id"].primary_key

    assert "input_data" in columns
    assert not columns["input_data"].nullable

    assert "diagnostico" in columns
    assert columns["diagnostico"].nullable

    assert "simulacao" in columns
    assert columns["simulacao"].nullable

    assert "version" in columns
    assert not columns["version"].nullable

    assert "updated_at" in columns
    assert not columns["updated_at"].nullable

    # Verify foreign key constraint on producer_id with ON DELETE CASCADE
    fks = list(columns["producer_id"].foreign_keys)
    assert len(fks) == 1
    fk = fks[0]
    assert fk.target_fullname == "producers.id"
    assert fk.ondelete == "CASCADE"


def test_producer_has_diagnostic_result_relationship():
    mapper = inspect(Producer)
    assert "diagnostic_result" in mapper.relationships
    rel = mapper.relationships["diagnostic_result"]
    assert rel.target.name == "diagnostic_results"
    assert not rel.uselist


def test_migration_003_metadata():
    migration_path = (
        Path(__file__).resolve().parent.parent.parent
        / "alembic"
        / "versions"
        / "003_add_diagnostic_results.py"
    )
    assert migration_path.exists(), "Migration 003_add_diagnostic_results.py must exist"

    spec = importlib.util.spec_from_file_location("migration_003", str(migration_path))
    assert spec is not None
    assert spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    assert mod.revision == "003_add_diagnostic_results"
    assert mod.down_revision == "002_add_producers"
    assert hasattr(mod, "upgrade")
    assert hasattr(mod, "downgrade")
