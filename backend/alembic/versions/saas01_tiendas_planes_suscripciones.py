"""SaaS 1/4: tablas de la plataforma (planes, tiendas, suscripciones) y la primera tienda

Todo lo que ya existe en la base pasa a ser de la tienda "fashionstore" (id 1), con el plan más
completo para que no pierda ninguna función.

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


def upgrade() -> None:
    op.create_table(
        "plan",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("codigo", sa.String(30), nullable=False, unique=True),
        sa.Column("nombre", sa.String(60), nullable=False),
        sa.Column("precio_mensual", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("moneda", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("max_sucursales", sa.Integer()),
        sa.Column("max_prendas", sa.Integer()),
        sa.Column("max_personal", sa.Integer()),
        sa.Column("ia", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("vestidor_ar", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("pago_qr", sa.Boolean(), nullable=False, server_default=sa.false()),
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
        sa.Column("stripe_customer_id", sa.String(100)),
        sa.Column("stripe_subscription_id", sa.String(100)),
        sa.Column("periodo_fin", sa.DateTime(timezone=True)),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # Planes iniciales (precios y límites se ajustan desde el panel de la plataforma)
    op.execute("""
        INSERT INTO plan (codigo, nombre, precio_mensual, max_sucursales, max_prendas, max_personal, ia, vestidor_ar, pago_qr, orden) VALUES
        ('gratis',  'Gratis',   0,  1,    30,   2,    false, false, false, 1),
        ('pro',     'Pro',      29, 3,    500,  15,   true,  true,  true,  2),
        ('empresa', 'Empresa',  99, NULL, NULL, NULL, true,  true,  true,  3)
    """)
    op.execute("""
        INSERT INTO tienda (id, slug, nombre, estado, color_primario, color_acento, correo_contacto)
        VALUES (1, 'fashionstore', 'FashionStore', 'activa', '#4f46e5', '#ec4899', 'admin@fashionstore.com')
    """)
    op.execute("SELECT setval('tienda_id_seq', (SELECT MAX(id) FROM tienda))")
    op.execute("""
        INSERT INTO suscripcion (tienda_id, plan_id, estado)
        SELECT 1, id, 'activa' FROM plan WHERE codigo = 'empresa'
    """)


def downgrade() -> None:
    op.drop_table("suscripcion")
    op.drop_table("tienda")
    op.drop_table("plan")
