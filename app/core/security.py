import bcrypt
from typing import Annotated, Optional
from fastapi import Header
from app.core.config import settings
from app.core.errors import UnauthorizedError


def hash_password(password: str) -> str:
    """Gera hash seguro com bcrypt e salt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica se a senha em texto puro corresponde ao hash bcrypt."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def verify_service_token(
    x_service_token: Annotated[Optional[str], Header()] = None,
    expected_token: Optional[str] = None,
) -> str:
    """Valida o cabecalho X-Service-Token."""
    target = expected_token if expected_token is not None else settings.SERVICE_TOKEN
    if not x_service_token or x_service_token != target:
        raise UnauthorizedError("Token de servico ausente ou invalido")
    return x_service_token
