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
from app.db.models import Consultant, Producer
from app.db.session import get_db
from app.main import app

AUTH_HEADERS = {"X-Service-Token": settings.SERVICE_TOKEN}


@pytest.fixture(scope="module")
def postgres_container():
    """Sobe um container PostgreSQL 16 isolado via testcontainers e executa Alembic head."""
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


def test_scenario_1_create_producer_success(client, pg_session):
    """Cenário 1: Cadastro bem-sucedido de novo produtor com dados JSONB e vínculo com consultor."""
    # 1. Cria um consultor
    cid = uuid.uuid4()
    c_resp = client.post(
        "/v1/consultants",
        json={
            "id": str(cid),
            "nome": "Consultor Responsável",
            "email": f"consultor_{cid.hex[:8]}@educampo.com.br",
            "password": "SenhaSegura123",
        },
        headers=AUTH_HEADERS,
    )
    assert c_resp.status_code == 201

    # 2. Cria produtor vinculado ao consultor com dados JSONB
    pid = uuid.uuid4()
    email = "fazenda.sol@educampo.com.br"
    dados = {
        "cultura_principal": "Café Arábica",
        "area_hectares": 180.5,
        "cooperativa": "Cooxupé",
    }
    payload = {
        "id": str(pid),
        "nome": "Fazenda Sol",
        "email": email,
        "password": "Produtor@123",
        "id_fazenda": "FZ-01",
        "dados": dados,
        "consultant_id": str(cid),
    }

    response = client.post("/v1/producers", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 201
    data = response.json()

    assert data["id"] == str(pid)
    assert data["nome"] == "Fazenda Sol"
    assert data["email"] == email
    assert data["id_fazenda"] == "FZ-01"
    assert data["dados"] == dados
    assert data["consultant_id"] == str(cid)
    assert data["version"] == 1
    assert "password" not in data
    assert "hashed_password" not in data

    # Verifica persistência real no PostgreSQL
    db_producer = pg_session.execute(
        select(Producer).where(Producer.id == pid)
    ).scalar_one_or_none()
    assert db_producer is not None
    assert db_producer.dados == dados
    assert db_producer.hashed_password != "Produtor@123"
    assert db_producer.hashed_password.startswith("$2b$")


def test_scenario_2_duplicate_email_citext(client):
    """Cenário 2: Rejeição de cadastro com e-mail duplicado (Case Insensitive via CITEXT)."""
    email = "fazenda.unicidade@educampo.com.br"
    resp1 = client.post(
        "/v1/producers",
        json={"nome": "Fazenda A", "email": email, "password": "SenhaProdutor123"},
        headers=AUTH_HEADERS,
    )
    assert resp1.status_code == 201

    # Tenta criar com caixa alta
    resp2 = client.post(
        "/v1/producers",
        json={"nome": "Fazenda B", "email": email.upper(), "password": "OutraSenha123"},
        headers=AUTH_HEADERS,
    )
    assert resp2.status_code == 409
    assert resp2.headers["content-type"].startswith("application/problem+json")
    data = resp2.json()
    assert data["type"] == "conflict-email"


def test_scenario_3_deterministic_find_by_name(client, pg_session):
    """Cenário 3: Busca determinística de produtor por nome retornando o registro mais antigo."""
    nome_comum = "Fazenda Boa Vista"
    id1 = uuid.uuid4()
    id2 = uuid.uuid4()

    # Cria primeiro registro
    p1 = Producer(
        id=id1,
        email="antigo@boavista.com.br",
        hashed_password="hash",
        nome=nome_comum,
        version=1,
        created_at=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
        updated_at=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
    )
    pg_session.add(p1)
    pg_session.commit()

    # Cria segundo registro mais recente
    p2 = Producer(
        id=id2,
        email="recente@boavista.com.br",
        hashed_password="hash",
        nome=nome_comum,
        version=1,
        created_at=datetime(2025, 1, 2, 10, 0, tzinfo=timezone.utc),
        updated_at=datetime(2025, 1, 2, 10, 0, tzinfo=timezone.utc),
    )
    pg_session.add(p2)
    pg_session.commit()

    # Busca informando o parâmetro de nome com caixa alternada
    resp = client.get(f"/v1/producers?nome={nome_comum.upper()}", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) >= 2
    # O primeiro registro ordenado deve ser o mais antigo
    assert items[0]["id"] == str(id1)
    assert items[0]["email"] == "antigo@boavista.com.br"


def test_scenario_4_and_5_get_by_id(client):
    """Cenários 4 e 5: Consulta por ID existente (200) e inexistente (404)."""
    pid = uuid.uuid4()
    create_resp = client.post(
        "/v1/producers",
        json={"id": str(pid), "nome": "Fazenda Consulta", "email": f"consulta_{pid.hex[:6]}@educampo.com.br", "password": "SenhaValida123"},
        headers=AUTH_HEADERS,
    )
    assert create_resp.status_code == 201

    # ID existente
    get_ok = client.get(f"/v1/producers/{pid}", headers=AUTH_HEADERS)
    assert get_ok.status_code == 200
    data = get_ok.json()
    assert data["id"] == str(pid)
    assert "hashed_password" not in data

    # ID inexistente
    get_404 = client.get(f"/v1/producers/{uuid.uuid4()}", headers=AUTH_HEADERS)
    assert get_404.status_code == 404
    assert get_404.headers["content-type"].startswith("application/problem+json")
    assert get_404.json()["type"] == "not-found"


def test_scenario_6_and_7_optimistic_locking(client):
    """Cenários 6 e 7: Atualização com If-Match válida (200) e bloqueio por conflito (412)."""
    pid = uuid.uuid4()
    original_email = f"lock_{pid.hex[:6]}@educampo.com.br"
    create_resp = client.post(
        "/v1/producers",
        json={
            "id": str(pid),
            "nome": "Fazenda Antes Update",
            "email": original_email,
            "password": "SenhaOriginal123",
            "id_fazenda": "FZ-OLD",
            "dados": {"area": 100},
        },
        headers=AUTH_HEADERS,
    )
    assert create_resp.status_code == 201
    assert create_resp.json()["version"] == 1

    # 1. Update válido com If-Match: 1 -> version passa para 2
    headers_v1 = {**AUTH_HEADERS, "If-Match": "1"}
    update_payload = {
        "nome": "Fazenda Atualizada v2",
        "id_fazenda": "FZ-NEW",
        "dados": {"area": 150, "pivo": True},
    }
    update_resp = client.put(f"/v1/producers/{pid}", json=update_payload, headers=headers_v1)
    assert update_resp.status_code == 200
    updated_data = update_resp.json()
    assert updated_data["nome"] == "Fazenda Atualizada v2"
    assert updated_data["id_fazenda"] == "FZ-NEW"
    assert updated_data["dados"] == {"area": 150, "pivo": True}
    assert updated_data["email"] == original_email
    assert updated_data["version"] == 2

    # 2. Concorrência: outro consumidor tenta atualizar com If-Match: 1 desatualizado -> 412
    conflict_resp = client.put(
        f"/v1/producers/{pid}",
        json={"nome": "Tentativa Invalida"},
        headers=headers_v1,
    )
    assert conflict_resp.status_code == 412
    assert conflict_resp.headers["content-type"].startswith("application/problem+json")
    assert conflict_resp.json()["type"] == "version-mismatch"

    # Confirma que os dados permaneceram na versão 2
    get_resp = client.get(f"/v1/producers/{pid}", headers=AUTH_HEADERS)
    assert get_resp.json()["version"] == 2
    assert get_resp.json()["nome"] == "Fazenda Atualizada v2"


def test_scenario_8_and_9_delete_producer(client):
    """Cenários 8 e 9: Exclusão com HTTP 204 e posterior 404 em consulta e nova exclusão."""
    pid = uuid.uuid4()
    client.post(
        "/v1/producers",
        json={"id": str(pid), "nome": "Para Excluir", "email": f"delete_{pid.hex[:6]}@educampo.com.br", "password": "SenhaValida123"},
        headers=AUTH_HEADERS,
    )

    # Exclusão com sucesso -> 204 No Content
    del_resp = client.delete(f"/v1/producers/{pid}", headers=AUTH_HEADERS)
    assert del_resp.status_code == 204
    assert not del_resp.content

    # Consulta subsequente -> 404
    get_resp = client.get(f"/v1/producers/{pid}", headers=AUTH_HEADERS)
    assert get_resp.status_code == 404

    # Segunda tentativa de exclusão -> 404
    del_404 = client.delete(f"/v1/producers/{pid}", headers=AUTH_HEADERS)
    assert del_404.status_code == 404
    assert del_404.headers["content-type"].startswith("application/problem+json")
    assert del_404.json()["type"] == "not-found"


def test_scenario_10_consultant_producers_managed_derivation(client):
    """Cenário 10: Derivação dinâmica de produtores gerenciados na consulta do consultor."""
    cid = uuid.uuid4()
    c_resp = client.post(
        "/v1/consultants",
        json={
            "id": str(cid),
            "nome": "Consultor com 3 Produtores",
            "email": f"consultor_{cid.hex[:8]}@educampo.com.br",
            "password": "SenhaSegura123",
        },
        headers=AUTH_HEADERS,
    )
    assert c_resp.status_code == 201

    # Cria 3 produtores vinculados a este consultor
    p_ids = []
    for i in range(3):
        pid = uuid.uuid4()
        p_ids.append(pid)
        p_resp = client.post(
            "/v1/producers",
            json={
                "id": str(pid),
                "nome": f"Fazenda Vinculada {i+1}",
                "email": f"fazenda_{pid.hex[:6]}@educampo.com.br",
                "password": "SenhaProdutor123",
                "consultant_id": str(cid),
            },
            headers=AUTH_HEADERS,
        )
        assert p_resp.status_code == 201

    # Consulta consultor
    c_get = client.get(f"/v1/consultants/{cid}", headers=AUTH_HEADERS)
    assert c_get.status_code == 200
    managed = c_get.json()["producers_managed"]
    assert len(managed) == 3
    for pid in p_ids:
        assert str(pid) in managed


def test_scenario_11_and_12_producer_auth_verify(client):
    """Cenários 11 e 12: POST /v1/auth/verify sucesso (200) e rejeição uniforme (401)."""
    pid = uuid.uuid4()
    email = "fazenda.sol.auth@educampo.com.br"
    password = "Produtor@123"

    create_resp = client.post(
        "/v1/producers",
        json={"id": str(pid), "nome": "Fazenda Sol", "email": email, "password": password},
        headers=AUTH_HEADERS,
    )
    assert create_resp.status_code == 201

    # Sucesso com role producer -> 200
    resp_ok = client.post(
        "/v1/auth/verify",
        json={"email": email, "password": password, "role": "producer"},
        headers=AUTH_HEADERS,
    )
    assert resp_ok.status_code == 200
    assert resp_ok.json() == {"id": str(pid), "role": "producer"}

    # Senha incorreta -> 401
    resp_bad_pw = client.post(
        "/v1/auth/verify",
        json={"email": email, "password": "SenhaIncorreta", "role": "producer"},
        headers=AUTH_HEADERS,
    )
    assert resp_bad_pw.status_code == 401
    assert resp_bad_pw.headers["content-type"].startswith("application/problem+json")
    assert resp_bad_pw.json()["type"] == "invalid-credentials"

    # E-mail inexistente -> 401 idêntico
    resp_no_email = client.post(
        "/v1/auth/verify",
        json={"email": "fantasma@educampo.com.br", "password": password, "role": "producer"},
        headers=AUTH_HEADERS,
    )
    assert resp_no_email.status_code == 401
    assert resp_no_email.json()["type"] == "invalid-credentials"


def test_scenario_13_and_14_pagination_and_limits(client):
    """Cenários 13 e 14: Paginação com X-Total-Count e limite máximo de 200."""
    resp = client.get("/v1/producers?limit=5&offset=0", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    assert "X-Total-Count" in resp.headers
    total = int(resp.headers["X-Total-Count"])
    assert total >= 1
    assert len(resp.json()) <= 5

    # Limite excedido -> 422
    resp_exceeded = client.get("/v1/producers?limit=201", headers=AUTH_HEADERS)
    assert resp_exceeded.status_code == 422
    assert resp_exceeded.headers["content-type"].startswith("application/problem+json")
    assert resp_exceeded.json()["type"] == "validation-error"
