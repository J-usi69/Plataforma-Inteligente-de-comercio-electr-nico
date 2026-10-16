from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.db.tenancy import PerteneceATienda, PerteneceATiendaOPlataforma


class Rol(PerteneceATienda, Base):
    """Cada tienda tiene sus roles y su matriz de permisos (los códigos de permiso son globales)."""

    __tablename__ = "rol"
    __table_args__ = (UniqueConstraint("tienda_id", "nombre"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(30))
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


class RolPermiso(PerteneceATienda, Base):
    __tablename__ = "rol_permiso"

    rol_id: Mapped[int] = mapped_column(ForeignKey("rol.id", ondelete="CASCADE"), primary_key=True)
    permiso_id: Mapped[int] = mapped_column(ForeignKey("permiso.id", ondelete="CASCADE"), primary_key=True)


class Usuario(PerteneceATiendaOPlataforma, Base):
    __tablename__ = "usuario"
    # El correo es único dentro de cada tienda (la misma persona puede ser cliente de varias) y
    # entre las cuentas de la plataforma
    __table_args__ = (
        Index("uq_usuario_tienda_correo", "tienda_id", "correo", unique=True, postgresql_where=text("tienda_id IS NOT NULL")),
        Index("uq_usuario_plataforma_correo", "correo", unique=True, postgresql_where=text("tienda_id IS NULL")),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    correo: Mapped[str] = mapped_column(String(150))
    password_hash: Mapped[str] = mapped_column(String(255))
    celular: Mapped[str | None] = mapped_column(String(15))
    estado: Mapped[bool] = mapped_column(Boolean, default=True)
    verificado: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fecha_eliminacion: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # Administra la plataforma (alta de tiendas, planes); solo cuentas sin tienda
    es_superadmin: Mapped[bool] = mapped_column(Boolean, default=False)

    personal: Mapped["Personal | None"] = relationship(back_populates="usuario", uselist=False)
    proveedor: Mapped["Proveedor | None"] = relationship(back_populates="usuario", uselist=False)


class UsuarioRol(PerteneceATienda, Base):
    __tablename__ = "usuario_rol"

    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id", ondelete="CASCADE"), primary_key=True)
    rol_id: Mapped[int] = mapped_column(ForeignKey("rol.id", ondelete="CASCADE"), primary_key=True)


class Bitacora(PerteneceATiendaOPlataforma, Base):
    __tablename__ = "bitacora"
    __table_args__ = (Index("idx_bitacora_usuario", "usuario_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"))
    accion: Mapped[str] = mapped_column(String(100))
    ip: Mapped[str | None] = mapped_column(String(45))
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PushToken(PerteneceATienda, Base):
    """Token de FCM de un dispositivo de la app móvil, para notificaciones push."""
    __tablename__ = "push_token"
    __table_args__ = (Index("idx_push_token_usuario", "usuario_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id", ondelete="CASCADE"))
    token: Mapped[str] = mapped_column(String(255), unique=True)
    plataforma: Mapped[str] = mapped_column(String(20), default="android")
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
