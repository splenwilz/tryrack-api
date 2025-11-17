"""
Health check endpoint
Provides basic health status for the application
Reference: https://fastapi.tiangolo.com/tutorial/bigger-applications/
"""
from fastapi import APIRouter
from pydantic import BaseModel


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
    summary="Health check",
    description="Returns the health status of the application",
)
async def health_check() -> HealthResponse:
    """
    Health check endpoint
    
    Returns a simple status message indicating the service is running.
    This is useful for:
    - Load balancer health checks
    - Monitoring systems
    - Container orchestration (Kubernetes liveness/readiness probes)
    
    Returns:
        HealthResponse: Status and message indicating service health
    """
    return HealthResponse(
        status="healthy",
        message="Service is running"
    )

