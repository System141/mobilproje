"""
Health check and monitoring endpoints for Turkish Business Integration Platform
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
import structlog
import psutil

from src.core.security import get_current_user, require_permissions
from src.database import get_session
from src.services.tenant_service import tenant_service
from src.config import settings

logger = structlog.get_logger(__name__)
router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    timestamp: datetime
    version: str
    uptime: float
    checks: Dict[str, Any]


@router.get("/", response_model=HealthResponse)
async def health_check():
    """
    Basic health check endpoint
    """
    start_time = time.time()
    checks = {}
    
    # Database check
    try:
        async with get_session() as session:
            await session.execute("SELECT 1")
        checks["database"] = {
            "status": "healthy",
            "response_time": f"{(time.time() - start_time) * 1000:.2f}ms"
        }
    except Exception as e:
        checks["database"] = {
            "status": "unhealthy",
            "error": str(e),
            "response_time": f"{(time.time() - start_time) * 1000:.2f}ms"
        }
    
    # Redis check (for token blacklisting)
    try:
        import redis.asyncio as redis
        redis_client = redis.from_url(settings.redis_url, decode_responses=True)
        
        redis_start = time.time()
        await redis_client.ping()
        await redis_client.close()
        
        checks["redis"] = {
            "status": "healthy",
            "response_time": f"{(time.time() - redis_start) * 1000:.2f}ms"
        }
    except Exception as e:
        checks["redis"] = {
            "status": "unhealthy",
            "error": str(e)
        }
    
    # Determine overall status
    overall_status = "healthy"
    for check in checks.values():
        if check["status"] == "unhealthy":
            overall_status = "unhealthy"
            break
    
    # Calculate uptime (this is a simple implementation)
    uptime_seconds = time.time() - getattr(health_check, '_start_time', time.time())
    
    return HealthResponse(
        status=overall_status,
        timestamp=datetime.utcnow(),
        version="1.0.0",
        uptime=uptime_seconds,
        checks=checks
    )


@router.get("/detailed")
async def detailed_health_check(
    current_user: Dict[str, Any] = Depends(require_permissions(["monitoring:read"]))
):
    """
    Detailed health check with system metrics (admin only)
    """
    start_time = time.time()
    checks = {}
    
    # Database check with connection pool info
    try:
        async with get_session() as session:
            result = await session.execute("""
                SELECT 
                    version() as version,
                    current_database() as database,
                    current_user as user,
                    NOW() as current_time
            """)
            db_info = result.fetchone()
            
        checks["database"] = {
            "status": "healthy",
            "version": db_info.version.split(' ')[0] if db_info.version else "unknown",
            "database": db_info.database,
            "user": db_info.user,
            "response_time": f"{(time.time() - start_time) * 1000:.2f}ms"
        }
    except Exception as e:
        checks["database"] = {
            "status": "unhealthy",
            "error": str(e),
            "response_time": f"{(time.time() - start_time) * 1000:.2f}ms"
        }
    
    # Redis detailed check
    try:
        import redis.asyncio as redis
        redis_client = redis.from_url(settings.redis_url, decode_responses=True)
        
        redis_start = time.time()
        info = await redis_client.info()
        await redis_client.close()
        
        checks["redis"] = {
            "status": "healthy",
            "version": info.get("redis_version", "unknown"),
            "memory_used": info.get("used_memory_human", "unknown"),
            "connected_clients": info.get("connected_clients", 0),
            "response_time": f"{(time.time() - redis_start) * 1000:.2f}ms"
        }
    except Exception as e:
        checks["redis"] = {
            "status": "unhealthy",
            "error": str(e)
        }
    
    # System metrics
    try:
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # Memory usage
        memory = psutil.virtual_memory()
        
        # Disk usage
        disk = psutil.disk_usage('/')
        
        checks["system"] = {
            "status": "healthy",
            "cpu_percent": cpu_percent,
            "memory": {
                "total": f"{memory.total / (1024**3):.2f}GB",
                "used": f"{memory.used / (1024**3):.2f}GB", 
                "percent": memory.percent
            },
            "disk": {
                "total": f"{disk.total / (1024**3):.2f}GB",
                "used": f"{disk.used / (1024**3):.2f}GB",
                "percent": (disk.used / disk.total) * 100
            }
        }
    except Exception as e:
        checks["system"] = {
            "status": "unhealthy",
            "error": str(e)
        }
    
    # Service integrations check
    integrations_status = {}
    
    # NetGSM API check (if configured)
    try:
        tenant_id = current_user["tenant_id"]
        config_result = await tenant_service.get_integration_config(tenant_id, "netgsm")
        
        if config_result["success"]:
            from src.integrations.base_connector import ConnectorConfig
            from src.integrations.netgsm import NetgsmConnector
            
            connector_config = ConnectorConfig(
                base_url="https://api.netgsm.com.tr",
                username=config_result["config"].get("username"),
                password=config_result["config"].get("password")
            )
            
            netgsm_start = time.time()
            async with NetgsmConnector(connector_config) as connector:
                result = await connector.test_connection()
            
            integrations_status["netgsm"] = {
                "status": "healthy" if result.success else "unhealthy",
                "response_time": f"{(time.time() - netgsm_start) * 1000:.2f}ms",
                "error": result.error if not result.success else None
            }
        else:
            integrations_status["netgsm"] = {
                "status": "not_configured",
                "message": "NetGSM integration not configured"
            }
    except Exception as e:
        integrations_status["netgsm"] = {
            "status": "unhealthy",
            "error": str(e)
        }
    
    checks["integrations"] = integrations_status
    
    # Determine overall status
    overall_status = "healthy"
    for service_name, check in checks.items():
        if service_name == "integrations":
            # Don't fail overall health for integration issues
            continue
        if check["status"] == "unhealthy":
            overall_status = "unhealthy"
            break
    
    return {
        "status": overall_status,
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "environment": settings.environment,
        "debug_mode": settings.debug,
        "checks": checks
    }


@router.get("/readiness")
async def readiness_check():
    """
    Kubernetes readiness probe endpoint
    """
    try:
        # Check database connection
        async with get_session() as session:
            await session.execute("SELECT 1")
        
        # Check Redis connection
        import redis.asyncio as redis
        redis_client = redis.from_url(settings.redis_url, decode_responses=True)
        await redis_client.ping()
        await redis_client.close()
        
        return {
            "status": "ready",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error("Readiness check failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "not_ready",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )


@router.get("/liveness")
async def liveness_check():
    """
    Kubernetes liveness probe endpoint
    """
    return {
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat(),
        "uptime": time.time() - getattr(liveness_check, '_start_time', time.time())
    }


@router.get("/metrics")
async def get_metrics(
    current_user: Dict[str, Any] = Depends(require_permissions(["monitoring:metrics"]))
):
    """
    Get application metrics (admin only)
    """
    try:
        # Get tenant statistics
        tenant_id = current_user["tenant_id"]
        
        # Get usage stats for current tenant
        usage_result = await tenant_service.get_usage_stats(tenant_id)
        tenant_usage = usage_result.get("usage", {}) if usage_result["success"] else {}
        
        # System metrics
        cpu_percent = psutil.cpu_percent()
        memory = psutil.virtual_memory()
        
        # Process metrics
        process = psutil.Process()
        process_memory = process.memory_info()
        
        metrics = {
            "timestamp": datetime.utcnow().isoformat(),
            "tenant_metrics": {
                "tenant_id": str(tenant_id),
                "sms_sent_today": tenant_usage.get("sms_today", 0),
                "whatsapp_sent_today": tenant_usage.get("whatsapp_today", 0),
                "sms_sent_month": tenant_usage.get("sms_month", 0),
                "whatsapp_sent_month": tenant_usage.get("whatsapp_month", 0),
                "api_requests_today": tenant_usage.get("api_requests_today", 0)
            },
            "system_metrics": {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_used_mb": memory.used / (1024 * 1024),
                "memory_available_mb": memory.available / (1024 * 1024)
            },
            "process_metrics": {
                "memory_rss_mb": process_memory.rss / (1024 * 1024),
                "memory_vms_mb": process_memory.vms / (1024 * 1024),
                "cpu_percent": process.cpu_percent(),
                "num_threads": process.num_threads(),
                "open_files": len(process.open_files()) if hasattr(process, 'open_files') else 0
            }
        }
        
        return {
            "success": True,
            "metrics": metrics
        }
        
    except Exception as e:
        logger.error("Get metrics error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "metrics_error",
                "message": "Metrikler alınırken hata oluştu",
                "message_en": "Error getting metrics"
            }
        )


@router.get("/logs")
async def get_application_logs(
    current_user: Dict[str, Any] = Depends(require_permissions(["monitoring:logs"])),
    level: str = "INFO",
    limit: int = 100
):
    """
    Get recent application logs (admin only)
    
    Note: This is a basic implementation. In production, you'd typically
    integrate with a proper logging solution like ELK Stack, Fluentd, etc.
    """
    try:
        # This is a simplified implementation
        # In reality, you'd read from log files or a logging service
        
        import logging
        
        # Get recent log entries (this is a placeholder)
        # You would implement actual log reading logic here
        logs = [
            {
                "timestamp": datetime.utcnow().isoformat(),
                "level": "INFO",
                "logger": "uvicorn.access",
                "message": "Application health check endpoint accessed",
                "tenant_id": current_user["tenant_id"]
            }
        ]
        
        return {
            "success": True,
            "logs": logs,
            "level": level,
            "limit": limit,
            "note": "This is a basic implementation. Use proper logging aggregation in production."
        }
        
    except Exception as e:
        logger.error("Get logs error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "logs_error", 
                "message": "Loglar alınırken hata oluştu",
                "message_en": "Error getting logs"
            }
        )


@router.get("/status")
async def health_status():
    """Get health service status"""
    return {
        "status": "active",
        "service": "Health & Monitoring API",
        "version": "1.0.0",
        "endpoints": {
            "/health/": "Basic health check",
            "/health/detailed": "Detailed health check with system metrics",
            "/health/readiness": "Kubernetes readiness probe",
            "/health/liveness": "Kubernetes liveness probe", 
            "/health/metrics": "Application and system metrics",
            "/health/logs": "Recent application logs"
        },
        "monitoring_features": [
            "Database Connection Monitoring",
            "Redis Connection Monitoring", 
            "System Resource Monitoring",
            "Integration Health Checks",
            "Tenant Usage Metrics",
            "Process Metrics"
        ]
    }


# Initialize start time for uptime calculation
health_check._start_time = time.time()
liveness_check._start_time = time.time()