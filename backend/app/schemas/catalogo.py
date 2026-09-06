from typing import Optional
from pydantic import BaseModel


class CategoriaOut(BaseModel):
    id: int
    nombre: str
    descripcion: Optional[str] = None
    estado: bool

    class Config:
        from_attributes = True


class ColeccionOut(BaseModel):
    id: int
    nombre: str
    descripcion: Optional[str] = None
    temporada_id: int
    estado: bool

    class Config:
        from_attributes = True


class PrendaCreate(BaseModel):
    nombre: str
    descripcion: Optional[str] = None
    categoria_id: int
    coleccion_id: Optional[int] = None
    proveedor_id: Optional[int] = None
    precio_base: float
    modelo_3d_url: Optional[str] = None


class PrendaUpdate(BaseModel):
    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    categoria_id: Optional[int] = None
    coleccion_id: Optional[int] = None
    proveedor_id: Optional[int] = None
    precio_base: Optional[float] = None
    modelo_3d_url: Optional[str] = None
    estado: Optional[bool] = None


class PrendaOut(BaseModel):
    id: int
    nombre: str
    descripcion: Optional[str] = None
    categoria_id: int
    coleccion_id: Optional[int] = None
    proveedor_id: Optional[int] = None
    precio_base: float
    modelo_3d_url: Optional[str] = None
    estado: bool
    categoria_nombre: Optional[str] = None
    coleccion_nombre: Optional[str] = None
    proveedor_nombre: Optional[str] = None

    class Config:
        from_attributes = True

