"""SaaS: cada tienda (tenant) con su marca, su plan y su suscripción. Estas tablas son de la
plataforma (no llevan el mixin de tienda); los datos de negocio de cada tienda sí lo llevan, ver
app/db/tenancy.py."""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.db.tenancy import estado_de_suscripcion


class Plan(Base):
    """Planes del SaaS (Básico y Profesional). Límites, precio y funciones se configuran desde
    el backend: el superadmin los edita en /plataforma/planes."""

    __tablename__ = "plan"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(30), unique=True)  # basico, profesional
    nombre: Mapped[str] = mapped_column(String(60))
    descripcion: Mapped[str | None] = mapped_column(String(200))
    precio_mensual: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    moneda: Mapped[str] = mapped_column(String(3), default="USD")
    # Límites: None = sin límite
    max_sucursales: Mapped[int | None] = mapped_column(Integer)
    max_prendas: Mapped[int | None] = mapped_column(Integer)
    max_personal: Mapped[int | None] = mapped_column(Integer)
    # Funciones incluidas (productos, ventas y reservas están en todos los planes)
    operacion_offline: Mapped[bool] = mapped_column(Boolean, default=True)
    reportes: Mapped[bool] = mapped_column(Boolean, default=True)
    reportes_ia: Mapped[bool] = mapped_column(Boolean, default=False)
    asistente_ia: Mapped[bool] = mapped_column(Boolean, default=True)
    vestidor_ar: Mapped[bool] = mapped_column(Boolean, default=True)
    pago_qr: Mapped[bool] = mapped_column(Boolean, default=True)
    orden: Mapped[int] = mapped_column(Integer, default=0)
    estado: Mapped[bool] = mapped_column(Boolean, default=True)


class Tienda(Base):
    __tablename__ = "tienda"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Identifica a la tienda en la URL: /t/<slug> (y más adelante <slug>.dominio.com)
    slug: Mapped[str] = mapped_column(String(40), unique=True)
    nombre: Mapped[str] = mapped_column(String(80))
    estado: Mapped[str] = mapped_column(String(20), default="activa")  # activa, suspendida
    # Marca: la web y la app toman de acá su logo y colores
    logo_url: Mapped[str | None] = mapped_column(String(500))
    color_primario: Mapped[str] = mapped_column(String(7), default="#4f46e5")
    color_acento: Mapped[str] = mapped_column(String(7), default="#ec4899")
    correo_contacto: Mapped[str | None] = mapped_column(String(120))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    suscripcion: Mapped["Suscripcion | None"] = relationship(back_populates="tienda", uselist=False)


class Suscripcion(Base):
    __tablename__ = "suscripcion"

    id: Mapped[int] = mapped_column(primary_key=True)
    tienda_id: Mapped[int] = mapped_column(ForeignKey("tienda.id", ondelete="CASCADE"), unique=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plan.id"))
    # activa, vencida, cancelada (una activa con la fecha de vencimiento pasada cuenta como vencida)
    estado: Mapped[str] = mapped_column(String(20), default="activa")
    fecha_inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fecha_vencimiento: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # None = no vence
    # Solo si el cobro es con Stripe (COBRO_SUSCRIPCIONES=stripe); con el cobro simulado quedan vacíos
    stripe_customer_id: Mapped[str | None] = mapped_column(String(100))
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(100))
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    tienda: Mapped[Tienda] = relationship(back_populates="suscripcion")
    plan: Mapped[Plan] = relationship()

    @property
    def estado_actual(self) -> str:
        return estado_de_suscripcion(self.estado, self.fecha_vencimiento)


class MovimientoSuscripcion(Base):
    """Historial de la suscripción de una tienda: alta, cambios de plan, renovaciones (pagos
    simulados o de Stripe) y cambios de estado hechos por la plataforma."""

    __tablename__ = "movimiento_suscripcion"

    id: Mapped[int] = mapped_column(primary_key=True)
    tienda_id: Mapped[int] = mapped_column(ForeignKey("tienda.id", ondelete="CASCADE"), index=True)
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # alta, cambio_plan, renovacion, suspension, reactivacion, cancelacion, ajuste
    tipo: Mapped[str] = mapped_column(String(20))
    plan_id: Mapped[int] = mapped_column(ForeignKey("plan.id"))
    monto: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    origen: Mapped[str] = mapped_column(String(20))  # simulado, stripe, plataforma
    detalle: Mapped[str | None] = mapped_column(String(255))
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id", ondelete="SET NULL"))

    plan: Mapped[Plan] = relationship()
