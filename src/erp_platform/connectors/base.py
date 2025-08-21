"""
Base connector class for all ERP systems
"""

import asyncio
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Dict, Optional, AsyncGenerator
import time

from erp_platform.core.logging import get_logger, log_performance

logger = get_logger(__name__)


@dataclass
class ConnectionConfig:
    """Configuration for ERP connections"""
    host: str
    port: int = None
    username: str = None
    password: str = None
    database: str = None
    timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0
    extra_params: Dict[str, Any] = None


class BaseConnector(ABC):
    """
    Abstract base class for ERP connectors
    """
    
    def __init__(self, config: ConnectionConfig):
        self.config = config
        self.connected = False
        self.connection = None
        self.connection_time = None
        self.total_requests = 0
        self.failed_requests = 0
        self.total_response_time = 0.0
        
    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection to ERP system"""
        pass
    
    @abstractmethod
    async def disconnect(self) -> bool:
        """Close connection to ERP system"""
        pass
    
    @abstractmethod
    async def execute(self, query: str, params: Dict[str, Any] = None) -> Any:
        """Execute query/operation on ERP system"""
        pass
    
    @abstractmethod
    async def ping(self) -> bool:
        """Check if connection is alive"""
        pass
    
    async def execute_with_retry(self, query: str, params: Dict[str, Any] = None) -> Any:
        """
        Execute operation with retry logic
        """
        last_error = None
        
        for attempt in range(self.config.max_retries):
            try:
                start_time = time.time()
                result = await self.execute(query, params)
                
                # Update statistics
                duration = time.time() - start_time
                self.total_requests += 1
                self.total_response_time += duration
                
                log_performance(
                    f"{self.__class__.__name__}.execute",
                    duration,
                    {"query": query[:100], "attempt": attempt + 1}
                )
                
                return result
                
            except Exception as e:
                last_error = e
                self.failed_requests += 1
                
                logger.warning(
                    "Query execution failed",
                    connector=self.__class__.__name__,
                    attempt=attempt + 1,
                    max_retries=self.config.max_retries,
                    error=str(e)
                )
                
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(self.config.retry_delay * (2 ** attempt))
                    
                    # Check and reconnect if needed
                    if not await self.ping():
                        logger.info("Connection lost, attempting to reconnect")
                        await self.reconnect()
        
        raise last_error
    
    async def reconnect(self) -> bool:
        """
        Reconnect to ERP system
        """
        logger.info(f"Reconnecting to {self.__class__.__name__}")
        
        if self.connected:
            await self.disconnect()
        
        return await self.connect()
    
    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator:
        """
        Context manager for transactions
        """
        if not self.connected:
            raise RuntimeError("Not connected to ERP system")
        
        # Begin transaction (implementation specific)
        await self.begin_transaction()
        
        try:
            yield self
            await self.commit_transaction()
        except Exception as e:
            await self.rollback_transaction()
            raise e
    
    async def begin_transaction(self):
        """Begin a transaction (override in subclasses if supported)"""
        pass
    
    async def commit_transaction(self):
        """Commit a transaction (override in subclasses if supported)"""
        pass
    
    async def rollback_transaction(self):
        """Rollback a transaction (override in subclasses if supported)"""
        pass
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get connector statistics
        """
        avg_response_time = (
            self.total_response_time / self.total_requests 
            if self.total_requests > 0 
            else 0
        )
        
        return {
            "connected": self.connected,
            "total_requests": self.total_requests,
            "failed_requests": self.failed_requests,
            "success_rate": (
                (self.total_requests - self.failed_requests) / self.total_requests * 100
                if self.total_requests > 0
                else 100
            ),
            "average_response_time": avg_response_time,
            "connection_time": self.connection_time,
        }
    
    def __repr__(self):
        return f"{self.__class__.__name__}(host={self.config.host}, connected={self.connected})"