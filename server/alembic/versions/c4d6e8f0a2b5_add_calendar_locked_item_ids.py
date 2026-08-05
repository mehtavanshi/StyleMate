"""add calendar_entries.locked_item_ids (full outfit per date)

locked_outfit_id held one garment, so a calendar date could not render the
outfit it stood for and wear analytics counted only the primary item.

Revision ID: c4d6e8f0a2b5
Revises: b3c5d7e9f1a3
Create Date: 2026-08-04 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4d6e8f0a2b5'
down_revision: Union[str, Sequence[str], None] = 'b3c5d7e9f1a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('calendar_entries', sa.Column('locked_item_ids', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('calendar_entries', 'locked_item_ids')
