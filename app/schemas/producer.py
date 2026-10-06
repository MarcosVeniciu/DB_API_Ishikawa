from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr


class ProducerCreateDTO(BaseModel):
    """Payload de entrada para criação de produtor (POST /v1/producers)."""

    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4, description="UUID gerado pelo cliente")
    email: EmailStr = Field(..., description="E-mail único do produtor")
    password: SecretStr = Field(
        ...,
        min_length=6,
        description="Senha em texto puro para hash exclusivo no DB_API",
    )
    nome: str = Field(..., min_length=1, max_length=255)
    id_fazenda: Optional[str] = Field(None, max_length=100)
    dados: Dict[str, Any] = Field(
        default_factory=dict,
        description="Dados agronômicos flexíveis em formato JSON",
    )
    consultant_id: Optional[UUID] = Field(
        None,
        description="FK opcional para o consultor responsável",
    )


class ProducerUpdateDTO(BaseModel):
    """Payload de entrada para atualização cadastral de produtor (PUT /v1/producers/{id}).

    Nota: email e senha permanecem estritamente imutáveis neste endpoint.
    """

    model_config = ConfigDict(extra="forbid")

    nome: str = Field(..., min_length=1, max_length=255)
    id_fazenda: Optional[str] = Field(None, max_length=100)
    dados: Dict[str, Any] = Field(
        default_factory=dict,
        description="Dados agronômicos flexíveis em formato JSON",
    )
    consultant_id: Optional[UUID] = Field(
        None,
        description="FK opcional para o consultor responsável",
    )


class ProducerDTO(BaseModel):
    """DTO de saída para produtores — nunca expõe hash ou senha."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    nome: str
    id_fazenda: Optional[str] = None
    dados: Dict[str, Any] = Field(default_factory=dict)
    consultant_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    version: int = Field(default=1, description="Número de versão para lock otimista")
