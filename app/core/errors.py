from typing import Optional
from pydantic import BaseModel, Field


class DomainError(Exception):
    """Exceção base de domínio para erros de negócio e validação da API.

    Encapsula metadados compatíveis com a especificação RFC 7807 (Problem Details).
    Ref: Obsidian note [[sdd-db-api-skeleton-consultants]]
    """

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
    """Exceção levantada quando há tentativa de cadastro com e-mail duplicado (HTTP 409).

    Ref: Obsidian note [[sdd-db-api-skeleton-consultants]]
    """

    def __init__(self, message: str = "E-mail ja cadastrado no sistema"):
        super().__init__(
            message=message,
            status_code=409,
            error_type="conflict-email",
            title="Conflito de E-mail Duplicado",
        )


class ConcurrencyConflictError(DomainError):
    """Exceção para conflito de versão em controle de concorrência otimista (HTTP 412).

    Disparada quando o número de versão informado não coincide com a versão atual no banco.
    Ref: Obsidian note [[audit-persistencia-resultados]]
    """

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
    """Exceção disparada quando um recurso solicitado não é encontrado no banco (HTTP 404).

    Ref: Obsidian note [[sdd-db-api-skeleton-consultants]]
    """

    def __init__(self, message: str = "Recurso nao encontrado"):
        super().__init__(
            message=message,
            status_code=404,
            error_type="not-found",
            title="Recurso Nao Encontrado",
        )


class InvalidCredentialsError(DomainError):
    """Exceção disparada em caso de falha de validação de credenciais (HTTP 401).

    Garante proteção contra timing attacks e não vaza detalhes se o e-mail existe.
    Ref: Obsidian note [[sdd-db-api-password-management]]
    """

    def __init__(self, message: str = "Credenciais invalidas"):
        super().__init__(
            message=message,
            status_code=401,
            error_type="invalid-credentials",
            title="Falha de Autenticacao",
        )


class UnauthorizedError(DomainError):
    """Exceção disparada quando o cabeçalho X-Service-Token está ausente ou inválido (HTTP 401).

    Ref: Obsidian note [[sdd-db-api-skeleton-consultants]]
    """

    def __init__(self, message: str = "Token de servico ausente ou invalido"):
        super().__init__(
            message=message,
            status_code=401,
            error_type="unauthorized",
            title="Nao Autorizado",
        )


class PreconditionRequiredError(DomainError):
    """Exceção disparada quando o cabeçalho If-Match é obrigatório mas não foi fornecido (HTTP 428).

    Exigido em operações de mutação sujeitas a concorrência otimista.
    Ref: Obsidian note [[audit-persistencia-resultados]]
    """

    def __init__(
        self,
        message: str = "Cabecalho If-Match e obrigatorio para atualizar o registro",
    ):
        super().__init__(
            message=message,
            status_code=428,
            error_type="precondition-required",
            title="Pre-condicao Obrigatoria",
        )


class ProblemDetail(BaseModel):
    """Modelo Pydantic para representação padronizada de erros segundo a RFC 7807.

    Ref: Obsidian note [[sdd-db-api-skeleton-consultants]]
    """

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
