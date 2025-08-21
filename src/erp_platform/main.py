"""
FastAPI main application with lifespan management
"""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app

from erp_platform.api.v1 import health, connectors, processors, tasks
from erp_platform.core.config import settings
from erp_platform.core.logging import get_logger
from erp_platform.core.telemetry import setup_telemetry
from erp_platform.connectors.pool import ConnectionPoolManager

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    Manage application lifecycle - startup and shutdown
    """
    # Startup
    logger.info("Starting ERP Integration Platform...")
    
    # Initialize telemetry
    setup_telemetry()
    
    # Initialize connection pools
    pool_manager = ConnectionPoolManager()
    
    try:
        # SAP Connection Pool
        if settings.SAP_ENABLED:
            await pool_manager.create_pool(
                "sap",
                max_connections=settings.SAP_POOL_SIZE,
                config={
                    "ashost": settings.SAP_HOST,
                    "sysnr": settings.SAP_SYSNR,
                    "client": settings.SAP_CLIENT,
                    "user": settings.SAP_USER,
                    "passwd": settings.SAP_PASSWORD,
                }
            )
            logger.info(f"SAP connection pool initialized with {settings.SAP_POOL_SIZE} connections")
        
        # Oracle Connection Pool
        if settings.ORACLE_ENABLED:
            await pool_manager.create_pool(
                "oracle",
                max_connections=settings.ORACLE_POOL_SIZE,
                config={
                    "host": settings.ORACLE_HOST,
                    "port": settings.ORACLE_PORT,
                    "service_name": settings.ORACLE_SERVICE,
                    "user": settings.ORACLE_USER,
                    "password": settings.ORACLE_PASSWORD,
                }
            )
            logger.info(f"Oracle connection pool initialized with {settings.ORACLE_POOL_SIZE} connections")
        
        # SQL Server Connection Pool
        if settings.SQLSERVER_ENABLED:
            await pool_manager.create_pool(
                "sqlserver",
                max_connections=settings.SQLSERVER_POOL_SIZE,
                config={
                    "server": settings.SQLSERVER_HOST,
                    "database": settings.SQLSERVER_DATABASE,
                    "username": settings.SQLSERVER_USER,
                    "password": settings.SQLSERVER_PASSWORD,
                }
            )
            logger.info(f"SQL Server connection pool initialized with {settings.SQLSERVER_POOL_SIZE} connections")
        
        # Store in app state
        app.state.pool_manager = pool_manager
        
        logger.info("All connection pools initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize connection pools: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down ERP Integration Platform...")
    
    # Close all connection pools
    await pool_manager.close_all()
    logger.info("All connection pools closed")
    
    # Cleanup tasks
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    for task in tasks:
        task.cancel()
    
    await asyncio.gather(*tasks, return_exceptions=True)
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    """
    Create and configure FastAPI application
    """
    app = FastAPI(
        title="ERP Integration Platform",
        description="Hybrid Python-to-C++ ERP Integration System",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/api/docs" if settings.ENABLE_DOCS else None,
        redoc_url="/api/redoc" if settings.ENABLE_DOCS else None,
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include routers
    app.include_router(health.router, prefix="/api/v1/health", tags=["health"])
    app.include_router(connectors.router, prefix="/api/v1/connectors", tags=["connectors"])
    app.include_router(processors.router, prefix="/api/v1/processors", tags=["processors"])
    app.include_router(tasks.router, prefix="/api/v1/tasks", tags=["tasks"])
    
    # Prometheus metrics endpoint
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)
    
    @app.on_event("startup")
    async def startup_event():
        logger.info(f"Application started - Environment: {settings.ENVIRONMENT}")
    
    return app


# Create application instance
app = create_app()

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "erp_platform.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )