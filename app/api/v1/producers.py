from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.core.security import verify_service_token
from app.db.repositories.consultant_repo import ConsultantRepository
from app.db.repositories.producer_repo import ProducerRepository
from app.db.session import get_db
from app.schemas.producer import (
    ProducerCreateDTO,
    ProducerDTO,
    ProducerUpdateDTO,
)
from app.services.producer_service import ProducerService

producers_router = APIRouter(
    prefix="/producers",
    tags=["Producers"],
    dependencies=[Depends(verify_service_token)],
)


def get_producer_service(db: Session = Depends(get_db)) -> ProducerService:
    """Dependency que constrói o serviço de produtores."""
    p_repo = ProducerRepository(db)
    c_repo = ConsultantRepository(db)
    return ProducerService(repository=p_repo, consultant_repository=c_repo)


@producers_router.post(
    "",
    response_model=ProducerDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Criar novo produtor",
)
def create_producer(
    dto: ProducerCreateDTO,
    service: ProducerService = Depends(get_producer_service),
) -> ProducerDTO:
    """Cria um novo produtor com integridade referencial e hash de senha seguro."""
    return service.create_producer(dto)


@producers_router.get(
    "",
    response_model=List[ProducerDTO],
    status_code=status.HTTP_200_OK,
    summary="Listar produtores paginados",
)
def list_producers(
    response: Response,
    limit: int = Query(50, ge=1, le=200, description="Limite máximo de 200 registros por página"),
    offset: int = Query(0, ge=0, description="Deslocamento para paginação"),
    email: Optional[str] = Query(None, description="Filtro opcional por e-mail"),
    nome: Optional[str] = Query(None, description="Filtro opcional por nome"),
    service: ProducerService = Depends(get_producer_service),
) -> List[ProducerDTO]:
    """Lista produtores paginados e adiciona cabeçalho X-Total-Count."""
    items, total = service.list_producers(
        limit=limit,
        offset=offset,
        email=email,
        nome=nome,
    )
    response.headers["X-Total-Count"] = str(total)
    return items


@producers_router.get(
    "/{producer_id}",
    response_model=ProducerDTO,
    status_code=status.HTTP_200_OK,
    summary="Buscar produtor por ID",
)
def get_producer_by_id(
    producer_id: UUID,
    service: ProducerService = Depends(get_producer_service),
) -> ProducerDTO:
    """Busca produtor por ID."""
    return service.get_producer_by_id(producer_id)


@producers_router.put(
    "/{producer_id}",
    response_model=ProducerDTO,
    status_code=status.HTTP_200_OK,
    summary="Atualizar produtor com lock otimista",
)
def update_producer(
    producer_id: UUID,
    dto: ProducerUpdateDTO,
    if_match: str = Header(..., alias="If-Match", description="Versão esperada do registro"),
    service: ProducerService = Depends(get_producer_service),
) -> ProducerDTO:
    """Atualiza dados do produtor se o cabeçalho If-Match coincidir com a versão atual."""
    try:
        expected_version = int(if_match.strip().strip('"'))
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cabeçalho If-Match deve ser um número inteiro representando a versão.",
        )

    return service.update_producer(
        producer_id=producer_id,
        dto=dto,
        expected_version=expected_version,
    )


@producers_router.delete(
    "/{producer_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Excluir produtor por ID",
)
def delete_producer(
    producer_id: UUID,
    service: ProducerService = Depends(get_producer_service),
) -> Response:
    """Exclui o produtor pelo identificador único retornando 204 sem corpo."""
    service.delete_producer(producer_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
