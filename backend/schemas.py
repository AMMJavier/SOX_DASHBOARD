from datetime import date
from pydantic import BaseModel, Field
from typing import Optional


class ValidationResponse(BaseModel):
    id: int
    #vpn: str
    #solicitante: str | None = None
    req: Optional[str] = None
    manager: str
    department: Optional[str] = None
    status: str
    decision: Optional[str] = None
    observation: Optional[str] = None
    deadline: Optional[date] = None

    class Config:
        from_attributes = True


class ValidationUpdate(BaseModel):
    decision: Optional[str] = None
    observation: Optional[str] = None
    status: Optional[str] = None

class UserResponse(BaseModel):
    id: int
    name: str
    username: str
    role: str

    class Config:
        from_attributes = True



class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    rol: str

class ChangePasswordRequest(BaseModel):
    password_actual: str
    password_nueva: str

class ValidationConfirmAllItem(BaseModel):
    checkpoint_uid: str
    decision: str
    observation: Optional[str] = None


class ValidationConfirmAllRequest(BaseModel):
    validations: list[ValidationConfirmAllItem]

# ---- Administración de usuarios SOX / Assets ----
from pydantic import field_validator, model_validator
from typing import Literal


class CreateUserRequest(BaseModel):
    username: str
    auth_provider: Literal["local", "ldap"]
    rol: Literal["administrador", "gerencial", "desarrollador", "assets_admin", "assets_viewer"]
    password: Optional[str] = None

    @field_validator("username")
    @classmethod
    def validar_username(cls, value: str) -> str:
        import re
        value = value.strip().lower()
        if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{2,99}", value):
            raise ValueError("username debe contener entre 3 y 100 caracteres: letras, números, punto, guion o guion bajo")
        return value

    @model_validator(mode="after")
    def validar_contrasena(self):
        if self.auth_provider == "local":
            if not self.password or len(self.password) < 8:
                raise ValueError("Los usuarios locales requieren contraseña de al menos 8 caracteres")
            if len(self.password.encode("utf-8")) > 72:
                raise ValueError("La contraseña local supera el máximo de 72 bytes permitido por bcrypt")
        elif self.password:
            raise ValueError("No se debe enviar contraseña al crear usuarios LDAP")
        return self


class UsuarioAdminResponse(BaseModel):
    id: int
    username: str
    auth_provider: str
    rol: str
    activo: int

    class Config:
        from_attributes = True


class UsuarioEstadoRequest(BaseModel):
    activo: bool

class ResetUserPasswordRequest(BaseModel):
    # Mismo nombre que envía el frontend (usersService.resetUserPassword) y que lee auth/users.py.
    password_nueva: str = Field(min_length=8)