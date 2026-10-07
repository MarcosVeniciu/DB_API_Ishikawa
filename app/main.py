import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.health import health_router
from app.api.v1.api import api_v1_router
from app.core.config import settings
from app.core.errors import DomainError, ProblemDetail, create_problem_detail
from app.db.session import SessionLocal
from app.seed.import_farms import run_seed

logger = logging.getLogger("db_api.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan gerenciando inicialização e finalização da aplicação."""
    # Startup actions
    if settings.SEED_ON_STARTUP:
        logger.info("SEED_ON_STARTUP habilitado. Executando seed de dados...")
        db = SessionLocal()
        try:
            run_seed(db)
        finally:
            db.close()
    yield
    # Shutdown actions


app = FastAPI(
    title="DB_API_Ishikawa",
    description="Serviço dedicado de persistência e validação de credenciais do Ecossistema Educampo Ishikawa",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
)


@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    """Mapeia exceções de domínio para respostas RFC 7807 Problem Details."""
    problem = create_problem_detail(exc, instance=str(request.url))
    return JSONResponse(
        status_code=exc.status_code,
        content=problem.model_dump(),
        media_type="application/problem+json",
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Mapeia erros de validação do Pydantic/FastAPI para o padrão RFC 7807."""
    problem = ProblemDetail(
        type="validation-error",
        title="Erro de Validacao da Requisicao",
        status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=str(exc.errors()),
        instance=str(request.url),
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=problem.model_dump(),
        media_type="application/problem+json",
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Mapeia HTTPException para o formato RFC 7807."""
    problem = ProblemDetail(
        type="http-error",
        title="Erro HTTP",
        status=exc.status_code,
        detail=str(exc.detail),
        instance=str(request.url),
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=problem.model_dump(),
        media_type="application/problem+json",
    )


# Registra rotas
app.include_router(health_router)
app.include_router(api_v1_router, prefix=settings.API_V1_STR)
