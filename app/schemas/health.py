"""Pydantic schemas for health check endpoints"""

from pydantic import BaseModel, Field
from typing import Dict
from datetime import datetime


class ComponentHealthStatus(BaseModel):
    """Health status of a single component"""
    name: str = Field(..., description="Component name")
    status: str = Field(..., description="Status: 'healthy' or 'unhealthy'")
    message: str = Field(default="", description="Status message")
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "redis",
                "status": "healthy",
                "message": "Connected"
            }
        }


class HealthResponse(BaseModel):
    """Response model for health check endpoint"""
    status: str = Field(..., description="Overall status: 'healthy' or 'unhealthy'")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Health check timestamp")
    version: str = Field(default="1.0.0", description="API version")
    components: Dict[str, str] = Field(default_factory=dict, description="Per-component status")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "timestamp": "2026-03-26T10:30:00",
                "version": "1.0.0",
                "components": {
                    "redis": "healthy",
                    "prometheus": "healthy",
                    "collector": "initialized"
                }
            }
        }
