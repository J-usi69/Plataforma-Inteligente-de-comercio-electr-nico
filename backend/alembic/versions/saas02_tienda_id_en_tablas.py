"""SaaS 2/4: tienda_id en cada tabla de negocio y unicidades por tienda

Patrón expand/contract: la columna entra con DEFAULT 1 (en Postgres 11+ agregar una columna con
un valor por defecto constante es instantáneo, no reescribe la tabla). Así todas las filas
actuales quedan en la tienda 1 y el código que todavía no conoce la columna sigue insertando sin
romperse. Cuando el código nuevo ya esté desplegado, saas04 quita el DEFAULT.

Revision ID: saas02
Revises: saas01
Create Date: 2026-10-15
"""
from typing import Sequence, Union

from alembic import op

revision: str = "saas02"
down_revision: Union[str, None] = "saas01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# tienda_id obligatorio
TABLAS_DE_TIENDA = [
    "categoria", "talla", "color", "temporada", "coleccion", "proveedor", "prenda",
    "variante_prenda", "disponibilidad_proveedor", "interaccion_ia", "inventario_sucursal",
    "movimiento_inventario", "reserva", "detalle_reserva", "rol", "rol_permiso", "usuario_rol",
    "push_token", "sucursal", "personal", "venta", "detalle_venta", "pago",
]
# tienda_id vacío = de la plataforma (superadmin)
TABLAS_DE_TIENDA_O_PLATAFORMA = ["usuario", "bitacora"]

# (tabla, restricción global actual, columnas que pasan a ser únicas por tienda)
UNICAS_POR_TIENDA = [
    ("categoria", "categoria_nombre_key", "nombre"),
    ("talla", "talla_nombre_key", "nombre"),
    ("color", "color_nombre_key", "nombre"),
    ("rol", "rol_nombre_key", "nombre"),
    ("variante_prenda", "variante_prenda_codigo_barras_key", "codigo_barras"),
]


def upgrade() -> None:
    for tabla in TABLAS_DE_TIENDA:
        op.execute(f"ALTER TABLE {tabla} ADD COLUMN tienda_id INTEGER NOT NULL DEFAULT 1 REFERENCES tienda(id)")
        op.execute(f"CREATE INDEX ix_{tabla}_tienda_id ON {tabla} (tienda_id)")
    for tabla in TABLAS_DE_TIENDA_O_PLATAFORMA:
        op.execute(f"ALTER TABLE {tabla} ADD COLUMN tienda_id INTEGER DEFAULT 1 REFERENCES tienda(id)")
        op.execute(f"CREATE INDEX ix_{tabla}_tienda_id ON {tabla} (tienda_id)")
    op.execute("ALTER TABLE usuario ADD COLUMN es_superadmin BOOLEAN NOT NULL DEFAULT false")

    for tabla, restriccion, columna in UNICAS_POR_TIENDA:
        op.execute(f"ALTER TABLE {tabla} DROP CONSTRAINT IF EXISTS {restriccion}")
        op.execute(f"ALTER TABLE {tabla} ADD CONSTRAINT {tabla}_tienda_id_{columna}_key UNIQUE (tienda_id, {columna})")

    # El correo: único dentro de cada tienda y entre las cuentas de la plataforma
    op.execute("ALTER TABLE usuario DROP CONSTRAINT IF EXISTS usuario_correo_key")
    op.execute("CREATE UNIQUE INDEX uq_usuario_tienda_correo ON usuario (tienda_id, correo) WHERE tienda_id IS NOT NULL")
    op.execute("CREATE UNIQUE INDEX uq_usuario_plataforma_correo ON usuario (correo) WHERE tienda_id IS NULL")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_usuario_plataforma_correo")
    op.execute("DROP INDEX IF EXISTS uq_usuario_tienda_correo")
    op.execute("ALTER TABLE usuario ADD CONSTRAINT usuario_correo_key UNIQUE (correo)")
    for tabla, restriccion, columna in UNICAS_POR_TIENDA:
        op.execute(f"ALTER TABLE {tabla} DROP CONSTRAINT IF EXISTS {tabla}_tienda_id_{columna}_key")
        op.execute(f"ALTER TABLE {tabla} ADD CONSTRAINT {restriccion} UNIQUE ({columna})")
    op.execute("ALTER TABLE usuario DROP COLUMN es_superadmin")
    for tabla in TABLAS_DE_TIENDA + TABLAS_DE_TIENDA_O_PLATAFORMA:
        op.execute(f"ALTER TABLE {tabla} DROP COLUMN tienda_id")
