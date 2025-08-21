"""
Connection pool management for ERP connectors
"""

import asyncio
from asyncio import Semaphore
from typing import Dict, Any, Optional
from contextlib import asynccontextmanager

from erp_platform.connectors.base import BaseConnector, ConnectionConfig
from erp_platform.connectors.sap import SAPConnector
from erp_platform.connectors.oracle import OracleConnector
from erp_platform.core.logging import get_logger

logger = get_logger(__name__)


class ConnectionPool:
    """
    Generic connection pool for ERP connectors
    """
    
    def __init__(self, connector_class: type, config: ConnectionConfig, max_connections: int = 5):
        self.connector_class = connector_class
        self.config = config
        self.max_connections = max_connections
        self.semaphore = Semaphore(max_connections)
        self.available_connections = []
        self.in_use_connections = set()
        self.lock = asyncio.Lock()
        self.initialized = False
        
    async def initialize(self):
        """
        Initialize the connection pool
        """
        if self.initialized:
            return
        
        async with self.lock:
            for _ in range(self.max_connections):
                connector = self.connector_class(self.config)
                await connector.connect()
                self.available_connections.append(connector)
            
            self.initialized = True
            logger.info(
                f"Connection pool initialized",
                connector=self.connector_class.__name__,
                size=self.max_connections
            )
    
    @asynccontextmanager
    async def acquire(self):
        """
        Acquire a connection from the pool
        """
        if not self.initialized:
            await self.initialize()
        
        await self.semaphore.acquire()
        
        async with self.lock:
            while not self.available_connections:
                await asyncio.sleep(0.1)
            
            connector = self.available_connections.pop()
            
            # Check connection health
            if not await connector.ping():
                logger.warning("Connection unhealthy, reconnecting")
                await connector.reconnect()
            
            self.in_use_connections.add(connector)
        
        try:
            yield connector
        finally:
            async with self.lock:
                self.in_use_connections.discard(connector)
                self.available_connections.append(connector)
            
            self.semaphore.release()
    
    async def close(self):
        """
        Close all connections in the pool
        """
        async with self.lock:
            # Close available connections
            for connector in self.available_connections:
                await connector.disconnect()
            
            # Close in-use connections
            for connector in self.in_use_connections:
                await connector.disconnect()
            
            self.available_connections.clear()
            self.in_use_connections.clear()
            self.initialized = False
            
            logger.info(f"Connection pool closed for {self.connector_class.__name__}")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get pool statistics
        """
        return {
            'max_connections': self.max_connections,
            'available': len(self.available_connections),
            'in_use': len(self.in_use_connections),
            'initialized': self.initialized,
        }


class ConnectionPoolManager:
    """
    Manages multiple connection pools for different ERP systems
    """
    
    def __init__(self):
        self.pools: Dict[str, ConnectionPool] = {}
        
    async def create_pool(
        self,
        name: str,
        connector_class: Optional[type] = None,
        config: Optional[Dict[str, Any]] = None,
        max_connections: int = 5
    ):
        """
        Create a new connection pool
        
        Args:
            name: Pool name (e.g., 'sap', 'oracle')
            connector_class: Connector class to use
            config: Connection configuration
            max_connections: Maximum number of connections
        """
        # Auto-detect connector class based on name
        if connector_class is None:
            connector_map = {
                'sap': SAPConnector,
                'oracle': OracleConnector,
            }
            connector_class = connector_map.get(name.lower())
            
            if connector_class is None:
                raise ValueError(f"Unknown connector type: {name}")
        
        # Create connection config
        connection_config = ConnectionConfig(
            host=config.get('host') or config.get('ashost'),
            port=config.get('port'),
            username=config.get('user') or config.get('username'),
            password=config.get('passwd') or config.get('password'),
            database=config.get('database') or config.get('service_name'),
            extra_params=config
        )
        
        # Create and initialize pool
        pool = ConnectionPool(connector_class, connection_config, max_connections)
        await pool.initialize()
        
        self.pools[name] = pool
        logger.info(f"Created connection pool: {name}")
    
    def get_pool(self, name: str) -> Optional[ConnectionPool]:
        """
        Get a connection pool by name
        """
        return self.pools.get(name)
    
    @asynccontextmanager
    async def get_connection(self, pool_name: str):
        """
        Get a connection from a specific pool
        """
        pool = self.get_pool(pool_name)
        if pool is None:
            raise ValueError(f"Connection pool '{pool_name}' not found")
        
        async with pool.acquire() as connector:
            yield connector
    
    async def close_pool(self, name: str):
        """
        Close a specific connection pool
        """
        pool = self.pools.get(name)
        if pool:
            await pool.close()
            del self.pools[name]
            logger.info(f"Closed connection pool: {name}")
    
    async def close_all(self):
        """
        Close all connection pools
        """
        for name in list(self.pools.keys()):
            await self.close_pool(name)
    
    def get_all_stats(self) -> Dict[str, Any]:
        """
        Get statistics for all pools
        """
        return {
            name: pool.get_stats()
            for name, pool in self.pools.items()
        }