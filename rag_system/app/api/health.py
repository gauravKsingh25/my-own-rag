"""Health check endpoints."""
from fastapi import APIRouter, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.health import HealthResponse, ReadinessResponse
from app.core.config import settings
from app.db.database import get_db
from app.db.redis import get_redis, RedisClient
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Health check endpoint",
    description="Basic health check to verify the service is running",
)
async def health_check() -> HealthResponse:
    """
    Basic health check endpoint.
    
    Returns basic service information without checking dependencies.
    Use /ready for comprehensive readiness checks.
    """
    return HealthResponse(
        status="healthy",
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
    )


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    status_code=status.HTTP_200_OK,
    summary="Readiness check endpoint",
    description="Comprehensive readiness check including all dependencies",
)
async def readiness_check(
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
) -> ReadinessResponse:
    """
    Comprehensive readiness check.
    
    Verifies all critical dependencies are available and responsive:
    - PostgreSQL database
    - Redis cache
    
    Returns detailed status for each service.
    """
    services = {}
    all_ready = True
    
    # Check PostgreSQL
    try:
        await db.execute("SELECT 1")
        services["postgresql"] = {
            "status": "connected",
            "healthy": True,
        }
        logger.debug("PostgreSQL health check: OK")
    except Exception as e:
        services["postgresql"] = {
            "status": "disconnected",
            "healthy": False,
            "error": str(e),
        }
        all_ready = False
        logger.error(f"PostgreSQL health check failed: {str(e)}")
    
    # Check Redis
    try:
        redis_healthy = await redis.ping()
        services["redis"] = {
            "status": "connected" if redis_healthy else "disconnected",
            "healthy": redis_healthy,
        }
        logger.debug("Redis health check: OK")
    except Exception as e:
        services["redis"] = {
            "status": "disconnected",
            "healthy": False,
            "error": str(e),
        }
        all_ready = False
        logger.error(f"Redis health check failed: {str(e)}")
    
    return ReadinessResponse(
        status="ready" if all_ready else "not_ready",
        services=services,
        details={
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
        },
    )
