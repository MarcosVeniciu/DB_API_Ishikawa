from pathlib import Path
import uuid
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from testcontainers.postgres import PostgresContainer

from app.core.config import settings
from app.db.models import Consultant
from app.db.session import get_db
from app.main import app

AUTH_HEADERS = {"X-Service-Token": settings.SERVICE_TOKEN}


@pytest.fixture(scope="module")
def postgres_container():
    """Sobe um container PostgreSQL 16 isolado via testcontainers."""
    with PostgresContainer("postgres:16-alpine") as postgres:
        raw_url = postgres.get_connection_url()
        # Normaliza driver para psycopg (v3)
        normalized_url = (
            raw_url.replace("postgresql://", "postgresql+psycopg://")
            .replace("postgresql+psycopg2://", "postgresql+psycopg://")
        )

        engine = create_engine(normalized_url)
        # Executa migrações Alembic no banco temporário usando a conexão aberta
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
    """Cria uma sessão SQLAlchemy conectada ao container de teste."""
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


def test_scenario_10_health_ready_connected_to_postgres(client):
    """Cenário 10: GET /health/ready com PostgreSQL ativo retorna HTTP 200."""
    response = client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["database"] == "connected"


def test_scenario_1_create_consultant_success(client, pg_session):
    """Cenário 1: Criar consultor retorna 201 sem expor hashed_password."""
    cid = uuid.uuid4()
    email = f"consultor_{cid.hex[:8]}@educampo.com.br"
    payload = {
        "id": str(cid),
        "nome": "Consultor Testcontainers",
        "email": email,
        "password": "SenhaSegura123",
    }

    response = client.post("/v1/consultants", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 201

    data = response.json()
    assert data["id"] == str(cid)
    assert data["nome"] == "Consultor Testcontainers"
    assert data["email"] == email
    assert data["version"] == 1
    assert data["producers_managed"] == []
    assert "password" not in data
    assert "hashed_password" not in data

    # Valida persistência direta no PostgreSQL real
    db_consultant = pg_session.execute(
        select(Consultant).where(Consultant.id == cid)
    ).scalar_one_or_none()
    assert db_consultant is not None
    assert db_consultant.hashed_password != "SenhaSegura123"
    assert db_consultant.hashed_password.startswith("$2b$")


def test_scenario_2_duplicate_email_citext(client):
    """Cenário 2: E-mail duplicado (mesmo variando case com CITEXT) retorna HTTP 409."""
    email = "consultor.citext@educampo.com.br"
    client.post(
        "/v1/consultants",
        json={"nome": "Primeiro", "email": email, "password": "Senha123"},
        headers=AUTH_HEADERS,
    )

    # Tenta cadastrar com caixa alta
    response = client.post(
        "/v1/consultants",
        json={"nome": "Segundo", "email": email.upper(), "password": "OutraSenha123"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 409
    assert response.headers["content-type"].startswith("application/problem+json")
    data = response.json()
    assert data["type"] == "conflict-email"


def test_scenario_3_and_4_auth_verify(client):
    """Cenários 3 e 4: POST /v1/auth/verify sucesso (200) e falha idêntica (401)."""
    email = "auth.verify@educampo.com.br"
    password = "MinhaSenhaReal@2026"
    create_resp = client.post(
        "/v1/consultants",
        json={"nome": "Consultor Auth", "email": email, "password": password},
        headers=AUTH_HEADERS,
    )
    cid = create_resp.json()["id"]

    # Sucesso
    resp_ok = client.post(
        "/v1/auth/verify",
        json={"email": email, "password": password, "role": "consultant"},
        headers=AUTH_HEADERS,
    )
    assert resp_ok.status_code == 200
    assert resp_ok.json() == {"id": cid, "role": "consultant"}

    # Senha incorreta -> 401
    resp_wrong_pw = client.post(
        "/v1/auth/verify",
        json={"email": email, "password": "SenhaErrada", "role": "consultant"},
        headers=AUTH_HEADERS,
    )
    assert resp_wrong_pw.status_code == 401
    assert resp_wrong_pw.headers["content-type"].startswith("application/problem+json")
    assert resp_wrong_pw.json()["type"] == "invalid-credentials"

    # E-mail inexistente -> 401 idêntico
    resp_no_user = client.post(
        "/v1/auth/verify",
        json={"email": "fantasma@educampo.com.br", "password": password, "role": "consultant"},
        headers=AUTH_HEADERS,
    )
    assert resp_no_user.status_code == 401
    assert resp_no_user.json()["type"] == "invalid-credentials"


def test_scenario_5_and_6_optimistic_locking(client):
    """Cenários 5 e 6: PUT /v1/consultants/{id} com If-Match e detecção de conflito 412."""
    create_resp = client.post(
        "/v1/consultants",
        json={"nome": "Antes do Update", "email": "lock@educampo.com.br", "password": "Senha123"},
        headers=AUTH_HEADERS,
    )
    cid = create_resp.json()["id"]

    # 1. Update bem-sucedido com If-Match: 1 -> version passa para 2
    headers_v1 = {**AUTH_HEADERS, "If-Match": "1"}
    resp_update = client.put(
        f"/v1/consultants/{cid}",
        json={"nome": "Nome Versao 2"},
        headers=headers_v1,
    )
    assert resp_update.status_code == 200
    data_v2 = resp_update.json()
    assert data_v2["nome"] == "Nome Versao 2"
    assert data_v2["version"] == 2

    # 2. Concorrência: outro cliente tenta atualizar com If-Match: 1 (desatualizado) -> 412
    resp_conflict = client.put(
        f"/v1/consultants/{cid}",
        json={"nome": "Tentativa Invalida"},
        headers=headers_v1,
    )
    assert resp_conflict.status_code == 412
    assert resp_conflict.headers["content-type"].startswith("application/problem+json")
    assert resp_conflict.json()["type"] == "version-mismatch"

    # Confirma que o dado no banco permaneceu inalterado
    get_resp = client.get(f"/v1/consultants/{cid}", headers=AUTH_HEADERS)
    assert get_resp.json()["nome"] == "Nome Versao 2"
    assert get_resp.json()["version"] == 2


def test_scenario_7_unauthorized_without_token(client):
    """Cenário 7: Requisição sem X-Service-Token retorna HTTP 401."""
    resp = client.get("/v1/consultants")
    assert resp.status_code == 401
    assert resp.headers["content-type"].startswith("application/problem+json")
    assert resp.json()["type"] == "unauthorized"


def test_scenario_8_and_9_pagination_limits(client):
    """Cenários 8 e 9: Listagem paginada com X-Total-Count e rejeição de limit > 200."""
    # Listagem válida
    resp = client.get("/v1/consultants?limit=2&offset=0", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    assert "X-Total-Count" in resp.headers
    total = int(resp.headers["X-Total-Count"])
    assert total >= 1
    assert len(resp.json()) <= 2

    # Excedendo limite máximo de 200 registros -> 422
    resp_exceeded = client.get("/v1/consultants?limit=201", headers=AUTH_HEADERS)
    assert resp_exceeded.status_code == 422
    assert resp_exceeded.headers["content-type"].startswith("application/problem+json")
    assert resp_exceeded.json()["type"] == "validation-error"
