"""
Alembic environment configuration
Handles database migrations with SQLAlchemy
Reference: https://alembic.sqlalchemy.org/en/latest/tutorial.html
"""
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# Import Base and models for autogenerate support
from app.core.database import Base
from app.models import Task, User  # Import all models here so Alembic can detect them

# This is the Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override sqlalchemy.url from settings if not set in alembic.ini
# Convert asyncpg URL to psycopg2 URL for Alembic (Alembic uses sync drivers)
if not config.get_main_option("sqlalchemy.url"):
    from app.core.config import settings
    # Convert asyncpg URL to psycopg2 URL (sync driver for migrations)
    db_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
    # Escape % for ConfigParser (double % to prevent interpolation)
    db_url = db_url.replace("%", "%%")
    config.set_main_option("sqlalchemy.url", db_url)

# Set target_metadata for autogenerate support
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
