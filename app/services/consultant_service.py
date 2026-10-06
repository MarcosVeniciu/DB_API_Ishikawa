from typing import List, Optional, Tuple
from uuid import UUID

from app.core.errors import (
    ConcurrencyConflictError,
    DuplicateEmailError,
    InvalidCredentialsError,
    NotFoundError,
)
from app.core.security import hash_password, verify_password
from app.db.models import Consultant
from app.db.repositories.consultant_repo import ConsultantRepository
from app.schemas.auth import AuthVerifyRequest, AuthVerifyResponse
from app.schemas.consultant import (
    ConsultantCreateDTO,
    ConsultantDTO,
    ConsultantUpdateDTO,
)


class ConsultantService:
    """Serviço com as regras de negócio de consultores e controle de autenticação."""

    def __init__(self, repository: ConsultantRepository):
        self.repository = repository

    def create_consultant(self, dto: ConsultantCreateDTO) -> ConsultantDTO:
        """Cria um novo consultor garantindo unicidade de e-mail e hash bcrypt."""
        existing = self.repository.get_by_email(str(dto.email))
        if existing:
            raise DuplicateEmailError(
                f"Consultor com e-mail '{dto.email}' ja cadastrado no sistema."
            )

        hashed = hash_password(dto.password.get_secret_value())
        consultant = Consultant(
            id=dto.id,
            nome=dto.nome,
            email=str(dto.email).strip(),
            hashed_password=hashed,
            version=1,
        )
        created = self.repository.create(consultant)
        return ConsultantDTO.model_validate(created)

    def get_consultant_by_id(self, consultant_id: UUID) -> ConsultantDTO:
        """Busca consultor por ID lançando NotFoundError caso não exista."""
        consultant = self.repository.get_by_id(consultant_id)
        if not consultant:
            raise NotFoundError(f"Consultor {consultant_id} nao encontrado.")
        return ConsultantDTO.model_validate(consultant)

    def get_consultant_by_email(self, email: str) -> Optional[ConsultantDTO]:
        """Busca consultor por e-mail retornando None caso não encontrado."""
        consultant = self.repository.get_by_email(email)
        if not consultant:
            return None
        return ConsultantDTO.model_validate(consultant)

    def list_consultants(
        self,
        limit: int = 50,
        offset: int = 0,
        email: Optional[str] = None,
    ) -> Tuple[List[ConsultantDTO], int]:
        """Lista consultores paginados."""
        items, total = self.repository.get_all(limit=limit, offset=offset, email=email)
        return [ConsultantDTO.model_validate(item) for item in items], total

    def update_consultant(
        self,
        consultant_id: UUID,
        dto: ConsultantUpdateDTO,
        expected_version: int,
    ) -> ConsultantDTO:
        """Atualiza consultor aplicando verificação atômica de versão (lock otimista)."""
        existing = self.repository.get_by_id(consultant_id)
        if not existing:
            raise NotFoundError(f"Consultor {consultant_id} nao encontrado.")

        updated = self.repository.update_atomic(
            consultant_id=consultant_id,
            nome=dto.nome,
            expected_version=expected_version,
        )
        if not updated:
            raise ConcurrencyConflictError(
                f"Conflito de concorrencia para o consultor {consultant_id}: "
                f"versao esperada {expected_version}, mas versao atual no banco e {existing.version}."
            )
        return ConsultantDTO.model_validate(updated)

    def verify_credentials(self, dto: AuthVerifyRequest) -> AuthVerifyResponse:
        """Valida credenciais do consultor de forma segura contra enumeração."""
        if dto.role != "consultant":
            raise InvalidCredentialsError("Credenciais invalidas.")

        consultant = self.repository.get_by_email(str(dto.email))
        if not consultant:
            # Resposta idêntica sem vazar existência de usuário
            raise InvalidCredentialsError("Credenciais invalidas.")

        if not verify_password(dto.password.get_secret_value(), consultant.hashed_password):
            raise InvalidCredentialsError("Credenciais invalidas.")

        return AuthVerifyResponse(id=consultant.id, role="consultant")
