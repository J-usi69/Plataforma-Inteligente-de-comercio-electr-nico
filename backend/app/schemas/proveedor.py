from typing import Optional
from pydantic import BaseModel


class ProveedorCreate(BaseModel):
    nombre_empresa: str
    contacto: Optional[str] = None


class ProveedorUpdate(BaseModel):
    nombre_empresa: Optional[str] = None
    contacto: Optional[str] = None
    estado: Optional[bool] = None


class ProveedorOut(BaseModel):
    id: int
    nombre_empresa: str
    contacto: Optional[str] = None
    estado: bool

    class Config:
        from_attributes = True

