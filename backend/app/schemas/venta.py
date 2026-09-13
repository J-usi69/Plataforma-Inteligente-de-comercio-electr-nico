from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


# --- Detalle de Venta ---
class DetalleVentaCreate(BaseModel):
    variante_id: int
    cantidad: int = Field(gt=0)
    precio_unitario: Optional[float] = None  # Si no se envía, se toma del precio_base de la Prenda


class DetalleVentaOut(BaseModel):
    id: int
    variante_id: int
    cantidad: int
    precio_unitario: float
    subtotal: float
    prenda_id: Optional[int] = None
    prenda_nombre: Optional[str] = None
    talla_nombre: Optional[str] = None
    color_nombre: Optional[str] = None
    codigo_barras: Optional[str] = None

    class Config:
        from_attributes = True


# --- Pago ---
class CobroCajaCreate(BaseModel):
    metodo_pago: str = Field(..., description="efectivo, tarjeta, qr")
    monto_recibido: Optional[float] = None


class PagoDigitalCreate(BaseModel):
    metodo_pago: str = Field(default="qr", description="qr, tarjeta, libelula")
    pasarela: Optional[str] = "pasarela_digital"
    numero_tarjeta_simulada: Optional[str] = None


class PagoOut(BaseModel):
    id: int
    venta_id: int
    metodo_pago: str
    pasarela: Optional[str] = None
    estado: str
    monto: float
    transaccion_id: Optional[str] = None
    fecha_pago: datetime

    class Config:
        from_attributes = True


# --- Creación de Venta ---
class VentaPresencialCreate(BaseModel):
    sucursal_id: Optional[int] = None  # Si no viene, se toma de la sucursal del cajero
    reserva_id: Optional[int] = None   # Si proviene de una reserva atendida
    cliente_id: Optional[int] = None   # Opcional si el cliente está registrado en el sistema
    detalles: List[DetalleVentaCreate]


class VentaDigitalCreate(BaseModel):
    sucursal_id: int
    detalles: List[DetalleVentaCreate]


# --- Salida de Venta ---
class VentaOut(BaseModel):
    id: int
    usuario_id: Optional[int] = None
    cliente_nombre: Optional[str] = None
    cliente_correo: Optional[str] = None
    personal_id: Optional[int] = None
    personal_nombre: Optional[str] = None
    sucursal_id: int
    sucursal_nombre: Optional[str] = None
    reserva_id: Optional[int] = None
    tipo_origen: str  # presencial, web, movil
    estado: str       # pendiente, pagada, anulada
    total: float
    fecha_venta: datetime
    detalles: List[DetalleVentaOut] = []
    pagos: List[PagoOut] = []

    class Config:
        from_attributes = True


# --- Comprobante de Venta (CU-23) ---
class ComprobanteItemOut(BaseModel):
    descripcion: str
    talla: Optional[str] = None
    color: Optional[str] = None
    codigo_barras: Optional[str] = None
    cantidad: int
    precio_unitario: float
    subtotal: float


class ComprobanteVentaOut(BaseModel):
    numero_comprobante: str
    venta_id: int
    fecha_emision: datetime
    tipo_origen: str
    sucursal_nombre: str
    sucursal_direccion: str
    sucursal_telefono: Optional[str] = None
    ciudad_nombre: Optional[str] = None
    cajero_nombre: Optional[str] = None
    cliente_nombre: str
    cliente_correo: Optional[str] = None
    metodo_pago: str
    transaccion_id: Optional[str] = None
    estado_venta: str
    subtotal: float
    total: float
    items: List[ComprobanteItemOut] = []

