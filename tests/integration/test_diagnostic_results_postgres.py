from datetime import datetime, timezone
from pathlib import Path
import time
import uuid
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from testcontainers.postgres import PostgresContainer

from app.core.config import settings
from app.db.models import DiagnosticResult
from app.db.session import get_db
from app.main import app

AUTH_HEADERS = {"X-Service-Token": settings.SERVICE_TOKEN}


@pytest.fixture(scope="module")
def postgres_container():
    """Conecta a uma instância PostgreSQL existente via TEST_DATABASE_URL ou sobe container via testcontainers."""
    import os

    test_db_url = os.getenv("TEST_DATABASE_URL")
    if test_db_url:
        normalized_url = (
            test_db_url.replace("postgresql://", "postgresql+psycopg://")
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
        return

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
def pg_session(postgres_container):
    """Cria uma sessão SQLAlchemy conectada ao container PostgreSQL."""
    engine = create_engine(postgres_container)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def client(postgres_container):
    """Fornece TestClient com override de get_db para o PostgreSQL do container."""
    engine = create_engine(postgres_container)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    engine.dispose()


def _create_helper_producer(client: TestClient) -> uuid.UUID:
    """Helper para criar consultor e produtor válidos no banco de testes."""
    cid = uuid.uuid4()
    c_resp = client.post(
        "/v1/consultants",
        json={
            "id": str(cid),
            "nome": "Consultor Teste Diagnostico",
            "email": f"consultor_{cid.hex[:8]}@educampo.com.br",
            "password": "SenhaSegura123",
        },
        headers=AUTH_HEADERS,
    )
    assert c_resp.status_code == 201

    pid = uuid.uuid4()
    p_resp = client.post(
        "/v1/producers",
        json={
            "id": str(pid),
            "nome": "Produtor Teste Diagnostico",
            "email": f"produtor_{pid.hex[:8]}@educampo.com.br",
            "password": "SenhaProdutor123",
            "consultant_id": str(cid),
            "dados": {"area_total": 250.0},
        },
        headers=AUTH_HEADERS,
    )
    assert p_resp.status_code == 201
    return pid


def test_scenario_1_save_diagnostic_creates_new_record_201(client, pg_session):
    """Cenário 1: Primeiro salvamento de diagnóstico para produtor cadastrado retorna 201 Created."""
    pid = _create_helper_producer(client)

    payload = {
        "input_data": {"cultura": "Café", "area": 120.0, "produtividade_estimada": 35.5},
        "diagnostico": {"status": "adequado", "pontos_atencao": ["adubacao"]},
        "simulacao": {"lucro_estimado": 125000.0, "roi": 18.2},
    }

    response = client.put(
        f"/v1/diagnostic-results/{pid}",
        json=payload,
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["producer_id"] == str(pid)
    assert data["input_data"] == payload["input_data"]
    assert data["diagnostico"] == payload["diagnostico"]
    assert data["simulacao"] == payload["simulacao"]
    assert data["version"] == 1
    assert data["updated_at"] is not None

    # Verificação direta no PostgreSQL
    db_record = pg_session.scalar(
        select(DiagnosticResult).where(DiagnosticResult.producer_id == pid)
    )
    assert db_record is not None
    assert db_record.version == 1
    assert db_record.input_data["cultura"] == "Café"


def test_scenario_2_update_diagnostic_with_if_match_updates_200(client, pg_session):
    """Cenário 2: Atualização de diagnóstico com If-Match contendo versão atual retorna 200 OK e version=2."""
    pid = _create_helper_producer(client)

    # 1. Cria versão inicial 1
    initial_payload = {
        "input_data": {"area": 80.0},
        "diagnostico": {"status": "inicial"},
    }
    create_resp = client.put(
        f"/v1/diagnostic-results/{pid}",
        json=initial_payload,
        headers=AUTH_HEADERS,
    )
    assert create_resp.status_code == 201
    assert create_resp.json()["version"] == 1

    # 2. Atualiza enviando If-Match: "1"
    update_payload = {
        "input_data": {"area": 95.0},
        "diagnostico": {"status": "revisado", "recomendacao": "correcao_solo"},
        "simulacao": {"novo_custo": 45000.0},
    }
    update_headers = {**AUTH_HEADERS, "If-Match": "1"}

    update_resp = client.put(
        f"/v1/diagnostic-results/{pid}",
        json=update_payload,
        headers=update_headers,
    )

    assert update_resp.status_code == 200
    data = update_resp.json()
    assert data["producer_id"] == str(pid)
    assert data["version"] == 2
    assert data["input_data"]["area"] == 95.0
    assert data["diagnostico"]["status"] == "revisado"
    assert data["simulacao"]["novo_custo"] == 45000.0

    # Verificação direta no PostgreSQL
    db_record = pg_session.scalar(
        select(DiagnosticResult).where(DiagnosticResult.producer_id == pid)
    )
    assert db_record is not None
    assert db_record.version == 2


def test_scenario_3_update_diagnostic_divergent_version_returns_412(client, pg_session):
    """Cenário 3: Atualização concorrente com If-Match divergente retorna 412 Precondition Failed."""
    pid = _create_helper_producer(client)

    # Cria versão 1
    client.put(
        f"/v1/diagnostic-results/{pid}",
        json={"input_data": {"area": 50.0}},
        headers=AUTH_HEADERS,
    )

    # Tenta atualizar com If-Match: "99"
    headers_conflict = {**AUTH_HEADERS, "If-Match": "99"}
    response = client.put(
        f"/v1/diagnostic-results/{pid}",
        json={"input_data": {"area": 60.0}},
        headers=headers_conflict,
    )

    assert response.status_code == 412
    assert response.headers["content-type"].startswith("application/problem+json")
    problem = response.json()
    assert problem["type"] == "version-mismatch"
    assert problem["status"] == 412

    # Verifica que banco permanece inalterado
    db_record = pg_session.scalar(
        select(DiagnosticResult).where(DiagnosticResult.producer_id == pid)
    )
    assert db_record.version == 1
    assert db_record.input_data["area"] == 50.0


def test_scenario_4_update_diagnostic_missing_if_match_returns_428(client, pg_session):
    """Cenário 4: Atualização de diagnóstico existente sem If-Match retorna 428 Precondition Required."""
    pid = _create_helper_producer(client)

    # Cria versão 1
    client.put(
        f"/v1/diagnostic-results/{pid}",
        json={"input_data": {"area": 40.0}},
        headers=AUTH_HEADERS,
    )

    # Atualiza sem passar If-Match
    response = client.put(
        f"/v1/diagnostic-results/{pid}",
        json={"input_data": {"area": 70.0}},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 428
    assert response.headers["content-type"].startswith("application/problem+json")
    problem = response.json()
    assert problem["type"] == "precondition-required"
    assert problem["status"] == 428


def test_scenario_5_save_diagnostic_nonexistent_producer_returns_404(client):
    """Cenário 5: Tentativa de salvar diagnóstico para produtor inexistente retorna 404 Not Found."""
    non_existent_pid = uuid.uuid4()

    response = client.put(
        f"/v1/diagnostic-results/{non_existent_pid}",
        json={"input_data": {"area": 10.0}},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    problem = response.json()
    assert problem["type"] == "not-found"
    assert problem["status"] == 404


def test_scenario_6_get_diagnostic_result_found_200(client):
    """Cenário 6: GET retorna 200 OK com payload estruturado completo para diagnóstico existente."""
    pid = _create_helper_producer(client)

    payload = {
        "input_data": {"area": 300.0, "cultura": "Soja"},
        "diagnostico": {"avaliacao": "excelente"},
        "simulacao": {"margem": 32.5},
    }
    client.put(
        f"/v1/diagnostic-results/{pid}",
        json=payload,
        headers=AUTH_HEADERS,
    )

    response = client.get(
        f"/v1/diagnostic-results/{pid}",
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["producer_id"] == str(pid)
    assert data["input_data"] == payload["input_data"]
    assert data["diagnostico"] == payload["diagnostico"]
    assert data["simulacao"] == payload["simulacao"]
    assert data["version"] == 1


def test_scenario_7_get_diagnostic_result_not_found_404(client):
    """Cenário 7: GET para produtor cadastrado mas sem diagnóstico retorna 404 Not Found."""
    pid = _create_helper_producer(client)

    response = client.get(
        f"/v1/diagnostic-results/{pid}",
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    problem = response.json()
    assert problem["type"] == "not-found"
    assert problem["status"] == 404


def test_scenario_8_delete_producer_cascade_deletes_diagnostic(client, pg_session):
    """Cenário 8: Exclusão do produtor remove em cascata o registro na tabela diagnostic_results."""
    pid = _create_helper_producer(client)

    # Cria diagnóstico associado
    client.put(
        f"/v1/diagnostic-results/{pid}",
        json={"input_data": {"area": 110.0}},
        headers=AUTH_HEADERS,
    )

    # Confirma existência no PostgreSQL
    db_record = pg_session.scalar(
        select(DiagnosticResult).where(DiagnosticResult.producer_id == pid)
    )
    assert db_record is not None

    # Exclui produtor via DELETE /v1/producers/{producer_id}
    del_resp = client.delete(f"/v1/producers/{pid}", headers=AUTH_HEADERS)
    assert del_resp.status_code == 204

    # Confirma que GET no diagnóstico agora retorna 404
    get_resp = client.get(f"/v1/diagnostic-results/{pid}", headers=AUTH_HEADERS)
    assert get_resp.status_code == 404

    # Expira a sessão do SQLAlchemy para ler o estado atual do banco
    pg_session.expire_all()
    db_record_after = pg_session.scalar(
        select(DiagnosticResult).where(DiagnosticResult.producer_id == pid)
    )
    assert db_record_after is None, "Registro de diagnóstico deve ter sido removido por ON DELETE CASCADE"


def test_scenario_9_auth_security_checks_401(client):
    """Cenário 9: Acesso sem token ou com token inválido retorna 401 Unauthorized."""
    pid = uuid.uuid4()

    # GET sem token
    resp_no_token = client.get(f"/v1/diagnostic-results/{pid}")
    assert resp_no_token.status_code == 401
    assert resp_no_token.json()["type"] == "unauthorized"

    # PUT com token errado
    resp_bad_token = client.put(
        f"/v1/diagnostic-results/{pid}",
        json={"input_data": {"area": 10.0}},
        headers={"X-Service-Token": "token-invalido"},
    )
    assert resp_bad_token.status_code == 401
    assert resp_bad_token.json()["type"] == "unauthorized"


def test_scenario_10_validation_error_returns_422(client):
    """Cenário 10: Envio de payload inválido (sem input_data) retorna 422 Unprocessable Entity."""
    pid = uuid.uuid4()

    response = client.put(
        f"/v1/diagnostic-results/{pid}",
        json={"diagnostico": {"obs": "sem input_data"}},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    problem = response.json()
    assert problem["type"] == "validation-error"
