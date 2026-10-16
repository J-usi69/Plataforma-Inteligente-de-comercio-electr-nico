from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.db.tenancy import PerteneceATienda


class Categoria(PerteneceATienda, Base):
    __tablename__ = "categoria"
    # Único dentro de cada tienda (dos tiendas pueden tener una categoría "Poleras")
    __table_args__ = (UniqueConstraint("tienda_id", "nombre"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100))
    descripcion: Mapped[str | None] = mapped_column(String(255))
    estado: Mapped[bool] = mapped_column(Boolean, default=True)


class Talla(PerteneceATienda, Base):
    __tablename__ = "talla"
    # Único dentro de cada tienda (dos tiendas pueden tener la misma talla "M")
    __table_args__ = (UniqueConstraint("tienda_id", "nombre"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(20))


class Color(PerteneceATienda, Base):
    __tablename__ = "color"
    __table_args__ = (UniqueConstraint("tienda_id", "nombre"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(50))
    hex: Mapped[str | None] = mapped_column(String(7))


class Temporada(PerteneceATienda, Base):
    __tablename__ = "temporada"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100))
    tipo: Mapped[str | None] = mapped_column(String(50))
    fecha_inicio: Mapped[date | None] = mapped_column(Date)
    fecha_fin: Mapped[date | None] = mapped_column(Date)
    estado: Mapped[bool] = mapped_column(Boolean, default=True)


class Coleccion(PerteneceATienda, Base):
    __tablename__ = "coleccion"
    __table_args__ = (Index("idx_coleccion_temporada", "temporada_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(150))
    descripcion: Mapped[str | None] = mapped_column(String(255))
    temporada_id: Mapped[int] = mapped_column(ForeignKey("temporada.id"))
    estado: Mapped[bool] = mapped_column(Boolean, default=True)


class Proveedor(PerteneceATienda, Base):
    __tablename__ = "proveedor"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id", ondelete="SET NULL"), unique=True)
    nombre_empresa: Mapped[str] = mapped_column(String(150))
    contacto: Mapped[str | None] = mapped_column(String(150))
    estado: Mapped[bool] = mapped_column(Boolean, default=True)

    usuario: Mapped["Usuario | None"] = relationship(back_populates="proveedor")


class Prenda(PerteneceATienda, Base):
    __tablename__ = "prenda"
    __table_args__ = (
        Index("idx_prenda_categoria", "categoria_id"),
        Index("idx_prenda_coleccion", "coleccion_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(150))
    descripcion: Mapped[str | None] = mapped_column(Text)
    categoria_id: Mapped[int] = mapped_column(ForeignKey("categoria.id"))
    coleccion_id: Mapped[int | None] = mapped_column(ForeignKey("coleccion.id"))
    proveedor_id: Mapped[int | None] = mapped_column(ForeignKey("proveedor.id"))
    precio_base: Mapped[float] = mapped_column(Numeric(10, 2))
    modelo_3d_url: Mapped[str | None] = mapped_column(String(500))
    imagen_url: Mapped[str | None] = mapped_column(String(500))
    estado: Mapped[bool] = mapped_column(Boolean, default=True)

    variantes: Mapped[list["VariantePrenda"]] = relationship(back_populates="prenda")


class VariantePrenda(PerteneceATienda, Base):
    __tablename__ = "variante_prenda"
    __table_args__ = (
        UniqueConstraint("prenda_id", "talla_id", "color_id"),
        UniqueConstraint("tienda_id", "codigo_barras"),
        Index("idx_variante_prenda", "prenda_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    prenda_id: Mapped[int] = mapped_column(ForeignKey("prenda.id", ondelete="CASCADE"))
    talla_id: Mapped[int] = mapped_column(ForeignKey("talla.id"))
    color_id: Mapped[int] = mapped_column(ForeignKey("color.id"))
    codigo_barras: Mapped[str] = mapped_column(String(50))
    estado: Mapped[bool] = mapped_column(Boolean, default=True)
    # Foto de referencia de ESTE color específico para el vestidor virtual (CU-14).
    # Si es NULL, se usa la foto genérica de Prenda.imagen_url como respaldo.
    imagen_url: Mapped[str | None] = mapped_column(String(500))

    prenda: Mapped["Prenda"] = relationship(back_populates="variantes")


class DisponibilidadProveedor(PerteneceATienda, Base):
    __tablename__ = "disponibilidad_proveedor"
    __table_args__ = (Index("idx_disponibilidad_prenda", "prenda_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    prenda_id: Mapped[int] = mapped_column(ForeignKey("prenda.id", ondelete="CASCADE"))
    proveedor_id: Mapped[int] = mapped_column(ForeignKey("proveedor.id", ondelete="CASCADE"))
    cantidad: Mapped[int] = mapped_column(Integer)
    fecha_estimada: Mapped[date] = mapped_column(Date)
    fecha_registro: Mapped[datetime] = mapped_column(DateTime(timezone=True))
