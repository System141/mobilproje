"""
Monitoring utilities for Turkish Business Integration Platform
"""

import time
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import structlog

logger = structlog.get_logger(__name__)

def setup_monitoring():
    """Setup monitoring configuration"""
    logger.info("Monitoring setup completed")

class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware for collecting metrics"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        
        response = await call_next(request)
        
        process_time = time.time() - start_time
        logger.info(
            "Request processed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            process_time=process_time
        )
        
        return response