"""
SQL Server Connector using pyodbc
"""

import asyncio
from typing import Any, Dict, List, Optional
import time

try:
    import pyodbc
    PYODBC_AVAILABLE = True
except ImportError:
    PYODBC_AVAILABLE = False
    pyodbc = None

from erp_platform.connectors.base import BaseConnector, ConnectionConfig
from erp_platform.core.logging import get_logger

logger = get_logger(__name__)


class SQLServerConnector(BaseConnector):
    """
    SQL Server connector using pyodbc
    """
    
    def __init__(self, config: ConnectionConfig):
        super().__init__(config)
        
        if not PYODBC_AVAILABLE:
            raise ImportError(
                "pyodbc is not installed. Please install it with: pip install pyodbc"
            )
        
        self.connection = None
        
    async def connect(self) -> bool:
        """
        Connect to SQL Server
        """
        try:
            start_time = time.time()
            
            # Build connection string
            driver = self.config.extra_params.get('driver', '{ODBC Driver 17 for SQL Server}')
            connection_string = (
                f'DRIVER={driver};'
                f'SERVER={self.config.host};'
                f'DATABASE={self.config.database};'
                f'UID={self.config.username};'
                f'PWD={self.config.password};'
            )
            
            # Add optional parameters
            if self.config.port:
                connection_string += f'PORT={self.config.port};'
            
            if self.config.extra_params.get('encrypt'):
                connection_string += 'Encrypt=yes;'
            
            if self.config.extra_params.get('trust_server_certificate'):
                connection_string += 'TrustServerCertificate=yes;'
            
            # Connect in thread pool
            loop = asyncio.get_event_loop()
            self.connection = await loop.run_in_executor(
                None,
                pyodbc.connect,
                connection_string,
                timeout=self.config.timeout
            )
            
            self.connected = True
            self.connection_time = time.time() - start_time
            
            logger.info(
                "Connected to SQL Server",
                host=self.config.host,
                database=self.config.database,
                duration=self.connection_time
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to SQL Server: {e}")
            self.connected = False
            raise
    
    async def disconnect(self) -> bool:
        """
        Disconnect from SQL Server
        """
        try:
            if self.connection:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self.connection.close)
                self.connection = None
            
            self.connected = False
            logger.info("Disconnected from SQL Server")
            return True
            
        except Exception as e:
            logger.error(f"Error disconnecting from SQL Server: {e}")
            return False
    
    async def execute(self, query: str, params: Dict[str, Any] = None) -> Any:
        """
        Execute SQL query
        """
        if not self.connected or not self.connection:
            raise RuntimeError("Not connected to SQL Server")
        
        try:
            loop = asyncio.get_event_loop()
            cursor = await loop.run_in_executor(
                None,
                self.connection.cursor
            )
            
            # Execute query
            if params:
                # Convert dict params to list for pyodbc
                param_list = list(params.values())
                await loop.run_in_executor(
                    None,
                    cursor.execute,
                    query,
                    param_list
                )
            else:
                await loop.run_in_executor(
                    None,
                    cursor.execute,
                    query
                )
            
            # Determine query type
            query_type = query.strip().upper().split()[0]
            
            if query_type in ['SELECT', 'WITH']:
                # Fetch results
                columns = [desc[0] for desc in cursor.description]
                rows = await loop.run_in_executor(None, cursor.fetchall)
                
                # Convert to list of dicts
                result = [dict(zip(columns, row)) for row in rows]
                
            elif query_type in ['INSERT', 'UPDATE', 'DELETE']:
                # Commit DML operations
                await loop.run_in_executor(None, self.connection.commit)
                result = {'rows_affected': cursor.rowcount}
                
            else:
                # DDL or other operations
                result = {'status': 'success'}
            
            await loop.run_in_executor(None, cursor.close)
            
            logger.debug(f"Executed query: {query[:100]}...")
            return result
            
        except Exception as e:
            logger.error(f"Query execution failed: {e}", query=query[:100])
            raise
    
    async def ping(self) -> bool:
        """
        Check SQL Server connection status
        """
        try:
            if not self.connection:
                return False
            
            # Execute simple query to check connection
            await self.execute("SELECT 1")
            return True
            
        except Exception:
            return False
    
    async def execute_many(
        self,
        query: str,
        data: List[List[Any]]
    ) -> Dict[str, Any]:
        """
        Execute bulk operations
        """
        if not self.connected or not self.connection:
            raise RuntimeError("Not connected to SQL Server")
        
        try:
            loop = asyncio.get_event_loop()
            cursor = await loop.run_in_executor(
                None,
                self.connection.cursor
            )
            
            # Use fast_executemany for better performance
            cursor.fast_executemany = True
            
            # Execute batch
            await loop.run_in_executor(
                None,
                cursor.executemany,
                query,
                data
            )
            
            await loop.run_in_executor(None, self.connection.commit)
            
            result = {
                'rows_affected': cursor.rowcount,
                'batch_size': len(data)
            }
            
            await loop.run_in_executor(None, cursor.close)
            
            logger.info(f"Executed batch operation: {result['rows_affected']} rows affected")
            return result
            
        except Exception as e:
            logger.error(f"Batch execution failed: {e}")
            raise
    
    async def call_procedure(
        self,
        procedure_name: str,
        params: List[Any] = None
    ) -> Any:
        """
        Call stored procedure
        """
        if not self.connected or not self.connection:
            raise RuntimeError("Not connected to SQL Server")
        
        try:
            loop = asyncio.get_event_loop()
            cursor = await loop.run_in_executor(
                None,
                self.connection.cursor
            )
            
            # Build procedure call
            param_placeholders = ','.join(['?' for _ in params]) if params else ''
            call_statement = f"{{CALL {procedure_name}({param_placeholders})}}"
            
            # Execute procedure
            if params:
                await loop.run_in_executor(
                    None,
                    cursor.execute,
                    call_statement,
                    params
                )
            else:
                await loop.run_in_executor(
                    None,
                    cursor.execute,
                    call_statement
                )
            
            # Get results if any
            if cursor.description:
                columns = [desc[0] for desc in cursor.description]
                rows = await loop.run_in_executor(None, cursor.fetchall)
                result = [dict(zip(columns, row)) for row in rows]
            else:
                result = {'status': 'success'}
            
            await loop.run_in_executor(None, cursor.close)
            
            logger.info(f"Called procedure: {procedure_name}")
            return result
            
        except Exception as e:
            logger.error(f"Procedure call failed: {e}", procedure=procedure_name)
            raise
    
    async def begin_transaction(self):
        """Begin a transaction"""
        if self.connection:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self.connection.execute,
                "BEGIN TRANSACTION"
            )
    
    async def commit_transaction(self):
        """Commit current transaction"""
        if self.connection:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.connection.commit)
    
    async def rollback_transaction(self):
        """Rollback current transaction"""
        if self.connection:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.connection.rollback)