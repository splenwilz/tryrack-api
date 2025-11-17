# FastAPI Auth Starter

A clean architecture FastAPI project starter with PostgreSQL and Alembic migrations.

## Project Structure

```
fastapi_auth_starter/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application entry point
│   ├── api/
│   │   └── v1/
│   │       ├── api.py       # API router aggregation
│   │       └── routes/
│   │           └── health.py  # Health check endpoint
│   ├── core/
│   │   ├── config.py        # Application configuration
│   │   └── database.py      # Database connection and session management
│   ├── models/              # SQLAlchemy database models
│   ├── services/            # Business logic services
│   └── db/                  # Database utilities
├── alembic/                 # Database migration scripts
├── alembic.ini              # Alembic configuration
├── pyproject.toml           # Project dependencies (uv)
└── README.md
```

## Features

- ✅ Clean architecture with separation of concerns
- ✅ FastAPI with async SQLAlchemy
- ✅ PostgreSQL database support
- ✅ Alembic for database migrations
- ✅ Health check endpoint
- ✅ Dependency injection with FastAPI
- ✅ Environment-based configuration

## Prerequisites

- Python 3.12+ (3.13 for local dev, 3.12 for Vercel deployment)
- [uv](https://github.com/astral-sh/uv) package manager
- PostgreSQL database (local or remote)

## Setup

### 1. Install Dependencies

Dependencies are managed with `uv`. They are automatically installed when you run commands with `uv run`.

### 2. Configure Environment Variables

**Important:** Copy the example environment file and configure your settings:

```bash
cp .env.example .env
```

Then edit `.env` with your configuration:

```bash
# Database Configuration
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/fastapi_auth

# API Configuration (optional - defaults are fine)
API_V1_PREFIX=/api/v1
PROJECT_NAME=FastAPI Auth Starter
VERSION=0.1.0
```

**Note:** 
- The `.env` file is gitignored and should not be committed
- The application uses `asyncpg` for async operations, but Alembic uses `psycopg2` for migrations (sync driver)
- All sensitive configuration should be in `.env` file, not hardcoded

### 3. Initialize Database

First, ensure PostgreSQL is running and create the database:

```bash
createdb fastapi_auth
```

Or using PostgreSQL client:

```sql
CREATE DATABASE fastapi_auth;
```

### 4. Run Migrations

Create your initial migration based on your database models:

```bash
# Create initial migration
uv run alembic revision --autogenerate -m "Initial migration"

# Apply migrations
uv run alembic upgrade head
```

## Running the Application

### Development Server

```bash
uv run uvicorn app.main:app --reload
```

The API will be available at:
- API: http://localhost:8000
- Docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Health Check

Test the health endpoint:

```bash
curl http://localhost:8000/api/v1/health
```

Expected response:
```json
{
  "status": "healthy",
  "message": "Service is running"
}
```

## Development

### Adding New Routes

1. Create a new route file in `app/api/v1/routes/`
2. Import and include the router in `app/api/v1/api.py`

Example:
```python
# app/api/v1/routes/users.py
from fastapi import APIRouter

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/")
async def get_users():
    return {"users": []}
```

Then add to `app/api/v1/api.py`:
```python
from app.api.v1.routes import users
api_router.include_router(users.router)
```

### Adding Database Models

1. Create model in `app/models/`
2. Import in `app/models/__init__.py`
3. Import in `alembic/env.py` (for autogenerate)

Example:
```python
# app/models/user.py
from sqlalchemy import Column, Integer, String
from app.core.database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, index=True)
```

### Creating Migrations

```bash
# Auto-generate migration from model changes
uv run alembic revision --autogenerate -m "Description of changes"

# Create empty migration
uv run alembic revision -m "Description of changes"
```

### Applying Migrations

```bash
# Apply all pending migrations
uv run alembic upgrade head

# Rollback one migration
uv run alembic downgrade -1

# Rollback to specific revision
uv run alembic downgrade <revision>
```

## Architecture

### Layers

- **API Layer** (`app/api/`): Route handlers, request/response models
- **Service Layer** (`app/services/`): Business logic, domain operations
- **Model Layer** (`app/models/`): SQLAlchemy database models
- **Core Layer** (`app/core/`): Configuration, database setup, utilities

### Dependency Injection

FastAPI's dependency injection is used throughout:
- Database sessions via `get_db()` dependency
- Configuration via `settings` object
- Custom dependencies in `app/core/dependencies.py` (create as needed)

## Deployment

### Vercel Deployment

1. **Install Dev Dependencies Locally:**
   ```bash
   uv sync  # Installs all dependencies including dev
   ```

2. **Set Environment Variables in Vercel:**
   - Go to your project settings in Vercel
   - Add `DATABASE_URL` environment variable with your PostgreSQL connection string
   - Format: `postgresql+asyncpg://user:password@host:port/database`

3. **Deploy:**
   ```bash
   vercel --prod
   ```

**Note:** 
- Runtime dependencies don't include `psycopg2-binary` or `alembic` (only needed for local migrations)
- Python 3.12 is used (Vercel doesn't support 3.13 yet)
- Make sure to run migrations on your database before deploying

## References

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy Async Documentation](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [uv Documentation](https://github.com/astral-sh/uv)
- [Vercel Python Documentation](https://vercel.com/docs/functions/serverless-functions/runtimes/python)

## License

MIT

