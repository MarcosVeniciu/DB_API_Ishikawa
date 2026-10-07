"""
Testes de integração para seed idempotente e RLS contra PostgreSQL 16 real (Lote 5).
Ref: Obsidian BDD [[bdd-db-api-seed-hardening]] & SDD [[sdd-db-api-seed-hardening]]
"""

from pathlib import Path
import uuid
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from testcontainers.postgres import PostgresContainer

from app.core.config import settings
from app.db.models import Consultant, Producer
from app.db.session import get_db
from app.main import app
from app.seed.import_farms import DEFAULT_CONSULTANT_ID, run_seed

AUTH_HEADERS = {"X-Service-Token": settings.SERVICE_TOKEN}


@pytest.fixture(scope="module")
def postgres_container():
    """Sobe um container PostgreSQL 16 isolado via testcontainers e roda migrações até head."""
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

    def _get_test_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _get_test_db
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()
    engine.dispose()


def test_scenario_1_seed_initial_execution(pg_session):
    """Cenário 1 BDD: Primeira execução do seed popula 1 consultor e 5 produtores com dados íntegros."""
    # Act
    summary = run_seed(pg_session)

    # Assert - AAA
    assert summary.consultants_inserted == 1
    assert summary.producers_inserted == 5
    assert summary.producers_skipped == 0
    assert summary.total_farms_processed == 5
    assert summary.duration_ms > 0

    consultants = pg_session.query(Consultant).all()
    assert len(consultants) == 1
    consultant = consultants[0]
    assert consultant.id == DEFAULT_CONSULTANT_ID
    assert consultant.email == "consultor@educampo.com"
    assert consultant.hashed_password.startswith("$2")

    producers = pg_session.query(Producer).all()
    assert len(producers) == 5
    for p in producers:
        assert p.consultant_id == DEFAULT_CONSULTANT_ID
        assert p.hashed_password.startswith("$2")
        assert p.id_fazenda is not None
        assert p.version == 1


def test_scenario_2_seed_strict_idempotency(pg_session):
    """Cenário 2 BDD: Execuções subsequentes do seed são estritamente idempotentes (0 inserções, 0 erros)."""
    # Act - Execução repetida sobre o mesmo banco já populado
    summary2 = run_seed(pg_session)

    # Assert - AAA
    assert summary2.consultants_inserted == 0
    assert summary2.producers_inserted == 0
    assert summary2.producers_skipped == 5
    assert summary2.total_farms_processed == 5

    # Valida que as contagens continuam idênticas
    assert pg_session.query(Consultant).count() == 1
    assert pg_session.query(Producer).count() == 5


def test_scenario_3_rls_enabled_in_catalog(pg_session):
    """Cenário 5 BDD: Tabelas consultants, producers e diagnostic_results possuem relrowsecurity ativado (D19)."""
    # Act
    result = pg_session.execute(
        text(
            """
            SELECT relname, relrowsecurity
            FROM pg_class
            WHERE relname IN ('consultants', 'producers', 'diagnostic_results')
            """
        )
    ).fetchall()

    # Assert - AAA
    rows = {row[0]: row[1] for row in result}
    assert len(rows) == 3
    assert rows["consultants"] is True
    assert rows["producers"] is True
    assert rows["diagnostic_results"] is True


def test_scenario_4_auth_verify_with_seeded_credentials(client):
    """Valida que credenciais geradas pelo seed autenticam com sucesso em /v1/auth/verify."""
    # 1. Login consultor padrão
    res_consultant = client.post(
        "/v1/auth/verify",
        json={
            "email": "consultor@educampo.com",
            "password": "admin123",
            "role": "consultant",
        },
        headers=AUTH_HEADERS,
    )
    assert res_consultant.status_code == 200
    assert res_consultant.json()["id"] == str(DEFAULT_CONSULTANT_ID)
    assert res_consultant.json()["role"] == "consultant"

    # 2. Login produtor do seed (email_fazenda_1@gmail.com / produtor123)
    res_producer = client.post(
        "/v1/auth/verify",
        json={
            "email": "email_fazenda_1@gmail.com",
            "password": "produtor123",
            "role": "producer",
        },
        headers=AUTH_HEADERS,
    )
    assert res_producer.status_code == 200
    assert res_producer.json()["role"] == "producer"

    # 3. Senha errada rejeitada com 401 idêntico
    res_invalid = client.post(
        "/v1/auth/verify",
        json={
            "email": "email_fazenda_1@gmail.com",
            "password": "senha_incorreta",
            "role": "producer",
        },
        headers=AUTH_HEADERS,
    )
    assert res_invalid.status_code == 401


def test_scenario_5_endpoints_read_seeded_data(client):
    """Valida leitura dos produtores importados e derivação de producers_managed no consultor."""
    # 1. Listagem de produtores
    res_producers = client.get("/v1/producers", headers=AUTH_HEADERS)
    assert res_producers.status_code == 200
    producers_data = res_producers.json()
    assert len(producers_data) == 5
    assert res_producers.headers.get("X-Total-Count") == "5"

    # 2. Consultor deriva os 5 produtores vinculados
    res_consultant = client.get(
        f"/v1/consultants/{DEFAULT_CONSULTANT_ID}", headers=AUTH_HEADERS
    )
    assert res_consultant.status_code == 200
    consultant_data = res_consultant.json()
    assert len(consultant_data["producers_managed"]) == 5
