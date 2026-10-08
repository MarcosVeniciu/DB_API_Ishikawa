from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.security import verify_service_token
from app.db.repositories.diagnostic_result_repo import DiagnosticResultRepository
from app.db.repositories.producer_repo import ProducerRepository
from app.db.session import get_db
from app.schemas.diagnostic_result import DiagnosticResultDTO, DiagnosticResultSaveDTO
from app.services.diagnostic_result_service import DiagnosticResultService

diagnostic_results_router = APIRouter(
    prefix="/diagnostic-results",
    tags=["Diagnostic Results"],
    dependencies=[Depends(verify_service_token)],
)


def get_diagnostic_service(db: Session = Depends(get_db)) -> DiagnosticResultService:
    """Dependency que constrói o serviço de resultados de diagnóstico."""
    diagnostic_repo = DiagnosticResultRepository(db)
    producer_repo = ProducerRepository(db)
    return DiagnosticResultService(
        diagnostic_repo=diagnostic_repo,
        producer_repo=producer_repo,
    )


@diagnostic_results_router.get(
    "/{producer_id}",
    response_model=DiagnosticResultDTO,
    status_code=status.HTTP_200_OK,
    summary="Buscar resultado de diagnóstico por ID do produtor",
)
def get_diagnostic_result_by_producer_id(
    producer_id: UUID,
    service: DiagnosticResultService = Depends(get_diagnostic_service),
) -> DiagnosticResultDTO:
    """Retorna o diagnóstico agronômico e simulação persistidos para o produtor."""
    return service.get_by_producer_id(producer_id)


@diagnostic_results_router.put(
    "/{producer_id}",
    response_model=DiagnosticResultDTO,
    summary="Salvar ou atualizar resultado de diagnóstico com lock otimista",
)
def save_diagnostic_result(
    producer_id: UUID,
    dto: DiagnosticResultSaveDTO,
    response: Response,
    if_match: Optional[str] = Header(None, alias="If-Match", description="Versão esperada do registro"),
    service: DiagnosticResultService = Depends(get_diagnostic_service),
) -> DiagnosticResultDTO:
    """Persiste ou atualiza atomicamente o diagnóstico do produtor.
    
    Retorna 201 Created para inserção inicial (If-Match opcional)
    ou 200 OK para atualização (If-Match obrigatório).
    """
    expected_version: Optional[int] = None
    if if_match is not None:
        try:
            expected_version = int(if_match.strip().strip('"'))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cabeçalho If-Match deve ser um número inteiro representando a versão.",
            )

    result_dto, created = service.save_diagnostic_result(
        producer_id=producer_id,
        dto=dto,
        expected_version=expected_version,
    )

    if created:
        response.status_code = status.HTTP_201_CREATED
    else:
        response.status_code = status.HTTP_200_OK

    return result_dto
