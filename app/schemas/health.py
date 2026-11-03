from datetime import datetime, timezone
from typing import Dict, Optional

from pydantic import BaseModel, Field


class ServiceComponentStatus(BaseModel):
    status: str = Field(..., description="'up' or 'down'")
    latency_ms: Optional[float] = Field(None, description="Response time in milliseconds")
    error: Optional[str] = Field(None, description="Error detail if service is down")


class HealthResponse(BaseModel):
    status: str = Field(..., description="'healthy', 'degraded', or 'unhealthy'")
    environment: str
    version: str
    services: Dict[str, ServiceComponentStatus]
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

