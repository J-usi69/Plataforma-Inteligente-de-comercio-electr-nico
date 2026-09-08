from datetime import datetime, time
from typing import List, Optional
from pydantic import BaseModel, Field


class DetalleReservaCreate(BaseModel):
    variante_id: int
    cantidad: int = Field(gt=0)


class ReservaCreate(BaseModel):
    sucursal_id: int
    horario_atencion: Optional[time] = None
    detalles: List[DetalleReservaCreate]


class DetalleReservaOut(BaseModel):
    id: int
    variante_id: int
    cantidad: int
    prenda_nombre: Optional[str] = None
    talla_nombre: Optional[str] = None
    color_nombre: Optional[str] = None
    codigo_barras: Optional[str] = None

    class Config:
        from_attributes = True


class ReservaOut(BaseModel):
    id: int
    usuario_id: int
    sucursal_id: int
    sucursal_nombre: Optional[str] = None
    personal_id: Optional[int] = None
    fecha_reserva: datetime
    horario_atencion: Optional[time] = None
    estado: str
    detalles: List[DetalleReservaOut] = []

    class Config:
        from_attributes = True
