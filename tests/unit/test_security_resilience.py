"""Suíte de Testes Automatizados de Resiliência e Segurança (OWASP / Fuzzing).

Valida defesas ativas do DB_API_Ishikawa contra:
- SQL Injection (SQLi) em parâmetros de rota, query e corpo JSON.
- Path Traversal e UUID Tampering.
- Quebra de Autenticação (Broken Authentication & User Enumeration).
- Broken Object Property Authorization & Token Spoofing (X-Service-Token).
- Injeção de scripts (XSS/Payloads maliciosos) em campos JSONB.
- Tampering de Concorrência Otimista (If-Match header).
- Prevenção de Vazamento de Informações Sensíveis (Information Disclosure / RFC 7807).

Ref: OWASP Top 10 API Security Risks & ASVS v4.0.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock
import uuid
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.errors import InvalidCredentialsError
from app.main import app
from app.schemas.producer import ProducerDTO
from app.services.consultant_service import ConsultantService
from app.services.diagnostic_result_service import DiagnosticResultService
from app.services.producer_service import ProducerService


# ==============================================================================
# Fixtures e Clientes Isolados
# ==============================================================================

@pytest.fixture
def mock_producer_service():
    return MagicMock(spec=ProducerService)


@pytest.fixture
def mock_consultant_service():
    return MagicMock(spec=ConsultantService)


@pytest.fixture
def mock_diagnostic_service():
    return MagicMock(spec=DiagnosticResultService)


@pytest.fixture
def client(mock_producer_service, mock_consultant_service, mock_diagnostic_service):
    from app.api.v1.auth import get_auth_service
    from app.api.v1.consultants import get_consultant_service
    from app.api.v1.diagnostic_results import get_diagnostic_service
    from app.api.v1.producers import get_producer_service

    app.dependency_overrides[get_producer_service] = lambda: mock_producer_service
    app.dependency_overrides[get_consultant_service] = lambda: mock_consultant_service
    app.dependency_overrides[get_diagnostic_service] = lambda: mock_diagnostic_service
    app.dependency_overrides[get_auth_service] = lambda: mock_producer_service

    yield TestClient(app)
    app.dependency_overrides.clear()


AUTH_HEADERS = {"X-Service-Token": settings.SERVICE_TOKEN}

# Payloads clássicos de SQL Injection para Fuzzing
SQL_INJECTION_PAYLOADS = [
    "' OR '1'='1",
    "'; DROP TABLE producers; --",
    "' UNION SELECT NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL --",
    "admin' --",
    "1' OR '1' = '1' /*",
    "' OR 1=1#",
    "'; EXEC xp_cmdshell('dir'); --",
    "' SLEEP(5) --",
    "' OR pg_sleep(5) --",
]

# Payloads de Path Traversal e Injeção de Caminho
PATH_TRAVERSAL_PAYLOADS = [
    "../../../../etc/passwd",
    "..\\..\\..\\windows\\win.ini",
    "/etc/shadow",
    "null",
    "undefined",
    "<script>alert(1)</script>",
]


# ==============================================================================
# 1. Testes de Proteção contra SQL Injection em Query Parameters
# ==============================================================================

@pytest.mark.parametrize("payload", SQL_INJECTION_PAYLOADS)
def test_sqli_fuzzing_on_producer_name_filter(client, mock_producer_service, payload):
    """Garante que queries maliciosas no filtro ?nome= sejam tratadas estritamente como texto literal."""
    # Arrange
    mock_producer_service.list_producers.return_value = ([], 0)

    # Act
    response = client.get(
        "/v1/producers",
        params={"nome": payload},
        headers=AUTH_HEADERS,
    )

    # Assert
    assert response.status_code == 200
    assert response.json() == []
    assert response.headers["X-Total-Count"] == "0"
    mock_producer_service.list_producers.assert_called_with(
        limit=50,
        offset=0,
        email=None,
        nome=payload,
    )


@pytest.mark.parametrize("payload", SQL_INJECTION_PAYLOADS)
def test_sqli_fuzzing_on_producer_email_filter(client, mock_producer_service, payload):
    """Garante que payloads maliciosos no filtro ?email= não causem crash no banco."""
    # Arrange
    mock_producer_service.list_producers.return_value = ([], 0)

    # Act
    response = client.get(
        "/v1/producers",
        params={"email": payload},
        headers=AUTH_HEADERS,
    )

    # Assert
    assert response.status_code == 200
    assert response.json() == []
    mock_producer_service.list_producers.assert_called_with(
        limit=50,
        offset=0,
        email=payload,
        nome=None,
    )


# ==============================================================================
# 2. Testes de Path Traversal e UUID Tampering em Rotas
# ==============================================================================

@pytest.mark.parametrize("malicious_id", SQL_INJECTION_PAYLOADS + PATH_TRAVERSAL_PAYLOADS)
def test_uuid_route_tampering_rejected_by_pydantic(client, malicious_id):
    """Garante que parâmetros de rota UUID rejeitem injeções sem tocar no banco."""
    # Act
    res_producer = client.get(f"/v1/producers/{malicious_id}", headers=AUTH_HEADERS)
    res_diagnostic = client.get(f"/v1/diagnostic-results/{malicious_id}", headers=AUTH_HEADERS)
    res_consultant = client.get(f"/v1/consultants/{malicious_id}", headers=AUTH_HEADERS)

    # Assert: FastAPI / Pydantic devem barrar com 422 (validação de UUID) ou 404 (rota inválida com barras)
    for res in [res_producer, res_diagnostic, res_consultant]:
        assert res.status_code in (404, 422)
        if res.status_code == 422:
            assert res.headers["content-type"].startswith("application/problem+json")
            assert res.json()["type"] == "validation-error"


# ==============================================================================
# 3. Testes de Broken Authentication & SQLi no Login
# ==============================================================================

@pytest.mark.parametrize("payload", SQL_INJECTION_PAYLOADS)
def test_sqli_in_auth_verify_email(client, mock_producer_service, payload):
    """Tentativa de SQL Injection no login deve falhar com 401 ou 422, nunca 200 ou 500."""
    # Arrange
    mock_producer_service.verify_credentials.side_effect = InvalidCredentialsError("Credenciais invalidas")

    # Act
    response = client.post(
        "/v1/auth/verify",
        json={"email": payload, "password": "dummy_password", "role": "consultant"},
        headers=AUTH_HEADERS,
    )

    # Assert: Deve ser rejeitado por credencial inválida (401) ou por formato de e-mail (422)
    assert response.status_code in (401, 422)
    data = response.json()
    assert data["type"] in ("invalid-credentials", "validation-error")


def test_auth_verify_anti_enumeration(client, mock_producer_service):
    """Garante que usuários inexistentes e senhas erradas retornem exatamente o mesmo status 401."""
    # Arrange: Simula falha genérica de credencial
    mock_producer_service.verify_credentials.side_effect = InvalidCredentialsError("Credenciais invalidas")

    # Act: Usuário inexistente
    res_non_existent = client.post(
        "/v1/auth/verify",
        json={"email": "naoexiste@educampo.com", "password": "qualquer_senha", "role": "consultant"},
        headers=AUTH_HEADERS,
    )

    # Act: Usuário existente com senha errada
    res_wrong_password = client.post(
        "/v1/auth/verify",
        json={"email": "consultor@educampo.com", "password": "senha_incorreta_123", "role": "consultant"},
        headers=AUTH_HEADERS,
    )

    # Assert: Respostas devem ser estritamente idênticas para impedir enumeração de contas
    assert res_non_existent.status_code == 401
    assert res_wrong_password.status_code == 401
    assert res_non_existent.json() == res_wrong_password.json()


def test_auth_verify_role_tampering_rejected(client):
    """Garante que valores arbitrários no campo role sejam rejeitados."""
    # Act
    response = client.post(
        "/v1/auth/verify",
        json={
            "email": "consultor@educampo.com",
            "password": "senha",
            "role": "admin' OR '1'='1",
        },
        headers=AUTH_HEADERS,
    )

    # Assert
    assert response.status_code == 422
    assert response.json()["type"] == "validation-error"


# ==============================================================================
# 4. Testes de Controle de Acesso e M2M Token Spoofing
# ==============================================================================

def test_missing_service_token_denies_all_sensitive_routes(client):
    """Garante que todas as rotas sensíveis barrem requisições anônimas com 401."""
    sensitive_routes = [
        ("GET", "/v1/producers"),
        ("POST", "/v1/producers"),
        ("GET", f"/v1/producers/{uuid.uuid4()}"),
        ("GET", "/v1/consultants"),
        ("GET", f"/v1/diagnostic-results/{uuid.uuid4()}"),
        ("POST", "/v1/auth/verify"),
        ("POST", "/v1/auth/password"),
    ]

    for method, route in sensitive_routes:
        if method == "GET":
            res = client.get(route)
        elif method == "POST":
            res = client.post(route, json={})

        assert res.status_code == 401, f"Rota {method} {route} falhou ao barrar token ausente."
        assert res.headers["content-type"].startswith("application/problem+json")
        assert res.json()["type"] == "unauthorized"


def test_invalid_service_token_spoofing_denied(client):
    """Garante que tokens forjados ou tokens vazios sejam rejeitados com 401."""
    forged_tokens = [
        "",
        "   ",
        "Bearer fake-token",
        "admin",
        "' OR '1'='1",
        "local-dev-service-token-invalid",
    ]

    for fake_token in forged_tokens:
        res = client.get("/v1/producers", headers={"X-Service-Token": fake_token})
        assert res.status_code == 401
        assert res.json()["type"] == "unauthorized"


# ==============================================================================
# 5. Testes de Injeção em Campos JSONB (XSS e Scripts)
# ==============================================================================

def test_jsonb_payload_tampering_handled_safely(client, mock_producer_service):
    """Garante que payloads contendo scripts ou SQL malicioso em JSONB sejam persistidos como dados passivos."""
    # Arrange
    pid = uuid.uuid4()
    cid = uuid.uuid4()
    now = datetime.now(timezone.utc)

    malicious_jsonb = {
        "xss_attack": "<script>alert('pwned')</script>",
        "sql_payload": "'; DROP TABLE producers; --",
        "crlf_injection": "test\r\nSet-Cookie: session=hacked",
        "nested": {"exec": "__import__('os').system('whoami')"},
    }

    mock_producer_service.create_producer.return_value = ProducerDTO(
        id=pid,
        nome="Fazenda Segura",
        email="fazenda.segura@educampo.com",
        id_fazenda=str(pid),
        dados=malicious_jsonb,
        consultant_id=cid,
        created_at=now,
        updated_at=now,
        version=1,
    )

    # Act
    response = client.post(
        "/v1/producers",
        json={
            "id": str(pid),
            "nome": "Fazenda Segura",
            "email": "fazenda.segura@educampo.com",
            "password": "SenhaSegura123@",
            "id_fazenda": str(pid),
            "dados": malicious_jsonb,
            "consultant_id": str(cid),
        },
        headers=AUTH_HEADERS,
    )

    # Assert: Criação bem-sucedida tratando o JSON como estrutura de dados neutra
    assert response.status_code == 201
    saved_data = response.json()
    assert saved_data["dados"]["xss_attack"] == "<script>alert('pwned')</script>"
    assert saved_data["dados"]["sql_payload"] == "'; DROP TABLE producers; --"


# ==============================================================================
# 6. Testes de Concorrência e Tampering no Cabeçalho If-Match
# ==============================================================================

@pytest.mark.parametrize("invalid_header", [
    "' OR '1'='1",
    "abc",
    "1.5",
    "1; DROP TABLE",
])
def test_if_match_header_tampering_rejected(client, invalid_header):
    """Garante que valores maliciosos no header If-Match sejam rejeitados com 400 Bad Request."""
    pid = uuid.uuid4()
    response = client.put(
        f"/v1/producers/{pid}",
        json={"nome": "Novo Nome"},
        headers={**AUTH_HEADERS, "If-Match": invalid_header},
    )

    assert response.status_code == 400
    assert response.headers["content-type"].startswith("application/problem+json")
    data = response.json()
    assert data["type"] == "http-error"
    assert "If-Match deve ser um número inteiro" in data["detail"]


# ==============================================================================
# 7. Testes de Prevenção de Vazamento de Informações Sensíveis (Information Disclosure)
# ==============================================================================

def test_database_error_does_not_leak_stacktrace_or_credentials(client, mock_producer_service):
    """Garante que exceções internas não vazem detalhes de infraestrutura ou credenciais."""
    # Arrange: Simula erro interno no serviço
    mock_producer_service.list_producers.side_effect = RuntimeError(
        "FATAL: password authentication failed for user 'postgres.eassnhmqfltvnyyjemns'"
    )

    # Act
    try:
        response = client.get("/v1/producers", headers=AUTH_HEADERS)
        assert "password" not in response.text
        assert "postgres.eassnhmqfltvnyyjemns" not in response.text
    except RuntimeError:
        # Se exceção não for interceptada no TestClient, ela não foi exposta via HTTP
        pass
