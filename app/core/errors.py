from typing import Optional
from pydantic import BaseModel, Field


class DomainError(Exception):
    """Base domain exception."""

    def __init__(
        self,
        message: str,
        status_code: int = 400,
        error_type: str = "about:blank",
        title: str = "Error",
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_type = error_type
        self.title = title


class DuplicateEmailError(DomainError):
    def __init__(self, message: str = "E-mail ja cadastrado no sistema"):
        super().__init__(
            message=message,
            status_code=409,
            error_type="conflict-email",
            title="Conflito de E-mail Duplicado",
        )


class ConcurrencyConflictError(DomainError):
    def __init__(
        self,
        message: str = "Conflito de concorrencia: versao do registro desatualizada",
    ):
        super().__init__(
            message=message,
            status_code=412,
            error_type="version-mismatch",
            title="Conflito de Concorrencia",
        )


class NotFoundError(DomainError):
    def __init__(self, message: str = "Recurso nao encontrado"):
        super().__init__(
            message=message,
            status_code=404,
            error_type="not-found",
            title="Recurso Nao Encontrado",
        )


class InvalidCredentialsError(DomainError):
    def __init__(self, message: str = "Credenciais invalidas"):
        super().__init__(
            message=message,
            status_code=401,
            error_type="invalid-credentials",
            title="Falha de Autenticacao",
        )


class UnauthorizedError(DomainError):
    def __init__(self, message: str = "Token de servico ausente ou invalido"):
        super().__init__(
            message=message,
            status_code=401,
            error_type="unauthorized",
            title="Nao Autorizado",
        )


class ProblemDetail(BaseModel):
    """RFC 7807 Problem Details representation."""

    type: str = Field(..., description="URI identificador do tipo do erro")
    title: str = Field(..., description="Resumo legivel do erro")
    status: int = Field(..., description="Codigo de status HTTP")
    detail: str = Field(..., description="Explicacao detalhada da ocorrencia")
    instance: Optional[str] = Field(None, description="URI da requisicao que gerou o erro")


def create_problem_detail(error: DomainError, instance: Optional[str] = None) -> ProblemDetail:
    """Mapeia DomainError para ProblemDetail RFC 7807."""
    return ProblemDetail(
        type=error.error_type,
        title=error.title,
        status=error.status_code,
        detail=error.message,
        instance=instance,
    )
