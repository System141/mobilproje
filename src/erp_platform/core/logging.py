"""
Structured logging configuration using structlog
"""

import logging
import sys
from typing import Any, Dict

import structlog
from structlog.processors import CallsiteParameter

from erp_platform.core.config import settings


def setup_logging():
    """
    Configure structured logging for the application
    """
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.CallsiteParameterAdder(
                parameters=[
                    CallsiteParameter.FILENAME,
                    CallsiteParameter.FUNC_NAME,
                    CallsiteParameter.LINENO,
                ]
            ),
            structlog.dev.ConsoleRenderer() if settings.DEBUG else structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.LOG_LEVEL),
    )
    
    # Suppress noisy loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Get a structured logger instance
    
    Args:
        name: Logger name (usually __name__)
    
    Returns:
        Configured logger instance
    """
    return structlog.get_logger(name)


def log_performance(func_name: str, duration: float, metadata: Dict[str, Any] = None):
    """
    Log performance metrics for a function
    
    Args:
        func_name: Name of the function
        duration: Execution duration in seconds
        metadata: Additional metadata to log
    """
    logger = get_logger(__name__)
    logger.info(
        "performance_metric",
        function=func_name,
        duration_ms=duration * 1000,
        **(metadata or {})
    )


# Initialize logging on module import
setup_logging()