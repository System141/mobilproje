"""
Telemetry and monitoring setup using OpenTelemetry and Prometheus
"""

from typing import Dict, Any
import time
from functools import wraps

from prometheus_client import Counter, Histogram, Gauge, Info
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import Resource

from erp_platform.core.config import settings
from erp_platform.core.logging import get_logger

logger = get_logger(__name__)

# Prometheus metrics
request_counter = Counter(
    'erp_requests_total',
    'Total number of ERP requests',
    ['connector', 'operation', 'status']
)

request_duration = Histogram(
    'erp_request_duration_seconds',
    'Request duration in seconds',
    ['connector', 'operation']
)

active_connections = Gauge(
    'erp_active_connections',
    'Number of active ERP connections',
    ['connector']
)

system_info = Info(
    'erp_system',
    'ERP Integration Platform information'
)

# Initialize system info
system_info.info({
    'version': '1.0.0',
    'environment': settings.ENVIRONMENT,
    'python_version': '3.8+',
})


def setup_telemetry():
    """
    Initialize telemetry providers
    """
    if settings.ENABLE_TRACING:
        # Setup OpenTelemetry tracing
        resource = Resource.create({
            "service.name": "erp-integration-platform",
            "service.version": "1.0.0",
            "environment": settings.ENVIRONMENT,
        })
        
        provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(provider)
        
        logger.info("OpenTelemetry tracing initialized")
    
    if settings.ENABLE_METRICS:
        # Setup OpenTelemetry metrics
        provider = MeterProvider(resource=Resource.create({
            "service.name": "erp-integration-platform",
        }))
        metrics.set_meter_provider(provider)
        
        logger.info("Metrics collection initialized")


def track_request(connector: str, operation: str):
    """
    Decorator to track ERP requests
    
    Args:
        connector: Connector name (e.g., 'sap', 'oracle')
        operation: Operation name (e.g., 'read_table', 'execute_bapi')
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            status = "success"
            
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                status = "failure"
                raise
            finally:
                duration = time.time() - start_time
                
                # Update metrics
                request_counter.labels(
                    connector=connector,
                    operation=operation,
                    status=status
                ).inc()
                
                request_duration.labels(
                    connector=connector,
                    operation=operation
                ).observe(duration)
                
                logger.info(
                    "Request tracked",
                    connector=connector,
                    operation=operation,
                    status=status,
                    duration=duration
                )
        
        return wrapper
    return decorator


def track_connection(connector: str):
    """
    Context manager to track active connections
    
    Args:
        connector: Connector name
    """
    class ConnectionTracker:
        def __enter__(self):
            active_connections.labels(connector=connector).inc()
            return self
        
        def __exit__(self, exc_type, exc_val, exc_tb):
            active_connections.labels(connector=connector).dec()
    
    return ConnectionTracker()


class PerformanceTracker:
    """
    Track performance metrics for operations
    """
    
    def __init__(self):
        self.operations = {}
        
    def start_operation(self, name: str) -> str:
        """
        Start tracking an operation
        
        Args:
            name: Operation name
        
        Returns:
            Operation ID
        """
        op_id = f"{name}_{time.time()}"
        self.operations[op_id] = {
            'name': name,
            'start_time': time.time(),
        }
        return op_id
    
    def end_operation(self, op_id: str, metadata: Dict[str, Any] = None):
        """
        End tracking an operation
        
        Args:
            op_id: Operation ID
            metadata: Additional metadata
        """
        if op_id not in self.operations:
            return
        
        operation = self.operations[op_id]
        duration = time.time() - operation['start_time']
        
        logger.info(
            "Operation completed",
            operation=operation['name'],
            duration=duration,
            **(metadata or {})
        )
        
        del self.operations[op_id]
    
    def get_pending_operations(self) -> Dict[str, Any]:
        """
        Get list of pending operations
        """
        return {
            op_id: {
                'name': op['name'],
                'duration': time.time() - op['start_time']
            }
            for op_id, op in self.operations.items()
        }


# Global performance tracker
performance_tracker = PerformanceTracker()