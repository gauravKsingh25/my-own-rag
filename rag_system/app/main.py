"""Main FastAPI application."""
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.core.middleware import RequestIDMiddleware
from app.core.exceptions import (
    BaseAPIException,
    base_exception_handler,
    http_exception_handler,
    validation_exception_handler,
    general_exception_handler,
)
from app.db.database import init_db, close_db
from app.db.redis import redis_client
from app.api.health import router as health_router
from app.api.documents import router as documents_router
from app.api.chat import router as chat_router

# Setup logging
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    Application lifespan manager.
    
    Handles startup and shutdown events.
    """
    # Startup
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    
    try:
        # Initialize database
        await init_db()
        logger.info("Database initialized")
        
        # Connect to Redis
        await redis_client.connect()
        logger.info("Redis connected")
        
        logger.info("Application startup complete")
        
    except Exception as e:
        logger.error(f"Startup failed: {str(e)}", exc_info=True)
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down application")
    
    try:
        # Close Redis connection
        await redis_client.disconnect()
        logger.info("Redis disconnected")
        
        # Close database connections
        await close_db()
        logger.info("Database connections closed")
        
        logger.info("Application shutdown complete")
        
    except Exception as e:
        logger.error(f"Shutdown error: {str(e)}", exc_info=True)


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Production-ready FastAPI infrastructure for enterprise RAG system",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
    debug=settings.DEBUG,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add request ID middleware
app.add_middleware(RequestIDMiddleware)

# Register exception handlers
app.add_exception_handler(BaseAPIException, base_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

# Include routers
app.include_router(health_router, prefix="", tags=["Health"])
app.include_router(documents_router, prefix=settings.API_V1_PREFIX, tags=["Documents"])
app.include_router(chat_router, tags=["Chat"])

# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "status": "running",
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )
