from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel


class ProveedorCreate(BaseModel):
    nombre_empresa: str
    contacto: Optional[str] = None
    correo: Optional[str] = None
    password: Optional[str] = None


class ProveedorUpdate(BaseModel):
    nombre_empresa: Optional[str] = None
    contacto: Optional[str] = None
    estado: Optional[bool] = None


class ProveedorOut(BaseModel):
    id: int
    nombre_empresa: str
    contacto: Optional[str] = None
    estado: bool
    correo: Optional[str] = None
    celular: Optional[str] = None

    class Config:
        from_attributes = True


class PrendaProveedorCreate(BaseModel):
    nombre: str
    descripcion: Optional[str] = None
    categoria_id: int
    precio_base: float
    modelo_3d_url: Optional[str] = None
    forzar: bool = False


class DisponibilidadCreate(BaseModel):
    cantidad: int
    fecha_estimada: date


class DisponibilidadOut(BaseModel):
    id: int
    prenda_id: int
    prenda_nombre: str
    cantidad: int
    fecha_estimada: date
    fecha_registro: datetime

    class Config:
        from_attributes = True
