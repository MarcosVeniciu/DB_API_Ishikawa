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
from app.schemas.auth import (
    AuthChangePasswordResponse,
    AuthVerifyRequest,
    AuthVerifyResponse,
)
from app.schemas.consultant import (
    ConsultantCreateDTO,
    ConsultantDTO,
    ConsultantUpdateDTO,
)


class ConsultantService:
    """Serviço de aplicação com as regras de negócio de consultores e gestão de credenciais.

    Orquestra o ciclo de vida dos consultores, criação com hashing seguro (bcrypt),
    verificação de credenciais em tempo constante, alteração de senhas e controle otimista de concorrência.
    Ref: Obsidian note [[sdd-db-api-skeleton-consultants]], [[sdd-db-api-password-management]]
    """

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
        dto_out = ConsultantDTO.model_validate(created)
        dto_out.producers_managed = []
        return dto_out

    def get_consultant_by_id(self, consultant_id: UUID) -> ConsultantDTO:
        """Busca consultor por ID lançando NotFoundError caso não exista."""
        consultant = self.repository.get_by_id(consultant_id)
        if not consultant:
            raise NotFoundError(f"Consultor {consultant_id} nao encontrado.")
        dto_out = ConsultantDTO.model_validate(consultant)
        dto_out.producers_managed = self.repository.get_producers_managed(consultant_id)
        return dto_out

    def get_consultant_by_email(self, email: str) -> Optional[ConsultantDTO]:
        """Busca consultor por e-mail retornando None caso não encontrado."""
        consultant = self.repository.get_by_email(email)
        if not consultant:
            return None
        dto_out = ConsultantDTO.model_validate(consultant)
        dto_out.producers_managed = self.repository.get_producers_managed(consultant.id)
        return dto_out

    def list_consultants(
        self,
        limit: int = 50,
        offset: int = 0,
        email: Optional[str] = None,
    ) -> Tuple[List[ConsultantDTO], int]:
        """Lista consultores paginados."""
        items, total = self.repository.get_all(limit=limit, offset=offset, email=email)
        dtos = []
        for item in items:
            dto_out = ConsultantDTO.model_validate(item)
            dto_out.producers_managed = self.repository.get_producers_managed(item.id)
            dtos.append(dto_out)
        return dtos, total

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
        dto_out = ConsultantDTO.model_validate(updated)
        dto_out.producers_managed = self.repository.get_producers_managed(updated.id)
        return dto_out

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

    def change_password(
        self,
        current_password: str,
        new_password: str,
        consultant_id: Optional[UUID] = None,
        email: Optional[str] = None,
    ) -> AuthChangePasswordResponse:
        """Atualiza a senha do consultor após validar a senha atual com bcrypt."""
        consultant = None
        if consultant_id:
            consultant = self.repository.get_by_id(consultant_id)
        elif email:
            consultant = self.repository.get_by_email(email)

        if not consultant:
            raise InvalidCredentialsError("Credenciais invalidas.")

        if not verify_password(current_password, consultant.hashed_password):
            raise InvalidCredentialsError("Credenciais invalidas.")

        new_hashed = hash_password(new_password)
        self.repository.update_password(consultant.id, new_hashed)
        return AuthChangePasswordResponse(
            id=consultant.id,
            role="consultant",
            message="Senha atualizada com sucesso.",
        )
