from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr


class AuthVerifyRequest(BaseModel):
    """Payload de entrada para verificação segura de credenciais."""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: SecretStr
    role: str = Field(..., pattern="^(consultant|producer)$")


class AuthVerifyResponse(BaseModel):
    """Resposta com confirmação de identidade do usuário autenticado."""

    id: UUID
    role: str
