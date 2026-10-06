from typing import Any
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.errors import InvalidCredentialsError
from app.core.security import verify_service_token
from app.db.repositories.consultant_repo import ConsultantRepository
from app.db.repositories.producer_repo import ProducerRepository
from app.db.session import get_db
from app.schemas.auth import AuthVerifyRequest, AuthVerifyResponse
from app.services.consultant_service import ConsultantService
from app.services.producer_service import ProducerService

auth_router = APIRouter(
    prefix="/auth",
    tags=["Auth"],
    dependencies=[Depends(verify_service_token)],
)


class AuthService:
    """Serviço unificado de verificação de credenciais."""

    def __init__(self, db: Session):
        self.consultant_service = ConsultantService(ConsultantRepository(db))
        self.producer_service = ProducerService(ProducerRepository(db))

    def verify_credentials(self, dto: AuthVerifyRequest) -> AuthVerifyResponse:
        if dto.role == "consultant":
            return self.consultant_service.verify_credentials(dto)
        elif dto.role == "producer":
            return self.producer_service.verify_credentials(dto)
        raise InvalidCredentialsError("Credenciais invalidas.")


def get_auth_service(db: Session = Depends(get_db)) -> Any:
    return AuthService(db)


@auth_router.post(
    "/verify",
    response_model=AuthVerifyResponse,
    status_code=status.HTTP_200_OK,
    summary="Verificar credenciais de usuário",
)
def verify_credentials(
    dto: AuthVerifyRequest,
    service: Any = Depends(get_auth_service),
) -> AuthVerifyResponse:
    """Verifica credenciais com bcrypt e retorna ID e papel sem vazar hash."""
    return service.verify_credentials(dto)

