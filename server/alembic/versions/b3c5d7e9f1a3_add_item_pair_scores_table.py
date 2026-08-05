"""add item_pair_scores table (pair-score cache)

The table was only ever created by Base.metadata.create_all, which runs for
SQLite only — Postgres deployments were missing it entirely and every capsule
or outfit request blew up on the first ensure_pair_scores() call.

Revision ID: b3c5d7e9f1a3
Revises: a2b4c6d8e0f2
Create Date: 2026-08-04 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3c5d7e9f1a3'
down_revision: Union[str, Sequence[str], None] = 'a2b4c6d8e0f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('item_pair_scores',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('item_a_id', sa.Integer(), nullable=False),
        sa.Column('item_b_id', sa.Integer(), nullable=False),
        sa.Column('score', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['item_a_id'], ['clothing_items.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['item_b_id'], ['clothing_items.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('item_a_id', 'item_b_id', name='uq_item_pair'),
    )
    op.create_index(op.f('ix_item_pair_scores_id'), 'item_pair_scores', ['id'], unique=False)
    op.create_index(op.f('ix_item_pair_scores_user_id'), 'item_pair_scores', ['user_id'], unique=False)
    op.create_index(op.f('ix_item_pair_scores_item_a_id'), 'item_pair_scores', ['item_a_id'], unique=False)
    op.create_index(op.f('ix_item_pair_scores_item_b_id'), 'item_pair_scores', ['item_b_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_item_pair_scores_item_b_id'), table_name='item_pair_scores')
    op.drop_index(op.f('ix_item_pair_scores_item_a_id'), table_name='item_pair_scores')
    op.drop_index(op.f('ix_item_pair_scores_user_id'), table_name='item_pair_scores')
    op.drop_index(op.f('ix_item_pair_scores_id'), table_name='item_pair_scores')
    op.drop_table('item_pair_scores')
