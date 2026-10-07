from datetime import datetime, timezone
from typing import Optional, Tuple
from uuid import UUID
from app.core.errors import ConcurrencyConflictError, NotFoundError, PreconditionRequiredError
from app.db.models import DiagnosticResult
from app.db.repositories.diagnostic_result_repo import DiagnosticResultRepository
from app.db.repositories.producer_repo import ProducerRepository
from app.schemas.diagnostic_result import DiagnosticResultDTO, DiagnosticResultSaveDTO


class DiagnosticResultService:
    """Serviço de aplicação para gestão de resultados de diagnóstico e simulação."""

    def __init__(
        self,
        diagnostic_repo: DiagnosticResultRepository,
        producer_repo: ProducerRepository,
    ):
        self.diagnostic_repo = diagnostic_repo
        self.producer_repo = producer_repo

    def get_by_producer_id(self, producer_id: UUID) -> DiagnosticResultDTO:
        """Busca o resultado de diagnóstico de um produtor."""
        result = self.diagnostic_repo.get_by_producer_id(producer_id)
        if not result:
            raise NotFoundError(f"Diagnostic result for producer '{producer_id}' not found.")
        return DiagnosticResultDTO.model_validate(result)

    def save_diagnostic_result(
        self,
        producer_id: UUID,
        dto: DiagnosticResultSaveDTO,
        expected_version: Optional[int] = None,
    ) -> Tuple[DiagnosticResultDTO, bool]:
        """Salva ou atualiza atomicamente o diagnóstico (upsert condicional com lock otimista).

        Retorna (DiagnosticResultDTO, created: bool), onde created=True indica inserção (201)
        e created=False indica atualização (200).
        """
        # 1. Validação prévia de existência do produtor
        producer = self.producer_repo.get_by_id(producer_id)
        if not producer:
            raise NotFoundError(f"Producer with id '{producer_id}' not found.")

        # 2. Verifica se o diagnóstico já existe
        existing = self.diagnostic_repo.get_by_producer_id(producer_id)

        # 3. Criação inicial (não existe diagnóstico)
        if not existing:
            new_model = DiagnosticResult(
                producer_id=producer_id,
                input_data=dto.input_data,
                diagnostico=dto.diagnostico,
                simulacao=dto.simulacao,
                version=1,
                updated_at=datetime.now(timezone.utc),
            )
            created_model = self.diagnostic_repo.create(new_model)
            return DiagnosticResultDTO.model_validate(created_model), True

        # 4. Atualização de diagnóstico existente
        if expected_version is None:
            raise PreconditionRequiredError(
                "Header 'If-Match' is required to update an existing diagnostic result."
            )

        updated_model = self.diagnostic_repo.update_atomic(
            producer_id=producer_id,
            dto=dto,
            expected_version=expected_version,
        )

        if not updated_model:
            raise ConcurrencyConflictError(
                f"Version mismatch: current version of diagnostic result for producer '{producer_id}' does not match {expected_version}."
            )

        return DiagnosticResultDTO.model_validate(updated_model), False
