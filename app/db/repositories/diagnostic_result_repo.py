from datetime import datetime, timezone
from typing import Optional
from uuid import UUID
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session
from app.db.models import DiagnosticResult
from app.schemas.diagnostic_result import DiagnosticResultSaveDTO


class DiagnosticResultRepository:
    """Repositório de persistência para resultados de diagnósticos via SQLAlchemy.

    Gerencia o ciclo de vida dos diagnósticos (input_data, parecer, simulação),
    executando atualizações atômicas com verificação estrita de versão (lock otimista).
    Ref: Obsidian note [[audit-persistencia-resultados]]
    """

    def __init__(self, session: Session):
        self.session = session

    def create(self, result: DiagnosticResult) -> DiagnosticResult:
        """Persiste um novo resultado de diagnóstico no banco de dados."""
        self.session.add(result)
        self.session.commit()
        self.session.refresh(result)
        return result

    def get_by_producer_id(self, producer_id: UUID) -> Optional[DiagnosticResult]:
        """Busca resultado de diagnóstico por chave primária producer_id."""
        stmt = select(DiagnosticResult).where(DiagnosticResult.producer_id == producer_id)
        return self.session.execute(stmt).scalar_one_or_none()

    def update_atomic(
        self,
        producer_id: UUID,
        dto: DiagnosticResultSaveDTO,
        expected_version: int,
    ) -> Optional[DiagnosticResult]:
        """Atualiza diagnóstico atomicamente se a versão bater (lock otimista)."""
        stmt = (
            update(DiagnosticResult)
            .where(
                DiagnosticResult.producer_id == producer_id,
                DiagnosticResult.version == expected_version,
            )
            .values(
                input_data=dto.input_data,
                diagnostico=dto.diagnostico,
                simulacao=dto.simulacao,
                version=DiagnosticResult.version + 1,
                updated_at=datetime.now(timezone.utc),
            )
            .returning(DiagnosticResult)
        )
        result = self.session.execute(stmt)
        updated = result.scalar_one_or_none()
        if updated:
            self.session.commit()
        return updated

    def delete_by_producer_id(self, producer_id: UUID) -> bool:
        """Remove o diagnóstico por producer_id se existir."""
        stmt = (
            delete(DiagnosticResult)
            .where(DiagnosticResult.producer_id == producer_id)
        )
        result = self.session.execute(stmt)
        if result.rowcount > 0:
            self.session.commit()
            return True
        return False
