"""fix_sticker_available_typo

Revision ID: cda4bf19cfe7
Revises: 3e12a25349db
Create Date: 2026-03-07 03:15:12.506716

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cda4bf19cfe7'
down_revision: Union[str, Sequence[str], None] = '3e12a25349db'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('sticker_pool', schema=None) as batch_op:
        batch_op.alter_column('is_avaible', new_column_name='is_available')


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('sticker_pool', schema=None) as batch_op:
        batch_op.alter_column('is_available', new_column_name='is_avaible')
