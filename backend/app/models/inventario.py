from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.enums import TipoMovimiento


class InventarioSucursal(Base):
    __tablename__ = "inventario_sucursal"
    __table_args__ = (
        UniqueConstraint("variante_id", "sucursal_id"),
        Index("idx_inventario_variante_sucursal", "variante_id", "sucursal_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    variante_id: Mapped[int] = mapped_column(ForeignKey("variante_prenda.id", ondelete="CASCADE"))
    sucursal_id: Mapped[int] = mapped_column(ForeignKey("sucursal.id", ondelete="CASCADE"))
    stock_disponible: Mapped[int] = mapped_column(Integer, default=0)
    stock_reservado: Mapped[int] = mapped_column(Integer, default=0)
    stock_minimo: Mapped[int] = mapped_column(Integer, default=0)
    stock_maximo: Mapped[int | None] = mapped_column(Integer)


class MovimientoInventario(Base):
    __tablename__ = "movimiento_inventario"
    __table_args__ = (
        Index("idx_movimiento_variante_sucursal", "variante_id", "sucursal_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    variante_id: Mapped[int] = mapped_column(ForeignKey("variante_prenda.id"))
    sucursal_id: Mapped[int] = mapped_column(ForeignKey("sucursal.id"))
    tipo_movimiento: Mapped[TipoMovimiento] = mapped_column(
        Enum(TipoMovimiento, name="tipo_movimiento", create_type=False)
    )
    cantidad: Mapped[int] = mapped_column(Integer)
    referencia_id: Mapped[int | None] = mapped_column(Integer)
    referencia_tipo: Mapped[str | None] = mapped_column(String(50))
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True))
