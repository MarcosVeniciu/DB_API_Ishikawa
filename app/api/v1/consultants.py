from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.core.security import verify_service_token
from app.db.repositories.consultant_repo import ConsultantRepository
from app.db.session import get_db
from app.schemas.consultant import (
    ConsultantCreateDTO,
    ConsultantDTO,
    ConsultantUpdateDTO,
)
from app.services.consultant_service import ConsultantService

consultants_router = APIRouter(
    prefix="/consultants",
    tags=["Consultants"],
    dependencies=[Depends(verify_service_token)],
)


def get_consultant_service(db: Session = Depends(get_db)) -> ConsultantService:
    """Dependency que constrói o serviço de consultores."""
    repository = ConsultantRepository(db)
    return ConsultantService(repository)


@consultants_router.post(
    "",
    response_model=ConsultantDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Criar novo consultor",
)
def create_consultant(
    dto: ConsultantCreateDTO,
    service: ConsultantService = Depends(get_consultant_service),
) -> ConsultantDTO:
    """Cria um novo consultor com hash bcrypt e lock otimista versão 1."""
    return service.create_consultant(dto)


@consultants_router.get(
    "",
    response_model=List[ConsultantDTO],
    status_code=status.HTTP_200_OK,
    summary="Listar consultores paginados",
)
def list_consultants(
    response: Response,
    limit: int = Query(50, ge=1, le=200, description="Limite máximo de 200 registros por página"),
    offset: int = Query(0, ge=0, description="Deslocamento para paginação"),
    email: Optional[str] = Query(None, description="Filtro opcional por e-mail"),
    service: ConsultantService = Depends(get_consultant_service),
) -> List[ConsultantDTO]:
    """Lista consultores paginados e adiciona cabeçalho X-Total-Count."""
    items, total = service.list_consultants(limit=limit, offset=offset, email=email)
    response.headers["X-Total-Count"] = str(total)
    return items


@consultants_router.get(
    "/{consultant_id}",
    response_model=ConsultantDTO,
    status_code=status.HTTP_200_OK,
    summary="Buscar consultor por ID",
)
def get_consultant_by_id(
    consultant_id: UUID,
    service: ConsultantService = Depends(get_consultant_service),
) -> ConsultantDTO:
    """Busca consultor por ID."""
    return service.get_consultant_by_id(consultant_id)


@consultants_router.put(
    "/{consultant_id}",
    response_model=ConsultantDTO,
    status_code=status.HTTP_200_OK,
    summary="Atualizar consultor com lock otimista",
)
def update_consultant(
    consultant_id: UUID,
    dto: ConsultantUpdateDTO,
    if_match: str = Header(..., alias="If-Match", description="Versão esperada do registro"),
    service: ConsultantService = Depends(get_consultant_service),
) -> ConsultantDTO:
    """Atualiza dados do consultor se o cabeçalho If-Match coincidir com a versão atual."""
    try:
        expected_version = int(if_match.strip().strip('"'))
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cabeçalho If-Match deve ser um número inteiro representando a versão.",
        )

    return service.update_consultant(
        consultant_id=consultant_id,
        dto=dto,
        expected_version=expected_version,
    )
