"""change_status_from_enum_to_varchar

Revision ID: 31d7bac6547d
Revises: 96a2f1b4ade5
Create Date: 2025-11-23 09:13:51.128162

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '31d7bac6547d'
down_revision: Union[str, Sequence[str], None] = '96a2f1b4ade5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Change status column from enum to VARCHAR to match SQLAlchemy's native_enum=False behavior."""
    # Convert enum to text (VARCHAR)
    op.execute("""
        ALTER TABLE wardrobe_items 
        ALTER COLUMN status TYPE VARCHAR(10) 
        USING status::text
    """)
    
    # Drop the enum type (no longer needed)
    op.execute("DROP TYPE IF EXISTS item_status_enum")


def downgrade() -> None:
    """Revert status column back to enum type."""
    # Recreate enum type
    op.execute("CREATE TYPE item_status_enum AS ENUM ('clean', 'worn', 'dirty')")
    
    # Convert VARCHAR back to enum
    op.execute("""
        ALTER TABLE wardrobe_items 
        ALTER COLUMN status TYPE item_status_enum 
        USING status::item_status_enum
    """)
