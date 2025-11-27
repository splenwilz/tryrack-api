"""
Health check endpoints
Provides health and readiness status for the application

Industry standard pattern:
- /health (liveness): App is running (doesn't check dependencies)
- /ready (readiness): App is ready to serve (checks database connectivity)

Reference: 
- https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/
- https://fastapi.tiangolo.com/tutorial/bigger-applications/
"""
import logging
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from app.core.database import engine

logger = logging.getLogger(__name__)

# Create router for health-related endpoints
# Reference: https://fastapi.tiangolo.com/tutorial/bigger-applications/#include-an-apirouter
router = APIRouter(
    prefix="/health",
    tags=["health"],  # Groups endpoints in API documentation
)


class HealthResponse(BaseModel):
    """
    Response model for health check endpoint
    Reference: https://fastapi.tiangolo.com/tutorial/response-model/
    """
    status: str
    message: str


@router.get(
    "",
    response_model=HealthResponse,
    summary="Health check (liveness)",
    description="Returns the liveness status of the application. Does not check dependencies.",
    status_code=status.HTTP_200_OK,
)
async def health_check() -> HealthResponse:
    """
    Liveness probe endpoint
    
    Returns a simple status message indicating the service is running.
    This endpoint does NOT check database connectivity - it only confirms
    the application process is alive.
    
    **Use cases:**
    - Kubernetes liveness probes (restart container if unhealthy)
    - Load balancer health checks
    - Basic monitoring
    
    **Returns:**
        HealthResponse: Status and message indicating service is running
    """
    return HealthResponse(
        status="healthy",
        message="Service is running"
    )


@router.get(
    "/ready",
    response_model=HealthResponse,
    summary="Readiness check",
    description="Returns the readiness status including database connectivity check.",
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Service is ready"},
        503: {"description": "Service is not ready (database unavailable)"}
    }
)
async def readiness_check() -> HealthResponse:
    """
    Readiness probe endpoint
    
    Checks if the application is ready to serve traffic by validating
    database connectivity. This is more comprehensive than the liveness probe.
    
    **Use cases:**
    - Kubernetes readiness probes (stop sending traffic if not ready)
    - Load balancer readiness checks
    - Deployment validation
    
    **Returns:**
        HealthResponse: Status indicating if service is ready to serve
        
    **Raises:**
        HTTPException: 503 if database is unavailable
    """
    try:
        # Quick database connectivity check
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        return HealthResponse(
            status="ready",
            message="Service is ready to serve traffic"
        )
    except Exception as e:
        logger.warning(f"Readiness check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service is not ready - database unavailable"
        )

