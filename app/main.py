"""
FastAPI application entry point
Main application factory and configuration
Reference: https://fastapi.tiangolo.com/tutorial/bigger-applications/
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.v1.api import api_router
from app.core.config import settings
from app.core.database import engine

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events
    Validates database connection on startup
    Reference: https://fastapi.tiangolo.com/advanced/events/
    """
    # Startup: Test database connection
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("✓ Database connection successful")
    except Exception as e:
        logger.error(f"✗ Database connection failed: {e}")
        logger.error(
            "Please check:\n"
            "1. DATABASE_URL is set correctly in Vercel environment variables\n"
            "2. AWS RDS security group allows connections from Vercel IP ranges\n"
            "3. Database is accessible and credentials are correct"
        )
        # Don't raise - let the app start but connections will fail
        # This allows health checks to work
    
    yield
    
    # Shutdown: Dispose of database connections
    await engine.dispose()
    logger.info("Database connections closed")


# Create FastAPI application instance
# Reference: https://fastapi.tiangolo.com/reference/fastapi/
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="A clean architecture FastAPI starter with PostgreSQL and Alembic",
    docs_url="/docs",  # Swagger UI documentation
    redoc_url="/redoc",  # ReDoc documentation
    lifespan=lifespan,  # Add lifespan for startup/shutdown events
)

allowed_origins = [
    "http://localhost:3000",
    # add other trusted origins here
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include API routers
# All routes from api_router will be included in the main app
app.include_router(api_router)


@app.get("/")
async def root():
    """
    Root endpoint
    Provides basic information about the API
    """
    return {
        "message": f"Welcome to {settings.PROJECT_NAME}",
        "version": settings.VERSION,
        "docs": "/docs",
    }

