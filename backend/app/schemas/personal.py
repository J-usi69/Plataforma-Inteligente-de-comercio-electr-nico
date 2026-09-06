from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class PersonalCreate(BaseModel):
    nombres: str
    apellidos: str
    cargo: str  # Encargado o Cajero
    sucursal_id: Optional[int] = None
    correo: EmailStr
    celular: Optional[str] = None
    password: str = Field(..., min_length=6)


class PersonalUpdate(BaseModel):
    nombres: Optional[str] = None
    apellidos: Optional[str] = None
    cargo: Optional[str] = None
    sucursal_id: Optional[int] = None
    estado: Optional[bool] = None
    celular: Optional[str] = None


class PersonalOut(BaseModel):
    id: int
    usuario_id: int
    sucursal_id: Optional[int] = None
    nombres: str
    apellidos: str
    cargo: str
    estado: bool
    correo: Optional[str] = None
    celular: Optional[str] = None
    sucursal_nombre: Optional[str] = None

    class Config:
        from_attributes = True

