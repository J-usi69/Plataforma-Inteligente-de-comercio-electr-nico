from datetime import datetime, time

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Ciudad(Base):
    __tablename__ = "ciudad"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100), unique=True)
    estado: Mapped[bool] = mapped_column(Boolean, default=True)
    fecha_eliminacion: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Sucursal(Base):
    __tablename__ = "sucursal"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(150))
    ciudad_id: Mapped[int] = mapped_column(ForeignKey("ciudad.id"))
    direccion: Mapped[str] = mapped_column(String(255))
    telefono: Mapped[str | None] = mapped_column(String(15))
    hora_inicio: Mapped[time | None] = mapped_column(Time)
    hora_fin: Mapped[time | None] = mapped_column(Time)
    estado: Mapped[bool] = mapped_column(Boolean, default=True)
    fecha_eliminacion: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Personal(Base):
    __tablename__ = "personal"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id", ondelete="CASCADE"), unique=True)
    sucursal_id: Mapped[int | None] = mapped_column(ForeignKey("sucursal.id"))
    nombres: Mapped[str] = mapped_column(String(60))
    apellidos: Mapped[str] = mapped_column(String(60))
    cargo: Mapped[str] = mapped_column(String(50))
    estado: Mapped[bool] = mapped_column(Boolean, default=True)
    fecha_eliminacion: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    usuario: Mapped["Usuario"] = relationship(back_populates="personal")
