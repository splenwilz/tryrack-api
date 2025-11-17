"""
Database connection and session management
Uses SQLAlchemy async engine for PostgreSQL
Reference: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
"""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.core.config import settings


# Validate DATABASE_URL is set
if not settings.DATABASE_URL:
    raise ValueError(
        "DATABASE_URL environment variable is not set. "
        "Please set it in your .env file or Vercel environment variables."
    )

# Create async engine for PostgreSQL
# Using NullPool for serverless (Vercel) - each request gets a fresh connection
# Connection pooling doesn't work well in serverless environments where functions
# are isolated and can be terminated/cold-started
# Reference: https://docs.sqlalchemy.org/en/20/core/pooling.html#switching-pool-implementations
# Reference: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html#using-multiple-asyncio-event-loops
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,  # Set to True for SQL query logging (useful for debugging)
    poolclass=NullPool,  # No connection pooling - each request gets a new connection
    # This is critical for serverless environments where connection reuse
    # across function invocations causes connection termination errors
    # Reference: https://docs.sqlalchemy.org/en/20/core/pooling.html#disabling-pooling-using-nullpool
    connect_args={
        # asyncpg-specific connection arguments
        # Reference: https://magicstack.github.io/asyncpg/current/api/index.html#connection
        "command_timeout": 60,  # Increased timeout for serverless network latency
        "server_settings": {
            "application_name": "fastapi_auth_starter",
        },
    },
)


# Create async session factory
# This is used to create database sessions throughout the application
# Reference: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html#session-basics
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Keep objects accessible after commit
    # This is important for serverless - objects remain accessible after commit
    # allowing timestamps to be read even if not refreshed
    autocommit=False,
    autoflush=False,
)


# Base class for all database models
# All models should inherit from this class
# Reference: https://docs.sqlalchemy.org/en/20/orm/declarative_styles.html
class Base(DeclarativeBase):
    """Base class for SQLAlchemy declarative models"""
    pass


# Dependency to get database session
# Used in FastAPI route handlers via dependency injection
# Reference: https://fastapi.tiangolo.com/tutorial/dependencies/
async def get_db() -> AsyncSession:
    """
    Dependency function that provides a database session
    Automatically closes the session after the request completes
    
    For serverless environments (Vercel), this ensures proper transaction handling:
    - Commits on success
    - Rolls back on error
    - Always closes the session
    """
    async with async_session_maker() as session:
        try:
            yield session
            # Commit transaction on success
            # This commits all changes made during the request
            # In serverless, this must complete before the function terminates
            await session.commit()
        except Exception as e:
            # Rollback on any exception to maintain data consistency
            try:
                await session.rollback()
            except Exception:
                # If rollback fails, connection is likely already closed
                # This can happen in serverless when connections are terminated
                pass
            # Re-raise the original exception so FastAPI can handle it properly
            raise
        finally:
            # Always close the session to release connection
            # With NullPool, this closes the connection completely
            # In serverless, this is critical to prevent connection leaks
            try:
                await session.close()
            except Exception:
                # If close fails, connection is likely already closed or terminated
                # This is acceptable - we're in cleanup anyway
                pass

