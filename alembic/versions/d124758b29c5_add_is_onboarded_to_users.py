"""add_is_onboarded_to_users

Revision ID: d124758b29c5
Revises: a733035b412d
Create Date: 2025-11-18 15:17:18.670227

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd124758b29c5'
down_revision: Union[str, Sequence[str], None] = 'a733035b412d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add is_onboarded column to users table with default False
    # Existing users will be set to False (not onboarded)
    op.add_column('users', sa.Column('is_onboarded', sa.Boolean(), nullable=False, server_default=sa.text('false')))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove is_onboarded column from users table
    op.drop_column('users', 'is_onboarded')
