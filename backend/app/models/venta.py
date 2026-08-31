from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import CanalVenta, EstadoPago, EstadoVenta


class Venta(Base):
    __tablename__ = "venta"
    __table_args__ = (
        Index("idx_venta_sucursal", "sucursal_id"),
        Index("idx_venta_usuario", "usuario_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    personal_id: Mapped[int | None] = mapped_column(ForeignKey("personal.id"))
    sucursal_id: Mapped[int] = mapped_column(ForeignKey("sucursal.id"))
    reserva_id: Mapped[int | None] = mapped_column(ForeignKey("reserva.id"))
    tipo_origen: Mapped[CanalVenta] = mapped_column(Enum(CanalVenta, name="canal_venta", create_type=False))
    estado: Mapped[EstadoVenta] = mapped_column(
        Enum(EstadoVenta, name="estado_venta", create_type=False), default=EstadoVenta.pendiente
    )
    total: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    fecha_venta: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    detalles: Mapped[list["DetalleVenta"]] = relationship(back_populates="venta")
    pagos: Mapped[list["Pago"]] = relationship(back_populates="venta")


class DetalleVenta(Base):
    __tablename__ = "detalle_venta"
    __table_args__ = (Index("idx_detalle_venta_venta", "venta_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    venta_id: Mapped[int] = mapped_column(ForeignKey("venta.id", ondelete="CASCADE"))
    variante_id: Mapped[int] = mapped_column(ForeignKey("variante_prenda.id"))
    cantidad: Mapped[int] = mapped_column(Integer)
    precio_unitario: Mapped[float] = mapped_column(Numeric(10, 2))
    subtotal: Mapped[float] = mapped_column(Numeric(10, 2))

    venta: Mapped["Venta"] = relationship(back_populates="detalles")


class Pago(Base):
    __tablename__ = "pago"

    id: Mapped[int] = mapped_column(primary_key=True)
    venta_id: Mapped[int] = mapped_column(ForeignKey("venta.id", ondelete="CASCADE"))
    metodo_pago: Mapped[str] = mapped_column(String(30))
    pasarela: Mapped[str | None] = mapped_column(String(30))
    estado: Mapped[EstadoPago] = mapped_column(
        Enum(EstadoPago, name="estado_pago", create_type=False), default=EstadoPago.pendiente
    )
    monto: Mapped[float] = mapped_column(Numeric(10, 2))
    transaccion_id: Mapped[str | None] = mapped_column(String(100))
    fecha_pago: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    venta: Mapped["Venta"] = relationship(back_populates="pagos")
