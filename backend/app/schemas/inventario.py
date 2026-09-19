from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class DisponibilidadSucursalOut(BaseModel):
    sucursal_id: int
    sucursal_nombre: str
    ciudad_id: int
    ciudad_nombre: str
    direccion: str
    stock_disponible: int


class InventarioVarianteOut(BaseModel):
    variante_id: int
    prenda_nombre: str
    talla_nombre: Optional[str] = None
    color_nombre: Optional[str] = None
    codigo_barras: Optional[str] = None
    stock_disponible: int
    stock_reservado: int


class MovimientoManualCreate(BaseModel):
    variante_id: int
    tipo: str  # "ingreso" | "devolucion" | "merma" | "ajuste"
    cantidad: int


class MovimientoManualOut(BaseModel):
    id: int
    variante_id: int
    tipo: str
    cantidad: int
    stock_disponible: int
    fecha: datetime
