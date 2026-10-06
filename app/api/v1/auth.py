from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.security import verify_service_token
from app.db.repositories.consultant_repo import ConsultantRepository
from app.db.session import get_db
from app.schemas.auth import AuthVerifyRequest, AuthVerifyResponse
from app.services.consultant_service import ConsultantService

auth_router = APIRouter(
    prefix="/auth",
    tags=["Auth"],
    dependencies=[Depends(verify_service_token)],
)


def get_auth_service(db: Session = Depends(get_db)) -> ConsultantService:
    repository = ConsultantRepository(db)
    return ConsultantService(repository)


@auth_router.post(
    "/verify",
    response_model=AuthVerifyResponse,
    status_code=status.HTTP_200_OK,
    summary="Verificar credenciais de usuário",
)
def verify_credentials(
    dto: AuthVerifyRequest,
    service: ConsultantService = Depends(get_auth_service),
) -> AuthVerifyResponse:
    """Verifica credenciais com bcrypt e retorna ID e papel sem vazar hash."""
    return service.verify_credentials(dto)
