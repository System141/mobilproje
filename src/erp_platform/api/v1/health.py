"""
Health check endpoints
"""

from fastapi import APIRouter, Depends
from typing import Dict, Any
import psutil
import time

from erp_platform.core.config import settings
from erp_platform.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)

start_time = time.time()


@router.get("/")
async def health_check() -> Dict[str, Any]:
    """
    Basic health check endpoint
    """
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
        "uptime": time.time() - start_time,
    }


@router.get("/detailed")
async def detailed_health() -> Dict[str, Any]:
    """
    Detailed health check with system metrics
    """
    # Get system metrics
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
        "uptime": time.time() - start_time,
        "system": {
            "cpu_percent": cpu_percent,
            "memory": {
                "total": memory.total,
                "available": memory.available,
                "percent": memory.percent,
            },
            "disk": {
                "total": disk.total,
                "used": disk.used,
                "free": disk.free,
                "percent": disk.percent,
            },
        },
        "connectors": {
            "sap_enabled": settings.SAP_ENABLED,
            "oracle_enabled": settings.ORACLE_ENABLED,
            "sqlserver_enabled": settings.SQLSERVER_ENABLED,
        },
    }


@router.get("/ready")
async def readiness_check() -> Dict[str, str]:
    """
    Kubernetes readiness probe endpoint
    """
    # Check if all required services are ready
    # In a real implementation, you would check database connections, etc.
    return {"status": "ready"}


@router.get("/live")
async def liveness_check() -> Dict[str, str]:
    """
    Kubernetes liveness probe endpoint
    """
    return {"status": "alive"}