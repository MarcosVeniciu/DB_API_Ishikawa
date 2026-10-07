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


class AuthChangePasswordRequest(BaseModel):
    """Payload de entrada para atualização de senha de produtores e consultores."""

    model_config = ConfigDict(extra="forbid")

    role: str = Field(..., pattern="^(consultant|producer)$")
    id: UUID | None = None
    email: EmailStr | None = None
    current_password: SecretStr = Field(..., min_length=1)
    new_password: SecretStr = Field(..., min_length=6)

    def model_post_init(self, __context: object) -> None:
        if not self.id and not self.email:
            raise ValueError("Ao menos 'id' ou 'email' deve ser fornecido para identificar o usuário.")


class AuthChangePasswordResponse(BaseModel):
    """Resposta com confirmação de atualização de senha."""

    id: UUID
    role: str
    message: str = "Senha atualizada com sucesso."
