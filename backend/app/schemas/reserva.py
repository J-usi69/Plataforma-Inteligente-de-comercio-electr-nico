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
    prenda_id: Optional[int] = None
    prenda_nombre: Optional[str] = None
    talla_nombre: Optional[str] = None
    color_nombre: Optional[str] = None
    codigo_barras: Optional[str] = None
    precio_unitario: Optional[float] = None
    subtotal: Optional[float] = None

    class Config:
        from_attributes = True


class ReservaOut(BaseModel):
    id: int
    usuario_id: int
    cliente_correo: Optional[str] = None
    cliente_celular: Optional[str] = None
    sucursal_id: int
    sucursal_nombre: Optional[str] = None
    personal_id: Optional[int] = None
    fecha_reserva: datetime
    horario_atencion: Optional[time] = None
    estado: str
    total_estimado: Optional[float] = None
    detalles: List[DetalleReservaOut] = []

    class Config:
        from_attributes = True
