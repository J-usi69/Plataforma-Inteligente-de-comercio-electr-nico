from typing import List, Optional

from pydantic import BaseModel


class VentaPorSucursalOut(BaseModel):
    sucursal_id: int
    sucursal_nombre: str
    cantidad_ventas: int
    total_ventas: float


class PrendaVendidaOut(BaseModel):
    prenda_id: Optional[int] = None
    prenda_nombre: str
    cantidad_vendida: int
    total_vendido: float


class QuiebreStockOut(BaseModel):
    variante_id: int
    prenda_nombre: str
    sucursal_id: int
    sucursal_nombre: str
    stock_disponible: int
    stock_minimo: int


class InventarioGlobalItemOut(BaseModel):
    variante_id: int
    prenda_nombre: str
    categoria_id: Optional[int] = None
    categoria_nombre: Optional[str] = None
    talla_nombre: Optional[str] = None
    color_nombre: Optional[str] = None
    sucursal_id: int
    sucursal_nombre: str
    ciudad_id: int
    ciudad_nombre: str
    stock_disponible: int
    stock_minimo: int
    es_quiebre: bool


class DashboardOut(BaseModel):
    cantidad_ventas: int
    total_ventas: float
    ticket_promedio: float
    reservas_pendientes: int
    variantes_bajo_minimo: int
    quiebres: List[QuiebreStockOut]
