from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import CITEXT, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.session import Base


class Consultant(Base):
    """Modelo ORM para a tabela de consultores."""

    __tablename__ = "consultants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    nome: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(CITEXT, unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relacionamento 1:N com produtores gerenciados
    producers: Mapped[List["Producer"]] = relationship(
        "Producer",
        back_populates="consultant",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Consultant(id={self.id}, email='{self.email}', version={self.version})>"


class Producer(Base):
    """Modelo ORM para a tabela de produtores rurais."""

    __tablename__ = "producers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    email: Mapped[str] = mapped_column(CITEXT, unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    nome: Mapped[str] = mapped_column(String(255), nullable=False)
    id_fazenda: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    dados: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )
    consultant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("consultants.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relacionamento N:1 com o consultor responsável
    consultant: Mapped[Optional["Consultant"]] = relationship(
        "Consultant",
        back_populates="producers",
    )

    # Relacionamento 1:1 com o resultado de diagnóstico
    diagnostic_result: Mapped[Optional["DiagnosticResult"]] = relationship(
        "DiagnosticResult",
        back_populates="producer",
        uselist=False,
        passive_deletes=True,
    )

    __table_args__ = (
        Index("ix_producers_lower_nome", func.lower(nome)),
    )

    def __repr__(self) -> str:
        return f"<Producer(id={self.id}, email='{self.email}', nome='{self.nome}', version={self.version})>"


class DiagnosticResult(Base):
    """Modelo ORM para a tabela de resultados de diagnósticos."""

    __tablename__ = "diagnostic_results"

    producer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("producers.id", ondelete="CASCADE"),
        primary_key=True,
    )
    input_data: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )
    diagnostico: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
    )
    simulacao: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relacionamento 1:1 com o produtor proprietário
    producer: Mapped["Producer"] = relationship(
        "Producer",
        back_populates="diagnostic_result",
    )

    def __repr__(self) -> str:
        return f"<DiagnosticResult(producer_id={self.producer_id}, version={self.version})>"

