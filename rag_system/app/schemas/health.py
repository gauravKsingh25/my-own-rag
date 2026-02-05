"""Health check schemas."""
from typing import Dict, Any
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Health check response schema."""
    
    status: str = Field(..., description="Health status (healthy/unhealthy)")
    version: str = Field(..., description="Application version")
    environment: str = Field(..., description="Environment name")


class ReadinessResponse(BaseModel):
    """Readiness check response schema."""
    
    status: str = Field(..., description="Readiness status (ready/not_ready)")
    services: Dict[str, Any] = Field(..., description="Status of dependent services")
    details: Dict[str, Any] = Field(default_factory=dict, description="Additional details")
