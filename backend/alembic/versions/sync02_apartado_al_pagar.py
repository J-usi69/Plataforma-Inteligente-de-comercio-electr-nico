"""Apartado de prendas mientras se paga con tarjeta o QR (venta.apartado_hasta)

Columna opcional (instantáneo en Postgres, sin reescribir la tabla) y un índice parcial que solo
cubre las ventas con algo apartado. Igual que sync01, va ANTES del deploy: el código nuevo lee la
columna.

Revision ID: sync02
Revises: sync01
Create Date: 2026-10-24
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "sync02"
down_revision: Union[str, None] = "sync01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("venta", sa.Column("apartado_hasta", sa.DateTime(timezone=True)))
    op.create_index(
        "idx_venta_apartado", "venta", ["apartado_hasta"], postgresql_where=sa.text("apartado_hasta IS NOT NULL")
    )


def downgrade() -> None:
    op.drop_index("idx_venta_apartado", table_name="venta")
    op.drop_column("venta", "apartado_hasta")
