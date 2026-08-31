from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Categoria(Base):
    __tablename__ = "categoria"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100), unique=True)
    descripcion: Mapped[str | None] = mapped_column(String(255))
    estado: Mapped[bool] = mapped_column(Boolean, default=True)


class Talla(Base):
    __tablename__ = "talla"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(20), unique=True)


class Color(Base):
    __tablename__ = "color"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(50), unique=True)
    hex: Mapped[str | None] = mapped_column(String(7))


class Temporada(Base):
    __tablename__ = "temporada"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100))
    tipo: Mapped[str | None] = mapped_column(String(50))
    fecha_inicio: Mapped[date | None] = mapped_column(Date)
    fecha_fin: Mapped[date | None] = mapped_column(Date)
    estado: Mapped[bool] = mapped_column(Boolean, default=True)


class Coleccion(Base):
    __tablename__ = "coleccion"
    __table_args__ = (Index("idx_coleccion_temporada", "temporada_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(150))
    descripcion: Mapped[str | None] = mapped_column(String(255))
    temporada_id: Mapped[int] = mapped_column(ForeignKey("temporada.id"))
    estado: Mapped[bool] = mapped_column(Boolean, default=True)


class Proveedor(Base):
    __tablename__ = "proveedor"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre_empresa: Mapped[str] = mapped_column(String(150))
    contacto: Mapped[str | None] = mapped_column(String(150))
    estado: Mapped[bool] = mapped_column(Boolean, default=True)


class Prenda(Base):
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
    estado: Mapped[bool] = mapped_column(Boolean, default=True)

    variantes: Mapped[list["VariantePrenda"]] = relationship(back_populates="prenda")


class VariantePrenda(Base):
    __tablename__ = "variante_prenda"
    __table_args__ = (
        UniqueConstraint("prenda_id", "talla_id", "color_id"),
        Index("idx_variante_prenda", "prenda_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    prenda_id: Mapped[int] = mapped_column(ForeignKey("prenda.id", ondelete="CASCADE"))
    talla_id: Mapped[int] = mapped_column(ForeignKey("talla.id"))
    color_id: Mapped[int] = mapped_column(ForeignKey("color.id"))
    codigo_barras: Mapped[str] = mapped_column(String(50), unique=True)
    estado: Mapped[bool] = mapped_column(Boolean, default=True)

    prenda: Mapped["Prenda"] = relationship(back_populates="variantes")
