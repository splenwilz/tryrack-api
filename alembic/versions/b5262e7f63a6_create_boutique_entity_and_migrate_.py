"""create_boutique_entity_and_migrate_relationships

Revision ID: b5262e7f63a6
Revises: 3683265c723a
Create Date: 2025-12-03 09:02:07.022560

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b5262e7f63a6'
down_revision: Union[str, Sequence[str], None] = '3683265c723a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: Create Boutique entity and migrate relationships."""
    # Step 1: Create boutiques table
    op.create_table(
        'boutiques',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('owner_id', sa.String(), nullable=False, comment='User ID of the boutique owner (creator)'),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_boutiques_owner_id'), 'boutiques', ['owner_id'], unique=False)

    # Step 2: Create boutiques for existing users with boutique_profiles
    # For each user with a boutique_profile, create a boutique
    op.execute("""
        INSERT INTO boutiques (owner_id, created_at, updated_at)
        SELECT DISTINCT user_id, created_at, updated_at
        FROM boutique_profiles
        WHERE user_id IS NOT NULL
    """)

    # Step 3: Add boutique_id columns (nullable first for data migration)
    op.add_column('boutique_looks', sa.Column('boutique_id', sa.Integer(), nullable=True))
    op.add_column('boutique_profiles', sa.Column('boutique_id', sa.Integer(), nullable=True))
    op.add_column('catalog_items', sa.Column('boutique_id', sa.Integer(), nullable=True))

    # Step 4: Migrate data - set boutique_id from user_id
    # For boutique_looks: get boutique_id from user_id via boutiques table
    op.execute("""
        UPDATE boutique_looks
        SET boutique_id = (
            SELECT b.id
            FROM boutiques b
            WHERE b.owner_id = boutique_looks.user_id
        )
        WHERE user_id IS NOT NULL
    """)

    # For boutique_profiles: get boutique_id from user_id via boutiques table
    op.execute("""
        UPDATE boutique_profiles
        SET boutique_id = (
            SELECT b.id
            FROM boutiques b
            WHERE b.owner_id = boutique_profiles.user_id
        )
        WHERE user_id IS NOT NULL
    """)

    # For catalog_items: get boutique_id from user_id via boutiques table
    op.execute("""
        UPDATE catalog_items
        SET boutique_id = (
            SELECT b.id
            FROM boutiques b
            WHERE b.owner_id = catalog_items.user_id
        )
        WHERE user_id IS NOT NULL
    """)

    # Step 5: Delete orphaned records (items without matching boutiques)
    # This should not happen if data is consistent, but safety check
    op.execute("DELETE FROM boutique_looks WHERE boutique_id IS NULL")
    op.execute("DELETE FROM boutique_profiles WHERE boutique_id IS NULL")
    op.execute("DELETE FROM catalog_items WHERE boutique_id IS NULL")

    # Step 6: Make boutique_id columns non-nullable
    op.alter_column('boutique_looks', 'boutique_id', nullable=False)
    op.alter_column('boutique_profiles', 'boutique_id', nullable=False)
    op.alter_column('catalog_items', 'boutique_id', nullable=False)

    # Step 7: Add comments to boutique_id columns
    op.alter_column('boutique_looks', 'boutique_id', comment='Boutique ID - links look to boutique')
    op.alter_column('boutique_profiles', 'boutique_id', comment='Boutique ID (unique - one profile per boutique)')
    op.alter_column('catalog_items', 'boutique_id', comment='Boutique ID - links catalog item to boutique')

    # Step 8: Update indexes and constraints for boutique_looks
    op.drop_index(op.f('ix_boutique_looks_user_featured'), table_name='boutique_looks')
    op.drop_index(op.f('ix_boutique_looks_user_id'), table_name='boutique_looks')
    op.create_index('ix_boutique_looks_boutique_featured', 'boutique_looks', ['boutique_id', 'is_featured'], unique=False)
    op.create_index('ix_boutique_looks_boutique_id', 'boutique_looks', ['boutique_id'], unique=False)
    op.drop_constraint(op.f('boutique_looks_user_id_fkey'), 'boutique_looks', type_='foreignkey')
    op.create_foreign_key(None, 'boutique_looks', 'boutiques', ['boutique_id'], ['id'], ondelete='CASCADE')
    op.drop_column('boutique_looks', 'user_id')

    # Step 9: Update constraints for boutique_profiles
    op.drop_constraint(op.f('uq_boutique_profiles_user_id'), 'boutique_profiles', type_='unique')
    op.create_unique_constraint('uq_boutique_profiles_boutique_id', 'boutique_profiles', ['boutique_id'])
    op.drop_constraint(op.f('boutique_profiles_user_id_fkey'), 'boutique_profiles', type_='foreignkey')
    op.create_foreign_key(None, 'boutique_profiles', 'boutiques', ['boutique_id'], ['id'], ondelete='CASCADE')
    op.drop_column('boutique_profiles', 'user_id')

    # Step 10: Update indexes and constraints for catalog_items
    op.drop_index(op.f('ix_catalog_items_user_id'), table_name='catalog_items')
    op.create_index(op.f('ix_catalog_items_boutique_id'), 'catalog_items', ['boutique_id'], unique=False)
    op.drop_constraint(op.f('fk_catalog_items_user_id'), 'catalog_items', type_='foreignkey')
    op.create_foreign_key(None, 'catalog_items', 'boutiques', ['boutique_id'], ['id'], ondelete='CASCADE')
    op.drop_column('catalog_items', 'user_id')

    # Step 11: Update comment on virtual_try_on_sessions.selected_items
    op.alter_column('virtual_try_on_sessions', 'selected_items',
               existing_type=postgresql.JSON(astext_type=sa.Text()),
               comment='Snapshot of items selected for this session (wardrobe items and/or boutique products)',
               existing_comment='Snapshot of the wardrobe items selected for this session',
               existing_nullable=False)


def downgrade() -> None:
    """Downgrade schema: Revert to user_id relationships."""
    # Revert comment
    op.alter_column('virtual_try_on_sessions', 'selected_items',
               existing_type=postgresql.JSON(astext_type=sa.Text()),
               comment='Snapshot of the wardrobe items selected for this session',
               existing_comment='Snapshot of items selected for this session (wardrobe items and/or boutique products)',
               existing_nullable=False)

    # Revert catalog_items
    op.add_column('catalog_items', sa.Column('user_id', sa.VARCHAR(), autoincrement=False, nullable=True))
    op.execute("""
        UPDATE catalog_items
        SET user_id = (
            SELECT b.owner_id
            FROM boutiques b
            WHERE b.id = catalog_items.boutique_id
        )
        WHERE boutique_id IS NOT NULL
    """)
    op.alter_column('catalog_items', 'user_id', nullable=False)
    op.drop_constraint(None, 'catalog_items', type_='foreignkey')
    op.create_foreign_key(op.f('fk_catalog_items_user_id'), 'catalog_items', 'users', ['user_id'], ['id'], ondelete='CASCADE')
    op.drop_index(op.f('ix_catalog_items_boutique_id'), table_name='catalog_items')
    op.create_index(op.f('ix_catalog_items_user_id'), 'catalog_items', ['user_id'], unique=False)
    op.drop_column('catalog_items', 'boutique_id')

    # Revert boutique_profiles
    op.add_column('boutique_profiles', sa.Column('user_id', sa.VARCHAR(), autoincrement=False, nullable=True))
    op.execute("""
        UPDATE boutique_profiles
        SET user_id = (
            SELECT b.owner_id
            FROM boutiques b
            WHERE b.id = boutique_profiles.boutique_id
        )
        WHERE boutique_id IS NOT NULL
    """)
    op.alter_column('boutique_profiles', 'user_id', nullable=False)
    op.drop_constraint(None, 'boutique_profiles', type_='foreignkey')
    op.create_foreign_key(op.f('boutique_profiles_user_id_fkey'), 'boutique_profiles', 'users', ['user_id'], ['id'], ondelete='CASCADE')
    op.drop_constraint('uq_boutique_profiles_boutique_id', 'boutique_profiles', type_='unique')
    op.create_unique_constraint(op.f('uq_boutique_profiles_user_id'), 'boutique_profiles', ['user_id'], postgresql_nulls_not_distinct=False)
    op.drop_column('boutique_profiles', 'boutique_id')

    # Revert boutique_looks
    op.add_column('boutique_looks', sa.Column('user_id', sa.VARCHAR(), autoincrement=False, nullable=True))
    op.execute("""
        UPDATE boutique_looks
        SET user_id = (
            SELECT b.owner_id
            FROM boutiques b
            WHERE b.id = boutique_looks.boutique_id
        )
        WHERE boutique_id IS NOT NULL
    """)
    op.alter_column('boutique_looks', 'user_id', nullable=False)
    op.drop_constraint(None, 'boutique_looks', type_='foreignkey')
    op.create_foreign_key(op.f('boutique_looks_user_id_fkey'), 'boutique_looks', 'users', ['user_id'], ['id'], ondelete='CASCADE')
    op.drop_index('ix_boutique_looks_boutique_id', table_name='boutique_looks')
    op.drop_index('ix_boutique_looks_boutique_featured', table_name='boutique_looks')
    op.create_index(op.f('ix_boutique_looks_user_id'), 'boutique_looks', ['user_id'], unique=False)
    op.create_index(op.f('ix_boutique_looks_user_featured'), 'boutique_looks', ['user_id', 'is_featured'], unique=False)
    op.drop_column('boutique_looks', 'boutique_id')

    # Drop boutiques table
    op.drop_index(op.f('ix_boutiques_owner_id'), table_name='boutiques')
    op.drop_table('boutiques')
