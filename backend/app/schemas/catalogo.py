from datetime import date
from typing import Optional
from pydantic import BaseModel


# --- CU-09: Categorías, Tallas y Colores ---
class CategoriaCreate(BaseModel):
    nombre: str
    descripcion: Optional[str] = None


class CategoriaUpdate(BaseModel):
    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    estado: Optional[bool] = None


class CategoriaOut(BaseModel):
    id: int
    nombre: str
    descripcion: Optional[str] = None
    estado: bool

    class Config:
        from_attributes = True


class TallaCreate(BaseModel):
    nombre: str


class TallaUpdate(BaseModel):
    nombre: Optional[str] = None


class TallaOut(BaseModel):
    id: int
    nombre: str

    class Config:
        from_attributes = True


class ColorCreate(BaseModel):
    nombre: str
    hex: Optional[str] = None


class ColorUpdate(BaseModel):
    nombre: Optional[str] = None
    hex: Optional[str] = None


class ColorOut(BaseModel):
    id: int
    nombre: str
    hex: Optional[str] = None

    class Config:
        from_attributes = True


# --- CU-10: Temporadas y Colecciones ---
class TemporadaCreate(BaseModel):
    nombre: str
    tipo: Optional[str] = None
    fecha_inicio: Optional[date] = None
    fecha_fin: Optional[date] = None


class TemporadaUpdate(BaseModel):
    nombre: Optional[str] = None
    tipo: Optional[str] = None
    fecha_inicio: Optional[date] = None
    fecha_fin: Optional[date] = None
    estado: Optional[bool] = None


class TemporadaOut(BaseModel):
    id: int
    nombre: str
    tipo: Optional[str] = None
    fecha_inicio: Optional[date] = None
    fecha_fin: Optional[date] = None
    estado: bool

    class Config:
        from_attributes = True


class ColeccionCreate(BaseModel):
    nombre: str
    descripcion: Optional[str] = None
    temporada_id: int


class ColeccionUpdate(BaseModel):
    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    temporada_id: Optional[int] = None
    estado: Optional[bool] = None


class ColeccionOut(BaseModel):
    id: int
    nombre: str
    descripcion: Optional[str] = None
    temporada_id: int
    estado: bool
    temporada_nombre: Optional[str] = None

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
    imagen_url: Optional[str] = None


class PrendaUpdate(BaseModel):
    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    categoria_id: Optional[int] = None
    coleccion_id: Optional[int] = None
    proveedor_id: Optional[int] = None
    precio_base: Optional[float] = None
    modelo_3d_url: Optional[str] = None
    imagen_url: Optional[str] = None
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
    imagen_url: Optional[str] = None
    estado: bool
    categoria_nombre: Optional[str] = None
    coleccion_nombre: Optional[str] = None
    proveedor_nombre: Optional[str] = None

    class Config:
        from_attributes = True


# --- CU-11: Variantes de prenda ---
class VariantePrendaCreate(BaseModel):
    talla_id: int
    color_id: int
    codigo_barras: Optional[str] = None


class VariantePrendaUpdate(BaseModel):
    talla_id: Optional[int] = None
    color_id: Optional[int] = None
    codigo_barras: Optional[str] = None
    estado: Optional[bool] = None


class VariantePrendaOut(BaseModel):
    id: int
    prenda_id: int
    talla_id: int
    color_id: int
    codigo_barras: str
    estado: bool
    talla_nombre: Optional[str] = None
    color_nombre: Optional[str] = None

    class Config:
        from_attributes = True

