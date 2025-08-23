"""
Turkish Business Integration Platform - FastAPI Application
"""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import make_asgi_app
import structlog

from src.config import settings
from src.database import engine, setup_row_level_security, DatabaseManager
from src.core.tenant import TenantMiddleware
from src.api.v1 import auth, tenants, integrations, webhooks
from src.utils.monitoring import setup_monitoring, MetricsMiddleware
from src.utils.turkish import setup_turkish_localization

# Configure structured logging
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.TimeStamper(fmt="ISO"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.make_filtering_bound_logger(
        min_level=getattr(structlog.stdlib, settings.log_level.upper())
    ),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    Application lifespan manager - handles startup and shutdown
    """
    # Startup
    logger.info(
        "Starting Turkish Business Integration Platform",
        version="1.0.0",
        environment=settings.environment
    )
    
    try:
        # Test database connection
        if await DatabaseManager.health_check():
            logger.info("✅ Database connection established")
        else:
            logger.error("❌ Database connection failed")
            raise Exception("Database connection failed")
        
        # Setup Row-Level Security for multi-tenant isolation
        if settings.is_production:
            await setup_row_level_security()
            logger.info("✅ Row-Level Security configured")
        
        # Setup monitoring
        if settings.prometheus_enabled:
            setup_monitoring()
            logger.info("✅ Monitoring configured")
        
        # Setup Turkish localization
        setup_turkish_localization()
        logger.info("✅ Turkish localization configured")
        
        logger.info("🚀 Application startup completed")
        
        yield
        
    except Exception as e:
        logger.error("❌ Application startup failed", error=str(e))
        raise
    
    # Shutdown
    logger.info("Shutting down Turkish Business Integration Platform...")
    
    try:
        # Close database connections
        await engine.dispose()
        logger.info("✅ Database connections closed")
        
        logger.info("👋 Application shutdown completed")
        
    except Exception as e:
        logger.error("❌ Error during shutdown", error=str(e))


# Create FastAPI application
app = FastAPI(
    title="Turkish Business Integration Platform",
    description="FastAPI Multi-Tenant SaaS for Turkish Business Systems",
    version="1.0.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else None,
    lifespan=lifespan
)

# Add security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add security headers to all responses"""
    response = await call_next(request)
    
    # Security headers for production
    if settings.is_production:
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    
    # Add Turkish compliance headers
    response.headers["X-Content-Language"] = "tr-TR"
    response.headers["X-Data-Residency"] = settings.data_residency_region
    
    return response

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)

# Add trusted host middleware for production
if settings.is_production:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*.yourdomain.com", "yourdomain.com"]
    )

# Add metrics middleware
if settings.prometheus_enabled:
    app.add_middleware(MetricsMiddleware)

# Add tenant middleware
tenant_middleware = TenantMiddleware(app)
app.add_middleware(TenantMiddleware)

# Exception handlers
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Handle 404 errors with Turkish localization"""
    return JSONResponse(
        status_code=404,
        content={
            "error": "not_found",
            "message": "Sayfa bulunamadı",
            "message_en": "Page not found",
            "path": request.url.path
        }
    )

@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    """Handle 500 errors with Turkish localization"""
    logger.error(
        "Internal server error",
        path=request.url.path,
        method=request.method,
        error=str(exc)
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "message": "Sunucu hatası",
            "message_en": "Internal server error"
        }
    )

# Health check endpoints
@app.get("/health", tags=["System"])
async def health_check():
    """Basic health check endpoint"""
    return {
        "status": "healthy",
        "service": "Turkish Business Integration Platform",
        "version": "1.0.0",
        "environment": settings.environment
    }

@app.get("/health/detailed", tags=["System"])
async def detailed_health_check():
    """Detailed health check with system information"""
    database_info = await DatabaseManager.get_database_info()
    database_healthy = await DatabaseManager.health_check()
    
    return {
        "status": "healthy" if database_healthy else "unhealthy",
        "service": "Turkish Business Integration Platform",
        "version": "1.0.0",
        "environment": settings.environment,
        "database": {
            "healthy": database_healthy,
            "info": database_info
        },
        "features": {
            "kvkk_compliance": settings.kvkk_enabled,
            "turkish_integrations": True,
            "multi_tenant": True
        }
    }

@app.get("/ready", tags=["System"])
async def readiness_check():
    """Kubernetes readiness probe endpoint"""
    database_healthy = await DatabaseManager.health_check()
    
    if not database_healthy:
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "message": "Database not available"
            }
        )
    
    return {"status": "ready"}

# Include API routers
app.include_router(
    auth.router,
    prefix="/api/v1/auth",
    tags=["Authentication"]
)

app.include_router(
    tenants.router,
    prefix="/api/v1/tenants",
    tags=["Tenants"]
)

app.include_router(
    integrations.router,
    prefix="/api/v1/integrations",
    tags=["Integrations"]
)

app.include_router(
    webhooks.router,
    prefix="/api/v1/webhooks",
    tags=["Webhooks"]
)

# Mount Prometheus metrics endpoint
if settings.prometheus_enabled:
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)

# Root endpoint
@app.get("/", tags=["System"])
async def root():
    """Root endpoint with service information"""
    return {
        "service": "Turkish Business Integration Platform",
        "version": "1.0.0",
        "description": "FastAPI Multi-Tenant SaaS for Turkish Business Systems",
        "features": [
            "Multi-tenant architecture",
            "KVKK compliance",
            "Turkish business system integrations",
            "Event-driven workflows",
            "Real-time monitoring"
        ],
        "integrations": {
            "netgsm": "SMS & WhatsApp messaging",
            "bulutfon": "Cloud phone system",
            "arvento": "Vehicle tracking",
            "findeks": "Credit scoring",
            "iyzico": "Payment processing",
            "efatura": "Electronic invoicing"
        },
        "docs": "/docs" if settings.debug else "Contact support",
        "environment": settings.environment
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
        access_log=settings.debug
    )