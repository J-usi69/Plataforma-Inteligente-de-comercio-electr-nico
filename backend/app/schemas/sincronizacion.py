"""Contrato de la operación sin conexión, el mismo para la PWA (IndexedDB) y la app móvil
(SQLite): el paquete que se descarga para trabajar sin Internet y el lote de operaciones que se
sube al volver la conexión."""
from datetime import datetime, time
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field

EstadoOperacion = Literal["confirmada", "rechazada", "conflicto", "error"]


# ------------------------------------------------------------------------------
# Lo que sube el dispositivo
# ------------------------------------------------------------------------------
class OperacionIn(BaseModel):
    """Sobre de cada operación. "datos" se valida según el tipo recién al procesarla: una
    operación mal armada queda rechazada sola, sin frenar al resto del lote."""

    id: UUID  # generado en el dispositivo al registrarla; no cambia en los reintentos
    tipo: str = Field(max_length=20)  # venta, reserva, cambio
    tienda: str = Field(max_length=40)  # slug de la empresa en la que se registró
    sucursal_id: int
    registrada_en: datetime  # hora del dispositivo al registrarla
    dispositivo: Optional[str] = Field(None, max_length=80)  # p. ej. "pwa:chrome" o "movil:android"
    datos: dict


class LoteIn(BaseModel):
    operaciones: list[OperacionIn] = Field(min_length=1, max_length=100)


class LineaIn(BaseModel):
    variante_id: int
    cantidad: int = Field(gt=0, le=1000)


class LineaConPrecioIn(LineaIn):
    precio_unitario: float = Field(ge=0)  # el precio que se usó en la tienda


class VentaOfflineIn(BaseModel):
    """Venta de contado: el efectivo ya se recibió en la tienda."""

    cliente_id: Optional[int] = None  # vacío: cliente ocasional
    detalles: list[LineaConPrecioIn] = Field(min_length=1, max_length=50)
    total: float = Field(ge=0)
    metodo_pago: Literal["efectivo"] = "efectivo"
    monto_recibido: Optional[float] = Field(None, ge=0)


class ReservaOfflineIn(BaseModel):
    cliente_id: Optional[int] = None  # obligatorio si la registra el personal; un cliente reserva para sí
    detalles: list[LineaIn] = Field(min_length=1, max_length=50)
    horario_atencion: Optional[time] = None


class CambioOfflineIn(BaseModel):
    """Cambio de prendas de una venta pagada dentro del plazo de la tienda."""

    venta_id: Optional[int] = None  # venta ya sincronizada...
    venta_operacion_id: Optional[UUID] = None  # ...o venta registrada sin conexión (id de su operación)
    devuelve: list[LineaIn] = Field(min_length=1, max_length=50)
    entrega: list[LineaConPrecioIn] = Field(min_length=1, max_length=50)
    diferencia: float  # lo que paga el cliente: valor entregado - valor devuelto
    motivo: Optional[str] = Field(None, max_length=200)
    metodo_pago: Literal["efectivo"] = "efectivo"


# ------------------------------------------------------------------------------
# Lo que responde el servidor
# ------------------------------------------------------------------------------
class ResultadoOperacionOut(BaseModel):
    id: UUID
    tipo: str
    # confirmada | rechazada | conflicto (espera la decisión de un encargado) | error (no se
    # pudo procesar ahora: el dispositivo la conserva y la reintenta)
    estado: EstadoOperacion
    codigo: Optional[str] = None
    mensaje: Optional[str] = None
    referencia_tipo: Optional[str] = None  # venta, reserva, cambio
    referencia_id: Optional[int] = None
    duplicada: bool = False  # ya había llegado antes: se devuelve el resultado guardado
    procesada_en: Optional[datetime] = None


class LoteOut(BaseModel):
    recibido_en: datetime
    resultados: list[ResultadoOperacionOut]


class EstadoOperacionesOut(BaseModel):
    resultados: list[ResultadoOperacionOut]
    desconocidas: list[UUID]  # el servidor no las recibió: hay que volver a enviarlas


class OperacionAdminOut(ResultadoOperacionOut):
    """Para el panel de sincronización del encargado o del administrador."""

    sucursal_id: Optional[int] = None
    sucursal_nombre: Optional[str] = None
    usuario_correo: Optional[str] = None
    dispositivo: Optional[str] = None
    registrada_en: datetime
    recibida_en: datetime
    intentos: int
    datos: dict
    resuelta_por_correo: Optional[str] = None
    resuelta_en: Optional[datetime] = None
    nota_resolucion: Optional[str] = None


class ResolverConflictoIn(BaseModel):
    accion: Literal["aceptar", "rechazar"]
    nota: Optional[str] = Field(None, max_length=300)


# ------------------------------------------------------------------------------
# Paquete para trabajar sin conexión (tablas normalizadas, como quedan en IndexedDB / SQLite)
# ------------------------------------------------------------------------------
class SucursalPaqueteOut(BaseModel):
    id: int
    nombre: str
    direccion: str
    ciudad: Optional[str] = None


class ItemNombreOut(BaseModel):
    id: int
    nombre: str


class ColorPaqueteOut(ItemNombreOut):
    hex: Optional[str] = None


class PrendaPaqueteOut(BaseModel):
    id: int
    nombre: str
    descripcion: Optional[str] = None
    categoria_id: int
    precio_base: float
    imagen_url: Optional[str] = None


class VariantePaqueteOut(BaseModel):
    id: int
    prenda_id: int
    talla_id: int
    color_id: int
    codigo_barras: str
    imagen_url: Optional[str] = None


class InventarioPaqueteOut(BaseModel):
    variante_id: int
    sucursal_id: int
    stock_disponible: int


class ClientePaqueteOut(BaseModel):
    id: int
    correo: str


class DetalleVentaPaqueteOut(BaseModel):
    variante_id: int
    cantidad: int
    precio_unitario: float
    devuelto: int  # ya devuelto en cambios anteriores


class VentaPaqueteOut(BaseModel):
    """Venta pagada que todavía está dentro del plazo de cambio."""

    id: int
    sucursal_id: int
    cliente_id: Optional[int] = None
    fecha_venta: datetime
    total: float
    detalles: list[DetalleVentaPaqueteOut]


class PaqueteOut(BaseModel):
    generado_en: datetime
    # Pasado este tiempo la app avisa que precios y existencias pueden estar desactualizados
    vigencia_horas: int
    tienda: str
    dias_para_cambio: int
    sucursales: list[SucursalPaqueteOut]
    categorias: list[ItemNombreOut]
    tallas: list[ItemNombreOut]
    colores: list[ColorPaqueteOut]
    prendas: list[PrendaPaqueteOut]
    variantes: list[VariantePaqueteOut]
    inventario: list[InventarioPaqueteOut]
    # Solo para el personal: clientes (datos mínimos) y ventas que se pueden cambiar
    clientes: list[ClientePaqueteOut]
    ventas: list[VentaPaqueteOut]
