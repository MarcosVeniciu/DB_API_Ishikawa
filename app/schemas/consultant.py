from datetime import datetime
from typing import List
from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr


class ConsultantCreateDTO(BaseModel):
    """Payload de entrada para criação de consultor (POST)."""

    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4, description="UUID gerado pelo cliente")
    nome: str = Field(..., min_length=1, max_length=255)
    email: EmailStr = Field(..., description="E-mail único do consultor")
    password: SecretStr = Field(
        ...,
        min_length=6,
        description="Senha em texto puro para hash exclusivo no DB_API",
    )


class ConsultantUpdateDTO(BaseModel):
    """Payload de entrada para atualização de consultor (PUT)."""

    model_config = ConfigDict(extra="forbid")

    nome: str = Field(..., min_length=1, max_length=255)


class ConsultantDTO(BaseModel):
    """DTO de saída — nunca expõe hash ou senha."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nome: str
    email: EmailStr
    producers_managed: List[UUID] = Field(
        default_factory=list,
        description="Lista de UUIDs derivada via FK em F2",
    )
    version: int = Field(default=1, description="Número de versão para lock otimista")
    created_at: datetime
