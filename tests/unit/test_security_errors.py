import pytest
from app.core.config import Settings
from app.core.security import hash_password, verify_password, verify_service_token
from app.core.errors import (
    DuplicateEmailError,
    ConcurrencyConflictError,
    NotFoundError,
    InvalidCredentialsError,
    UnauthorizedError,
    create_problem_detail,
)


def test_hash_password_and_verify():
    # Arrange
    plain = "MinhaSenhaForte@2026"

    # Act
    hashed = hash_password(plain)

    # Assert
    assert hashed != plain
    assert hashed.startswith("$2b$") or hashed.startswith("$2a$")
    assert verify_password(plain, hashed) is True
    assert verify_password("SenhaErrada", hashed) is False


def test_verify_service_token_valid():
    # Arrange
    settings = Settings(SERVICE_TOKEN="secret-test-token")

    # Act
    token = verify_service_token("secret-test-token", expected_token=settings.SERVICE_TOKEN)

    # Assert
    assert token == "secret-test-token"


def test_verify_service_token_missing_or_invalid():
    # Arrange
    expected = "secret-test-token"

    # Act & Assert
    with pytest.raises(UnauthorizedError) as exc_info:
        verify_service_token(None, expected_token=expected)
    assert exc_info.value.status_code == 401

    with pytest.raises(UnauthorizedError) as exc_info2:
        verify_service_token("wrong-token", expected_token=expected)
    assert exc_info2.value.status_code == 401


def test_problem_details_mapping():
    # Duplicate email (409)
    err_dup = DuplicateEmailError("E-mail ja cadastrado")
    pd_dup = create_problem_detail(err_dup)
    assert pd_dup.status == 409
    assert pd_dup.type == "conflict-email"
    assert "E-mail ja cadastrado" in pd_dup.detail

    # Concurrency conflict (412)
    err_conflict = ConcurrencyConflictError("Versao divergente")
    pd_conflict = create_problem_detail(err_conflict)
    assert pd_conflict.status == 412
    assert pd_conflict.type == "version-mismatch"

    # Not found (404)
    err_nf = NotFoundError("Consultor nao encontrado")
    pd_nf = create_problem_detail(err_nf)
    assert pd_nf.status == 404
    assert pd_nf.type == "not-found"

    # Invalid credentials (401)
    err_cred = InvalidCredentialsError("Credenciais invalidas")
    pd_cred = create_problem_detail(err_cred)
    assert pd_cred.status == 401
    assert pd_cred.type == "invalid-credentials"

    # Unauthorized (401)
    err_unauth = UnauthorizedError("Token de servico invalido ou ausente")
    pd_unauth = create_problem_detail(err_unauth)
    assert pd_unauth.status == 401
    assert pd_unauth.type == "unauthorized"
