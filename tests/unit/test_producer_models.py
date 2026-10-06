import importlib.util
from pathlib import Path
import uuid
from sqlalchemy import Index, inspect
from app.db.models import Consultant, Producer


def test_producer_model_attributes_and_relationships():
    # Arrange
    pid = uuid.uuid4()
    cid = uuid.uuid4()
    dados_mock = {"hectares": 150.5, "cultura": "Café Conilon"}

    # Act
    producer = Producer(
        id=pid,
        email="produtor.teste@educampo.com.br",
        hashed_password="$2b$12$hashedpwdexample",
        nome="Fazenda Santa Rita",
        id_fazenda="FAZ-001",
        dados=dados_mock,
        consultant_id=cid,
        version=1,
    )

    # Assert - AAA
    assert producer.id == pid
    assert producer.email == "produtor.teste@educampo.com.br"
    assert producer.hashed_password == "$2b$12$hashedpwdexample"
    assert producer.nome == "Fazenda Santa Rita"
    assert producer.id_fazenda == "FAZ-001"
    assert producer.dados == dados_mock
    assert producer.consultant_id == cid
    assert producer.version == 1
    assert "Producer" in repr(producer)


def test_producer_table_metadata_and_constraints():
    mapper = inspect(Producer)
    columns = {col.key: col for col in mapper.columns}

    # Verify column existence and nullable constraints
    assert "id" in columns
    assert not columns["id"].nullable

    assert "email" in columns
    assert not columns["email"].nullable
    assert columns["email"].unique

    assert "hashed_password" in columns
    assert not columns["hashed_password"].nullable

    assert "nome" in columns
    assert not columns["nome"].nullable

    assert "id_fazenda" in columns
    assert columns["id_fazenda"].nullable

    assert "dados" in columns
    assert not columns["dados"].nullable

    assert "consultant_id" in columns
    assert columns["consultant_id"].nullable

    assert "version" in columns
    assert not columns["version"].nullable

    # Verify foreign key constraint on consultant_id
    fks = list(columns["consultant_id"].foreign_keys)
    assert len(fks) == 1
    fk = fks[0]
    assert fk.target_fullname == "consultants.id"
    assert fk.ondelete == "SET NULL"

    # Verify index on lower(nome) or consultant_id
    table = Producer.__table__
    index_names = {idx.name for idx in table.indexes}
    assert "ix_producers_consultant_id" in index_names or any(
        "consultant_id" in [c.name for c in idx.columns] for idx in table.indexes
    )


def test_consultant_has_producers_relationship():
    mapper = inspect(Consultant)
    assert "producers" in mapper.relationships
    rel = mapper.relationships["producers"]
    assert rel.target.name == "producers"


def test_migration_002_metadata():
    migration_path = (
        Path(__file__).resolve().parent.parent.parent
        / "alembic"
        / "versions"
        / "002_add_producers.py"
    )
    assert migration_path.exists(), "Migration 002_add_producers.py must exist"

    spec = importlib.util.spec_from_file_location("migration_002", str(migration_path))
    assert spec is not None
    assert spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    assert mod.revision == "002_add_producers"
    assert mod.down_revision == "001_initial_consultants"
    assert hasattr(mod, "upgrade")
    assert hasattr(mod, "downgrade")
