"""agregar imagen_url a variante_prenda para vestidor virtual por color CU-14

Revision ID: a81abebe3f58
Revises: 36fd7e030c0c
Create Date: 2026-09-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a81abebe3f58'
down_revision: Union[str, None] = '36fd7e030c0c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('variante_prenda', sa.Column('imagen_url', sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column('variante_prenda', 'imagen_url')
