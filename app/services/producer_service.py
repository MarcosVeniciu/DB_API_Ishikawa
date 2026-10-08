from typing import List, Optional, Tuple
from uuid import UUID

from app.core.errors import (
    ConcurrencyConflictError,
    DuplicateEmailError,
    InvalidCredentialsError,
    NotFoundError,
)
from app.core.security import hash_password, verify_password
from app.db.models import Producer
from app.db.repositories.consultant_repo import ConsultantRepository
from app.db.repositories.producer_repo import ProducerRepository
from app.schemas.auth import (
    AuthChangePasswordResponse,
    AuthVerifyRequest,
    AuthVerifyResponse,
)
from app.schemas.producer import (
    ProducerCreateDTO,
    ProducerDTO,
    ProducerUpdateDTO,
)


class ProducerService:
    """Serviço de aplicação com regras de negócio, persistência e autenticação de produtores rurais.

    Gerencia o cadastro com hash seguro (bcrypt), consultas paginadas, vinculação com consultores,
    busca determinística por nome, verificação e alteração de senha e lock otimista.
    Ref: Obsidian note [[bdd-db-api-producers]], [[sdd-db-api-password-management]]
    """

    def __init__(
        self,
        repository: ProducerRepository,
        consultant_repository: Optional[ConsultantRepository] = None,
    ):
        self.repository = repository
        self.consultant_repository = consultant_repository

    def create_producer(self, dto: ProducerCreateDTO) -> ProducerDTO:
        """Cria um novo produtor com verificação de e-mail e hash seguro de senha."""
        existing = self.repository.get_by_email(str(dto.email))
        if existing:
            raise DuplicateEmailError(
                f"Produtor com e-mail '{dto.email}' ja cadastrado no sistema."
            )

        if dto.consultant_id and self.consultant_repository:
            consultant = self.consultant_repository.get_by_id(dto.consultant_id)
            if not consultant:
                raise NotFoundError(f"Consultor {dto.consultant_id} nao encontrado.")

        hashed = hash_password(dto.password.get_secret_value())
        producer = Producer(
            id=dto.id,
            email=str(dto.email).strip(),
            hashed_password=hashed,
            nome=dto.nome,
            id_fazenda=dto.id_fazenda,
            dados=dto.dados,
            consultant_id=dto.consultant_id,
            version=1,
        )
        created = self.repository.create(producer)
        return ProducerDTO.model_validate(created)

    def get_producer_by_id(self, producer_id: UUID) -> ProducerDTO:
        """Busca produtor por ID lançando NotFoundError caso não exista."""
        producer = self.repository.get_by_id(producer_id)
        if not producer:
            raise NotFoundError(f"Produtor {producer_id} nao encontrado.")
        return ProducerDTO.model_validate(producer)

    def get_producer_by_email(self, email: str) -> Optional[ProducerDTO]:
        """Busca produtor por e-mail retornando None caso não encontrado."""
        producer = self.repository.get_by_email(email)
        if not producer:
            return None
        return ProducerDTO.model_validate(producer)

    def find_producer_by_name(self, nome: str) -> Optional[ProducerDTO]:
        """Busca determinística de produtor por nome retornando o registro mais antigo."""
        producer = self.repository.find_by_name(nome)
        if not producer:
            return None
        return ProducerDTO.model_validate(producer)

    def list_producers(
        self,
        limit: int = 50,
        offset: int = 0,
        email: Optional[str] = None,
        nome: Optional[str] = None,
    ) -> Tuple[List[ProducerDTO], int]:
        """Lista produtores paginados com filtros opcionais de e-mail e nome."""
        items, total = self.repository.get_all(
            limit=limit,
            offset=offset,
            email=email,
            nome=nome,
        )
        return [ProducerDTO.model_validate(item) for item in items], total

    def update_producer(
        self,
        producer_id: UUID,
        dto: ProducerUpdateDTO,
        expected_version: int,
    ) -> ProducerDTO:
        """Atualiza dados cadastrais aplicando verificação atômica de versão (lock otimista)."""
        existing = self.repository.get_by_id(producer_id)
        if not existing:
            raise NotFoundError(f"Produtor {producer_id} nao encontrado.")

        if dto.consultant_id and self.consultant_repository:
            consultant = self.consultant_repository.get_by_id(dto.consultant_id)
            if not consultant:
                raise NotFoundError(f"Consultor {dto.consultant_id} nao encontrado.")

        updated = self.repository.update_atomic(
            producer_id=producer_id,
            nome=dto.nome,
            id_fazenda=dto.id_fazenda,
            dados=dto.dados,
            consultant_id=dto.consultant_id,
            expected_version=expected_version,
        )
        if not updated:
            raise ConcurrencyConflictError(
                f"Conflito de concorrencia para o produtor {producer_id}: "
                f"versao esperada {expected_version}, mas versao atual no banco e {existing.version}."
            )
        return ProducerDTO.model_validate(updated)

    def delete_producer(self, producer_id: UUID) -> None:
        """Remove produtor por ID lançando NotFoundError caso não exista."""
        existing = self.repository.get_by_id(producer_id)
        if not existing:
            raise NotFoundError(f"Produtor {producer_id} nao encontrado.")
        self.repository.delete(producer_id)

    def verify_credentials(self, dto: AuthVerifyRequest) -> AuthVerifyResponse:
        """Valida credenciais do produtor contra enumeração de usuários."""
        if dto.role != "producer":
            raise InvalidCredentialsError("Credenciais invalidas.")

        producer = self.repository.get_by_email(str(dto.email))
        if not producer:
            raise InvalidCredentialsError("Credenciais invalidas.")

        if not verify_password(dto.password.get_secret_value(), producer.hashed_password):
            raise InvalidCredentialsError("Credenciais invalidas.")

        return AuthVerifyResponse(id=producer.id, role="producer")

    def change_password(
        self,
        current_password: str,
        new_password: str,
        producer_id: Optional[UUID] = None,
        email: Optional[str] = None,
    ) -> AuthChangePasswordResponse:
        """Atualiza a senha do produtor após validar a senha atual com bcrypt."""
        producer = None
        if producer_id:
            producer = self.repository.get_by_id(producer_id)
        elif email:
            producer = self.repository.get_by_email(email)

        if not producer:
            raise InvalidCredentialsError("Credenciais invalidas.")

        if not verify_password(current_password, producer.hashed_password):
            raise InvalidCredentialsError("Credenciais invalidas.")

        new_hashed = hash_password(new_password)
        self.repository.update_password(producer.id, new_hashed)
        return AuthChangePasswordResponse(
            id=producer.id,
            role="producer",
            message="Senha atualizada com sucesso.",
        )
