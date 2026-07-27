"""add cached_outfits table for anchor-deduplicated outfit cache

Revision ID: a2b4c6d8e0f2
Revises: 9f4a2b7c1d5e
Create Date: 2026-07-27 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a2b4c6d8e0f2'
down_revision: Union[str, Sequence[str], None] = '9f4a2b7c1d5e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('cached_outfits',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('anchor_key', sa.String(), nullable=False),
        sa.Column('items_json', sa.Text(), nullable=False),
        sa.Column('score', sa.Float(), nullable=False),
        sa.Column('reason', sa.String(), nullable=True),
        sa.Column('breakdown_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'anchor_key', name='uq_cached_outfit_user_anchor'),
    )
    op.create_index(op.f('ix_cached_outfits_id'), 'cached_outfits', ['id'], unique=False)
    op.create_index(op.f('ix_cached_outfits_user_id'), 'cached_outfits', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_cached_outfits_user_id'), table_name='cached_outfits')
    op.drop_index(op.f('ix_cached_outfits_id'), table_name='cached_outfits')
    op.drop_table('cached_outfits')
