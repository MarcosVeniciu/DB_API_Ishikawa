import importlib.util
from pathlib import Path
import uuid
from app.db.models import Consultant


def test_consultant_model_attributes():
    cid = uuid.uuid4()
    consultant = Consultant(
        id=cid,
        nome="Consultor Especialista",
        email="consultor@educampo.com.br",
        hashed_password="$2b$12$somehashvalue",
        version=1,
    )

    assert consultant.id == cid
    assert consultant.nome == "Consultor Especialista"
    assert consultant.email == "consultor@educampo.com.br"
    assert consultant.hashed_password == "$2b$12$somehashvalue"
    assert consultant.version == 1
    assert "Consultant" in repr(consultant)


def test_migration_001_metadata():
    migration_path = (
        Path(__file__).resolve().parent.parent.parent
        / "alembic"
        / "versions"
        / "001_initial_consultants.py"
    )
    assert migration_path.exists()

    spec = importlib.util.spec_from_file_location("migration_001", str(migration_path))
    assert spec is not None
    assert spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    assert mod.revision == "001_initial_consultants"
    assert mod.down_revision is None
