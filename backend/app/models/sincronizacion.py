"""Operación sin conexión (PWA y app móvil).

Cada venta, reserva o cambio de prenda que se registra sin Internet llega después a
POST /sync/operaciones con un identificador (UUID) generado en el dispositivo. OperacionSync
guarda qué llegó, cuándo, cuántas veces y cómo terminó: es lo que hace idempotente el reenvío
(el mismo id no se aplica dos veces) y lo que permite diagnosticar las que fallaron.

El cambio de prendas (devolver lo comprado y llevarse otra cosa dentro del plazo de la tienda)
no modifica la venta original: queda como un registro propio con lo devuelto y lo entregado.
"""
from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.db.tenancy import PerteneceATienda


class OperacionSync(PerteneceATienda, Base):
    __tablename__ = "operacion_sync"
    __table_args__ = (
        # Único por tienda: el id lo genera el dispositivo, y una tienda no debe poder chocar
        # (ni enterarse de que existe) con el de otra
        UniqueConstraint("tienda_id", "uuid"),
        Index("idx_operacion_sync_estado", "tienda_id", "estado"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[UUID] = mapped_column(Uuid)
    tipo: Mapped[str] = mapped_column(String(20))  # venta, reserva, cambio
    # Vacía si la sucursal enviada no era válida (la enviada queda en datos)
    sucursal_id: Mapped[int | None] = mapped_column(ForeignKey("sucursal.id"))
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id", ondelete="SET NULL"))
    dispositivo: Mapped[str | None] = mapped_column(String(80))
    registrada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # hora del dispositivo
    recibida_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ultimo_intento: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    intentos: Mapped[int] = mapped_column(Integer, default=1)
    # confirmada, rechazada o conflicto (la resuelve un encargado: pasa a confirmada o rechazada)
    estado: Mapped[str] = mapped_column(String(20))
    codigo: Mapped[str | None] = mapped_column(String(40))  # motivo: sin_stock, fuera_de_plazo...
    mensaje: Mapped[str | None] = mapped_column(String(500))
    huella: Mapped[str] = mapped_column(String(64))  # sha256 del contenido: mismo id, otro contenido = error del cliente
    datos: Mapped[dict] = mapped_column(JSONB)  # la operación tal como llegó
    referencia_tipo: Mapped[str | None] = mapped_column(String(20))  # venta, reserva, cambio
    referencia_id: Mapped[int | None] = mapped_column(Integer)
    resuelta_por: Mapped[int | None] = mapped_column(ForeignKey("usuario.id", ondelete="SET NULL"))
    resuelta_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    nota_resolucion: Mapped[str | None] = mapped_column(String(300))


class CambioPrenda(PerteneceATienda, Base):
    __tablename__ = "cambio_prenda"
    __table_args__ = (Index("idx_cambio_prenda_venta", "venta_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    venta_id: Mapped[int] = mapped_column(ForeignKey("venta.id"))
    sucursal_id: Mapped[int] = mapped_column(ForeignKey("sucursal.id"))
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id", ondelete="SET NULL"))
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    motivo: Mapped[str | None] = mapped_column(String(200))
    total_devuelto: Mapped[float] = mapped_column(Numeric(10, 2))
    total_entregado: Mapped[float] = mapped_column(Numeric(10, 2))
    # Lo que pagó el cliente por la diferencia (el cambio es por igual o mayor valor)
    diferencia: Mapped[float] = mapped_column(Numeric(10, 2))
    metodo_pago: Mapped[str] = mapped_column(String(30))

    detalles: Mapped[list["DetalleCambio"]] = relationship(back_populates="cambio")


class DetalleCambio(PerteneceATienda, Base):
    __tablename__ = "detalle_cambio"
    __table_args__ = (Index("idx_detalle_cambio_cambio", "cambio_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    cambio_id: Mapped[int] = mapped_column(ForeignKey("cambio_prenda.id", ondelete="CASCADE"))
    variante_id: Mapped[int] = mapped_column(ForeignKey("variante_prenda.id"))
    tipo: Mapped[str] = mapped_column(String(10))  # devuelve, entrega
    cantidad: Mapped[int] = mapped_column(Integer)
    precio_unitario: Mapped[float] = mapped_column(Numeric(10, 2))

    cambio: Mapped["CambioPrenda"] = relationship(back_populates="detalles")
