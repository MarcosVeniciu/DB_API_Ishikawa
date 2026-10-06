from datetime import datetime, timezone
from typing import List, Optional, Tuple
from uuid import UUID
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session
from app.db.models import Consultant


class ConsultantRepository:
    """Repositório de persistência para consultores via SQLAlchemy."""

    def __init__(self, session: Session):
        self.session = session

    def create(self, consultant: Consultant) -> Consultant:
        """Persiste um novo consultor no banco de dados."""
        self.session.add(consultant)
        self.session.commit()
        self.session.refresh(consultant)
        return consultant

    def get_by_id(self, consultant_id: UUID) -> Optional[Consultant]:
        """Busca consultor por chave primária UUID."""
        stmt = select(Consultant).where(Consultant.id == consultant_id)
        return self.session.execute(stmt).scalar_one_or_none()

    def get_by_email(self, email: str) -> Optional[Consultant]:
        """Busca consultor por e-mail (normalizado com strip e case-insensitive via CITEXT)."""
        normalized_email = email.strip()
        stmt = select(Consultant).where(Consultant.email == normalized_email)
        return self.session.execute(stmt).scalar_one_or_none()

    def get_all(
        self,
        limit: int = 50,
        offset: int = 0,
        email: Optional[str] = None,
    ) -> Tuple[List[Consultant], int]:
        """Retorna lista paginada de consultores e a contagem total."""
        query = select(Consultant)
        count_query = select(func.count(Consultant.id))

        if email:
            normalized_email = email.strip()
            query = query.where(Consultant.email == normalized_email)
            count_query = count_query.where(Consultant.email == normalized_email)

        total = self.session.execute(count_query).scalar() or 0
        items = (
            self.session.execute(
                query.order_by(Consultant.created_at.asc()).offset(offset).limit(limit)
            )
            .scalars()
            .all()
        )
        return list(items), total

    def update_atomic(
        self,
        consultant_id: UUID,
        nome: str,
        expected_version: int,
    ) -> Optional[Consultant]:
        """Atualiza o nome do consultor se a versão bater (lock otimista atômico)."""
        stmt = (
            update(Consultant)
            .where(
                Consultant.id == consultant_id,
                Consultant.version == expected_version,
            )
            .values(
                nome=nome,
                version=Consultant.version + 1,
                updated_at=datetime.now(timezone.utc),
            )
            .returning(Consultant)
        )
        result = self.session.execute(stmt)
        updated = result.scalar_one_or_none()
        if updated:
            self.session.commit()
        return updated
