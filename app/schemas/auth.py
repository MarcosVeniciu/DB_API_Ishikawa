from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr


class AuthVerifyRequest(BaseModel):
    """Payload de entrada para verificação segura de credenciais de login.

    Valida o papel informado ('consultant' ou 'producer'), e-mail e senha.
    Ref: Obsidian note [[sdd-db-api-password-management]]
    """

    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: SecretStr
    role: str = Field(..., pattern="^(consultant|producer)$")


class AuthVerifyResponse(BaseModel):
    """Resposta com confirmação de identidade do usuário autenticado.

    Retorna o identificador único e papel após validação bem-sucedida de credenciais.
    Ref: Obsidian note [[sdd-db-api-password-management]]
    """

    id: UUID
    role: str


class AuthChangePasswordRequest(BaseModel):
    """Payload de entrada para atualização de senha de produtores e consultores.

    Exige a senha atual para validação prévia e nova senha com requisitos de complexidade.
    Ref: Obsidian note [[sdd-db-api-password-management]]
    """

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
    """Resposta com confirmação de atualização de senha.

    Retorna o identificador do usuário, perfil e mensagem de sucesso da operação.
    Ref: Obsidian note [[sdd-db-api-password-management]]
    """

    id: UUID
    role: str
    message: str = "Senha atualizada com sucesso."
