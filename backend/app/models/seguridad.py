from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Rol(Base):
    __tablename__ = "rol"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(30), unique=True)
    descripcion: Mapped[str | None] = mapped_column(String(100))
    estado: Mapped[bool] = mapped_column(Boolean, default=True)
    fecha_eliminacion: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Permiso(Base):
    __tablename__ = "permiso"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(50), unique=True)
    descripcion: Mapped[str | None] = mapped_column(String(100))
    modulo: Mapped[str | None] = mapped_column(String(50))
    estado: Mapped[bool] = mapped_column(Boolean, default=True)


class RolPermiso(Base):
    __tablename__ = "rol_permiso"

    rol_id: Mapped[int] = mapped_column(ForeignKey("rol.id", ondelete="CASCADE"), primary_key=True)
    permiso_id: Mapped[int] = mapped_column(ForeignKey("permiso.id", ondelete="CASCADE"), primary_key=True)


class Usuario(Base):
    __tablename__ = "usuario"

    id: Mapped[int] = mapped_column(primary_key=True)
    correo: Mapped[str] = mapped_column(String(150), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    celular: Mapped[str | None] = mapped_column(String(15))
    estado: Mapped[bool] = mapped_column(Boolean, default=True)
    verificado: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fecha_eliminacion: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    personal: Mapped["Personal | None"] = relationship(back_populates="usuario", uselist=False)


class UsuarioRol(Base):
    __tablename__ = "usuario_rol"

    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id", ondelete="CASCADE"), primary_key=True)
    rol_id: Mapped[int] = mapped_column(ForeignKey("rol.id", ondelete="CASCADE"), primary_key=True)


class Bitacora(Base):
    __tablename__ = "bitacora"
    __table_args__ = (Index("idx_bitacora_usuario", "usuario_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"))
    accion: Mapped[str] = mapped_column(String(100))
    ip: Mapped[str | None] = mapped_column(String(45))
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True))
