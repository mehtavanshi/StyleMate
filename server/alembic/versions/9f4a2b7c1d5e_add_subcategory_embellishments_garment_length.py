"""add subcategory, embellishments, garment_length to clothing_items

Revision ID: 9f4a2b7c1d5e
Revises: 8d6386aec3e2
Create Date: 2026-07-25 12:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9f4a2b7c1d5e'
down_revision: Union[str, Sequence[str], None] = '8d6386aec3e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('clothing_items', sa.Column('subcategory', sa.String(), nullable=True))
    op.add_column('clothing_items', sa.Column('embellishments', sa.Text(), nullable=True))
    op.add_column('clothing_items', sa.Column('garment_length', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('clothing_items', 'garment_length')
    op.drop_column('clothing_items', 'embellishments')
    op.drop_column('clothing_items', 'subcategory')
