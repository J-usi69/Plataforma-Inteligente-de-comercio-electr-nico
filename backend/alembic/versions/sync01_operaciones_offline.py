"""Operación sin conexión: registro de las operaciones sincronizadas, cambios de prendas y el
plazo de cambio de cada tienda

Solo agrega (tablas nuevas y una columna con valor por defecto), así que el código anterior sigue
funcionando con la base migrada. Se aplica ANTES del deploy: el código nuevo lee
tienda.dias_para_cambio en cada pedido y sin la columna fallaría.

    alembic upgrade head   # primero
    (deploy del código nuevo)

Revision ID: sync01
Revises: saas04
Create Date: 2026-10-24
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "sync01"
down_revision: Union[str, None] = "saas04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ROL = "fashionstore_app"  # ver saas03
TABLAS = ["operacion_sync", "cambio_prenda", "detalle_cambio"]


def _tienda() -> sa.Column:
    return sa.Column("tienda_id", sa.Integer(), sa.ForeignKey("tienda.id"), nullable=False, index=True)


def upgrade() -> None:
    op.add_column("tienda", sa.Column("dias_para_cambio", sa.Integer(), nullable=False, server_default="7"))

    op.create_table(
        "operacion_sync",
        sa.Column("id", sa.Integer(), primary_key=True),
        _tienda(),
        sa.Column("uuid", sa.Uuid(), nullable=False),
        sa.Column("tipo", sa.String(20), nullable=False),
        sa.Column("sucursal_id", sa.Integer(), sa.ForeignKey("sucursal.id")),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuario.id", ondelete="SET NULL")),
        sa.Column("dispositivo", sa.String(80)),
        sa.Column("registrada_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recibida_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ultimo_intento", sa.DateTime(timezone=True), nullable=False),
        sa.Column("intentos", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("estado", sa.String(20), nullable=False),
        sa.Column("codigo", sa.String(40)),
        sa.Column("mensaje", sa.String(500)),
        sa.Column("huella", sa.String(64), nullable=False),
        sa.Column("datos", postgresql.JSONB(), nullable=False),
        sa.Column("referencia_tipo", sa.String(20)),
        sa.Column("referencia_id", sa.Integer()),
        sa.Column("resuelta_por", sa.Integer(), sa.ForeignKey("usuario.id", ondelete="SET NULL")),
        sa.Column("resuelta_en", sa.DateTime(timezone=True)),
        sa.Column("nota_resolucion", sa.String(300)),
        sa.UniqueConstraint("tienda_id", "uuid"),
    )
    op.create_index("idx_operacion_sync_estado", "operacion_sync", ["tienda_id", "estado"])

    op.create_table(
        "cambio_prenda",
        sa.Column("id", sa.Integer(), primary_key=True),
        _tienda(),
        sa.Column("venta_id", sa.Integer(), sa.ForeignKey("venta.id"), nullable=False),
        sa.Column("sucursal_id", sa.Integer(), sa.ForeignKey("sucursal.id"), nullable=False),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuario.id", ondelete="SET NULL")),
        sa.Column("fecha", sa.DateTime(timezone=True), nullable=False),
        sa.Column("motivo", sa.String(200)),
        sa.Column("total_devuelto", sa.Numeric(10, 2), nullable=False),
        sa.Column("total_entregado", sa.Numeric(10, 2), nullable=False),
        sa.Column("diferencia", sa.Numeric(10, 2), nullable=False),
        sa.Column("metodo_pago", sa.String(30), nullable=False),
    )
    op.create_index("idx_cambio_prenda_venta", "cambio_prenda", ["venta_id"])

    op.create_table(
        "detalle_cambio",
        sa.Column("id", sa.Integer(), primary_key=True),
        _tienda(),
        sa.Column("cambio_id", sa.Integer(), sa.ForeignKey("cambio_prenda.id", ondelete="CASCADE"), nullable=False),
        sa.Column("variante_id", sa.Integer(), sa.ForeignKey("variante_prenda.id"), nullable=False),
        sa.Column("tipo", sa.String(10), nullable=False),
        sa.Column("cantidad", sa.Integer(), nullable=False),
        sa.Column("precio_unitario", sa.Numeric(10, 2), nullable=False),
    )
    op.create_index("idx_detalle_cambio_cambio", "detalle_cambio", ["cambio_id"])

    # Mismo aislamiento que el resto de las tablas de una tienda (saas03). Los permisos se dan
    # explícitos: los privilegios por defecto solo cubren tablas creadas por el mismo usuario
    for tabla in TABLAS:
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {tabla} TO {ROL}")
        op.execute(f"GRANT USAGE, SELECT ON SEQUENCE {tabla}_id_seq TO {ROL}")
        op.execute(f"ALTER TABLE {tabla} ENABLE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY tienda_aislada ON {tabla} TO {ROL}
            USING (tienda_id = app_tienda_actual()) WITH CHECK (tienda_id = app_tienda_actual())
        """)


def downgrade() -> None:
    for tabla in reversed(TABLAS):
        op.execute(f"DROP POLICY IF EXISTS tienda_aislada ON {tabla}")
        op.drop_table(tabla)
    op.drop_column("tienda", "dias_para_cambio")
