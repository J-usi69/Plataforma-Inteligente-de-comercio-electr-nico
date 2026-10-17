"""SaaS 1/4: tablas de la plataforma (planes, tiendas, suscripciones con su historial) y la
primera tienda

Planes del enunciado: Básico (hasta 2 sucursales, sin reportes con IA) y Profesional (hasta 10
sucursales, con todo). Todo lo que ya existe en la base pasa a ser de la tienda "fashionstore"
(id 1), con el plan Profesional para que no pierda ninguna función.

Revision ID: saas01
Revises: a81abebe3f58
Create Date: 2026-10-15
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "saas01"
down_revision: Union[str, None] = "a81abebe3f58"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _funcion(nombre: str, por_defecto: bool) -> sa.Column:
    return sa.Column(nombre, sa.Boolean(), nullable=False, server_default=sa.true() if por_defecto else sa.false())


def upgrade() -> None:
    op.create_table(
        "plan",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("codigo", sa.String(30), nullable=False, unique=True),
        sa.Column("nombre", sa.String(60), nullable=False),
        sa.Column("descripcion", sa.String(200)),
        sa.Column("precio_mensual", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("moneda", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("max_sucursales", sa.Integer()),
        sa.Column("max_prendas", sa.Integer()),
        sa.Column("max_personal", sa.Integer()),
        _funcion("operacion_offline", True),
        _funcion("reportes", True),
        _funcion("reportes_ia", False),
        _funcion("asistente_ia", True),
        _funcion("vestidor_ar", True),
        _funcion("pago_qr", True),
        sa.Column("orden", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estado", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_table(
        "tienda",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(40), nullable=False, unique=True),
        sa.Column("nombre", sa.String(80), nullable=False),
        sa.Column("estado", sa.String(20), nullable=False, server_default="activa"),
        sa.Column("logo_url", sa.String(500)),
        sa.Column("color_primario", sa.String(7), nullable=False, server_default="#4f46e5"),
        sa.Column("color_acento", sa.String(7), nullable=False, server_default="#ec4899"),
        sa.Column("correo_contacto", sa.String(120)),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "suscripcion",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tienda_id", sa.Integer(), sa.ForeignKey("tienda.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("plan_id", sa.Integer(), sa.ForeignKey("plan.id"), nullable=False),
        sa.Column("estado", sa.String(20), nullable=False, server_default="activa"),
        sa.Column("fecha_inicio", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("fecha_vencimiento", sa.DateTime(timezone=True)),
        sa.Column("stripe_customer_id", sa.String(100)),
        sa.Column("stripe_subscription_id", sa.String(100)),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "movimiento_suscripcion",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tienda_id", sa.Integer(), sa.ForeignKey("tienda.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("fecha", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("tipo", sa.String(20), nullable=False),
        sa.Column("plan_id", sa.Integer(), sa.ForeignKey("plan.id"), nullable=False),
        sa.Column("monto", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("origen", sa.String(20), nullable=False),
        sa.Column("detalle", sa.String(255)),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuario.id", ondelete="SET NULL")),
    )

    # Planes del enunciado (precio y límites se ajustan desde la plataforma: PUT /plataforma/planes)
    op.execute("""
        INSERT INTO plan (codigo, nombre, descripcion, precio_mensual, max_sucursales,
                          operacion_offline, reportes, reportes_ia, asistente_ia, vestidor_ar, pago_qr, orden) VALUES
        ('basico', 'Básico', 'Hasta 2 sucursales con productos, ventas, reservas, operación offline y reportes',
         20, 2, true, true, false, true, true, true, 1),
        ('profesional', 'Profesional', 'Hasta 10 sucursales y además reportes generados con IA',
         50, 10, true, true, true, true, true, true, 2)
    """)
    op.execute("""
        INSERT INTO tienda (id, slug, nombre, estado, color_primario, color_acento, correo_contacto)
        VALUES (1, 'fashionstore', 'FashionStore', 'activa', '#4f46e5', '#ec4899', 'admin@fashionstore.com')
    """)
    op.execute("SELECT setval('tienda_id_seq', (SELECT MAX(id) FROM tienda))")
    op.execute("""
        INSERT INTO suscripcion (tienda_id, plan_id, estado, fecha_inicio, fecha_vencimiento)
        SELECT 1, id, 'activa', now(), now() + interval '1 year' FROM plan WHERE codigo = 'profesional'
    """)
    op.execute("""
        INSERT INTO movimiento_suscripcion (tienda_id, tipo, plan_id, monto, origen, detalle)
        SELECT 1, 'alta', id, 0, 'plataforma', 'Tienda original incorporada al SaaS' FROM plan WHERE codigo = 'profesional'
    """)


def downgrade() -> None:
    op.drop_table("movimiento_suscripcion")
    op.drop_table("suscripcion")
    op.drop_table("tienda")
    op.drop_table("plan")
