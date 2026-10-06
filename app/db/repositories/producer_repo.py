from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session
from app.db.models import Producer


class ProducerRepository:
    """Repositório de persistência para produtores rurais via SQLAlchemy."""

    def __init__(self, session: Session):
        self.session = session

    def create(self, producer: Producer) -> Producer:
        """Persiste um novo produtor no banco de dados."""
        self.session.add(producer)
        self.session.commit()
        self.session.refresh(producer)
        return producer

    def get_by_id(self, producer_id: UUID) -> Optional[Producer]:
        """Busca produtor por chave primária UUID."""
        stmt = select(Producer).where(Producer.id == producer_id)
        return self.session.execute(stmt).scalar_one_or_none()

    def get_by_email(self, email: str) -> Optional[Producer]:
        """Busca produtor por e-mail (case-insensitive via CITEXT)."""
        normalized_email = email.strip()
        stmt = select(Producer).where(Producer.email == normalized_email)
        return self.session.execute(stmt).scalar_one_or_none()

    def find_by_name(self, nome: str) -> Optional[Producer]:
        """Busca determinística de produtor por nome retornando o registro mais antigo."""
        normalized_nome = nome.strip()
        stmt = (
            select(Producer)
            .where(func.lower(Producer.nome) == func.lower(normalized_nome))
            .order_by(Producer.created_at.asc())
            .limit(1)
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def get_all(
        self,
        limit: int = 50,
        offset: int = 0,
        email: Optional[str] = None,
        nome: Optional[str] = None,
    ) -> Tuple[List[Producer], int]:
        """Retorna lista paginada de produtores e a contagem total filtrada."""
        query = select(Producer)
        count_query = select(func.count(Producer.id))

        if email:
            normalized_email = email.strip()
            query = query.where(Producer.email == normalized_email)
            count_query = count_query.where(Producer.email == normalized_email)

        if nome:
            normalized_nome = nome.strip()
            query = query.where(func.lower(Producer.nome) == func.lower(normalized_nome))
            count_query = count_query.where(func.lower(Producer.nome) == func.lower(normalized_nome))

        total = self.session.execute(count_query).scalar() or 0
        items = (
            self.session.execute(
                query.order_by(Producer.created_at.asc()).offset(offset).limit(limit)
            )
            .scalars()
            .all()
        )
        return list(items), total

    def update_atomic(
        self,
        producer_id: UUID,
        nome: str,
        id_fazenda: Optional[str],
        dados: Dict[str, Any],
        consultant_id: Optional[UUID],
        expected_version: int,
    ) -> Optional[Producer]:
        """Atualiza dados do produtor atomicamente se a versão bater (lock otimista)."""
        stmt = (
            update(Producer)
            .where(
                Producer.id == producer_id,
                Producer.version == expected_version,
            )
            .values(
                nome=nome,
                id_fazenda=id_fazenda,
                dados=dados,
                consultant_id=consultant_id,
                version=Producer.version + 1,
                updated_at=datetime.now(timezone.utc),
            )
            .returning(Producer)
        )
        result = self.session.execute(stmt)
        updated = result.scalar_one_or_none()
        if updated:
            self.session.commit()
        return updated

    def delete(self, producer_id: UUID) -> bool:
        """Remove o produtor por ID se existir."""
        producer = self.get_by_id(producer_id)
        if not producer:
            return False
        self.session.delete(producer)
        self.session.commit()
        return True

    def get_producers_managed_by_consultant(self, consultant_id: UUID) -> List[UUID]:
        """Retorna lista de UUIDs dos produtores gerenciados por um consultor."""
        stmt = (
            select(Producer.id)
            .where(Producer.consultant_id == consultant_id)
            .order_by(Producer.created_at.asc())
        )
        return list(self.session.execute(stmt).scalars().all())
