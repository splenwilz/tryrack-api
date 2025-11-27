"""fix_item_status_enum_values_to_lowercase

Revision ID: 96a2f1b4ade5
Revises: 0700b864b68d
Create Date: 2025-11-22 23:41:30.111969

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '96a2f1b4ade5'
down_revision: Union[str, Sequence[str], None] = '0700b864b68d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - convert item_status_enum from uppercase to lowercase values."""
    # Create new enum type with lowercase values
    op.execute("CREATE TYPE item_status_enum_new AS ENUM ('clean', 'worn', 'dirty')")
    
    # Convert existing data and alter column to use new enum
    # Using CASE to convert enum values to lowercase
    # Handles both uppercase (legacy DBs) and lowercase (fresh installs after migration fix) values
    op.execute("""
        ALTER TABLE wardrobe_items 
        ALTER COLUMN status TYPE item_status_enum_new 
        USING CASE 
            WHEN status::text IN ('CLEAN', 'clean') THEN 'clean'::item_status_enum_new
            WHEN status::text IN ('WORN', 'worn') THEN 'worn'::item_status_enum_new
            WHEN status::text IN ('DIRTY', 'dirty') THEN 'dirty'::item_status_enum_new
            ELSE NULL
        END
    """)
    
    # Drop old enum type
    op.execute("DROP TYPE item_status_enum")
    
    # Rename new enum to original name
    op.execute("ALTER TYPE item_status_enum_new RENAME TO item_status_enum")


def downgrade() -> None:
    """Downgrade schema - convert item_status_enum from lowercase to uppercase values."""
    # Create new enum type with uppercase values
    op.execute("CREATE TYPE item_status_enum_old AS ENUM ('CLEAN', 'WORN', 'DIRTY')")
    
    # Convert existing data and alter column to use old enum
    # Handles both lowercase and uppercase values (idempotent)
    op.execute("""
        ALTER TABLE wardrobe_items 
        ALTER COLUMN status TYPE item_status_enum_old 
        USING CASE 
            WHEN status::text IN ('clean', 'CLEAN') THEN 'CLEAN'::item_status_enum_old
            WHEN status::text IN ('worn', 'WORN') THEN 'WORN'::item_status_enum_old
            WHEN status::text IN ('dirty', 'DIRTY') THEN 'DIRTY'::item_status_enum_old
            ELSE NULL
        END
    """)
    
    # Drop lowercase enum type
    op.execute("DROP TYPE item_status_enum")
    
    # Rename old enum to original name
    op.execute("ALTER TYPE item_status_enum_old RENAME TO item_status_enum")
