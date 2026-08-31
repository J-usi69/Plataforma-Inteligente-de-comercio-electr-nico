from datetime import datetime, time

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import EstadoReserva


class Reserva(Base):
    __tablename__ = "reserva"
    __table_args__ = (Index("idx_reserva_usuario", "usuario_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"))
    sucursal_id: Mapped[int] = mapped_column(ForeignKey("sucursal.id"))
    personal_id: Mapped[int | None] = mapped_column(ForeignKey("personal.id"))
    fecha_reserva: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    horario_atencion: Mapped[time | None] = mapped_column(Time)
    estado: Mapped[EstadoReserva] = mapped_column(
        Enum(EstadoReserva, name="estado_reserva", create_type=False), default=EstadoReserva.pendiente
    )

    detalles: Mapped[list["DetalleReserva"]] = relationship(back_populates="reserva")


class DetalleReserva(Base):
    __tablename__ = "detalle_reserva"
    __table_args__ = (
        UniqueConstraint("reserva_id", "variante_id"),
        Index("idx_detalle_reserva_reserva", "reserva_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    reserva_id: Mapped[int] = mapped_column(ForeignKey("reserva.id", ondelete="CASCADE"))
    variante_id: Mapped[int] = mapped_column(ForeignKey("variante_prenda.id"))
    cantidad: Mapped[int] = mapped_column(Integer)

    reserva: Mapped["Reserva"] = relationship(back_populates="detalles")
