from pathlib import Path
import uuid
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from testcontainers.postgres import PostgresContainer

from app.core.config import settings
from app.db.session import get_db
from app.main import app

AUTH_HEADERS = {"X-Service-Token": settings.SERVICE_TOKEN}


@pytest.fixture(scope="module")
def postgres_container():
    """Sobe container PostgreSQL 16 isolado via testcontainers com migrations aplicadas."""
    with PostgresContainer("postgres:16-alpine") as postgres:
        raw_url = postgres.get_connection_url()
        normalized_url = (
            raw_url.replace("postgresql://", "postgresql+psycopg://")
            .replace("postgresql+psycopg2://", "postgresql+psycopg://")
        )

        engine = create_engine(normalized_url)
        alembic_ini_path = (
            Path(__file__).resolve().parent.parent.parent / "alembic.ini"
        )
        alembic_cfg = Config(str(alembic_ini_path))
        alembic_cfg.set_main_option("sqlalchemy.url", normalized_url)
        with engine.begin() as conn:
            alembic_cfg.attributes["connection"] = conn
            command.upgrade(alembic_cfg, "head")
        engine.dispose()

        yield normalized_url


@pytest.fixture
def client(postgres_container):
    """TestClient apontando para o PostgreSQL real do testcontainer."""
    engine = create_engine(postgres_container)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def _override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    engine.dispose()


def test_change_password_producer_postgres_end_to_end(client):
    # 1. Cria um produtor com senha inicial
    producer_id = str(uuid.uuid4())
    create_payload = {
        "id": producer_id,
        "email": f"produtor_{uuid.uuid4().hex[:6]}@educampo.com.br",
        "password": "senhaInicial123",
        "nome": "Fazenda Modelo Conexão Real",
        "id_fazenda": "FAZ-REAL-01",
        "dados": {"total_vacas": 85},
    }
    res_create = client.post("/v1/producers", json=create_payload, headers=AUTH_HEADERS)
    assert res_create.status_code == 201

    # 2. Valida login com a senha inicial
    verify_payload = {
        "email": create_payload["email"],
        "password": "senhaInicial123",
        "role": "producer",
    }
    res_verify_old = client.post("/v1/auth/verify", json=verify_payload, headers=AUTH_HEADERS)
    assert res_verify_old.status_code == 200
    assert res_verify_old.json()["id"] == producer_id

    # 3. Altera a senha via POST /v1/auth/password
    change_payload = {
        "role": "producer",
        "id": producer_id,
        "current_password": "senhaInicial123",
        "new_password": "senhaNovaSuperSegura456",
    }
    res_change = client.post("/v1/auth/password", json=change_payload, headers=AUTH_HEADERS)
    assert res_change.status_code == 200
    data_change = res_change.json()
    assert data_change["id"] == producer_id
    assert data_change["role"] == "producer"
    assert "sucesso" in data_change["message"]

    # 4. Verifica que login com a senha antiga agora é REJEITADO (401)
    res_verify_failed = client.post("/v1/auth/verify", json=verify_payload, headers=AUTH_HEADERS)
    assert res_verify_failed.status_code == 401

    # 5. Verifica que login com a nova senha é ACEITO (200)
    verify_new_payload = {
        "email": create_payload["email"],
        "password": "senhaNovaSuperSegura456",
        "role": "producer",
    }
    res_verify_success = client.post("/v1/auth/verify", json=verify_new_payload, headers=AUTH_HEADERS)
    assert res_verify_success.status_code == 200
    assert res_verify_success.json()["id"] == producer_id


def test_change_password_consultant_postgres_end_to_end(client):
    # 1. Cria consultor com senha inicial
    consultant_id = str(uuid.uuid4())
    cons_email = f"consultor_{uuid.uuid4().hex[:6]}@educampo.com.br"
    create_payload = {
        "id": consultant_id,
        "nome": "Consultor Agronômico Sênior",
        "email": cons_email,
        "password": "consSecret123",
    }
    res_create = client.post("/v1/consultants", json=create_payload, headers=AUTH_HEADERS)
    assert res_create.status_code == 201

    # 2. Altera a senha utilizando o e-mail como identificador
    change_payload = {
        "role": "consultant",
        "email": cons_email,
        "current_password": "consSecret123",
        "new_password": "consSecretNovaSenha999",
    }
    res_change = client.post("/v1/auth/password", json=change_payload, headers=AUTH_HEADERS)
    assert res_change.status_code == 200
    assert res_change.json()["id"] == consultant_id

    # 3. Verifica credencial nova
    verify_new = {
        "email": cons_email,
        "password": "consSecretNovaSenha999",
        "role": "consultant",
    }
    res_verify = client.post("/v1/auth/verify", json=verify_new, headers=AUTH_HEADERS)
    assert res_verify.status_code == 200


def test_change_password_rejects_wrong_current_password_in_postgres(client):
    # 1. Cria consultor
    cid = str(uuid.uuid4())
    email = f"cons_err_{uuid.uuid4().hex[:6]}@educampo.com.br"
    client.post(
        "/v1/consultants",
        json={"id": cid, "nome": "Consultor Erro", "email": email, "password": "senhaCorreta"},
        headers=AUTH_HEADERS,
    )

    # 2. Tenta trocar com senha atual incorreta
    change_payload = {
        "role": "consultant",
        "id": cid,
        "current_password": "senhaIncorretaDigitada",
        "new_password": "novaSenhaPretendida",
    }
    res_change = client.post("/v1/auth/password", json=change_payload, headers=AUTH_HEADERS)
    assert res_change.status_code == 401
    assert res_change.json()["type"] == "invalid-credentials"

    # 3. Verifica que a senha original continua intacta
    res_verify = client.post(
        "/v1/auth/verify",
        json={"email": email, "password": "senhaCorreta", "role": "consultant"},
        headers=AUTH_HEADERS,
    )
    assert res_verify.status_code == 200
