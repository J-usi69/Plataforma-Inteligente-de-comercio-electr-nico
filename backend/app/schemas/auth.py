from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field


class UsuarioRegister(BaseModel):
    correo: EmailStr
    password: str = Field(..., min_length=6)
    celular: Optional[str] = None


class UsuarioLogin(BaseModel):
    login: str  # Puede ser correo o celular
    password: str


class UsuarioUpdate(BaseModel):
    celular: Optional[str] = None
    estado: Optional[bool] = None


class PersonalBriefOut(BaseModel):
    id: int
    nombres: str
    apellidos: str
    cargo: str
    sucursal_id: Optional[int] = None
    sucursal_nombre: Optional[str] = None

    class Config:
        from_attributes = True


class ProveedorBriefOut(BaseModel):
    id: int
    nombre_empresa: str
    contacto: Optional[str] = None

    class Config:
        from_attributes = True


class UsuarioOut(BaseModel):
    id: int
    correo: str
    celular: Optional[str] = None
    estado: bool
    roles: List[str] = []
    permisos: List[str] = []
    creado_en: Optional[datetime] = None
    personal: Optional[PersonalBriefOut] = None
    proveedor: Optional[ProveedorBriefOut] = None

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario: UsuarioOut


class BitacoraOut(BaseModel):
    id: int
    usuario_id: int
    accion: str
    ip: Optional[str] = None
    fecha: datetime

    class Config:
        from_attributes = True
