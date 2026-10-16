"""SaaS 4/4 (contract): tienda_id sin valor por defecto

Se aplica DESPUÉS de desplegar el código multi-tienda (que siempre asigna tienda_id). Desde acá,
una fila que llegue sin tienda falla en vez de caer en silencio en la tienda 1.

    alembic upgrade saas03   # antes del deploy
    (deploy del código nuevo)
    alembic upgrade head     # esta migración

Revision ID: saas04
Revises: saas03
Create Date: 2026-10-15
"""
from typing import Sequence, Union

from alembic import op

revision: str = "saas04"
down_revision: Union[str, None] = "saas03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLAS = [
    "categoria", "talla", "color", "temporada", "coleccion", "proveedor", "prenda",
    "variante_prenda", "disponibilidad_proveedor", "interaccion_ia", "inventario_sucursal",
    "movimiento_inventario", "reserva", "detalle_reserva", "rol", "rol_permiso", "usuario_rol",
    "push_token", "sucursal", "personal", "venta", "detalle_venta", "pago", "usuario", "bitacora",
]


def upgrade() -> None:
    for tabla in TABLAS:
        op.execute(f"ALTER TABLE {tabla} ALTER COLUMN tienda_id DROP DEFAULT")


def downgrade() -> None:
    for tabla in TABLAS:
        op.execute(f"ALTER TABLE {tabla} ALTER COLUMN tienda_id SET DEFAULT 1")
