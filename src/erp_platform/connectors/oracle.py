"""
Oracle Database Connector using python-oracledb
"""

import asyncio
from typing import Any, Dict, List, Optional
import time

try:
    import oracledb
    ORACLEDB_AVAILABLE = True
except ImportError:
    try:
        # Fallback to older python-oracledb package
        import oracledb
        ORACLEDB_AVAILABLE = True
    except ImportError:
        ORACLEDB_AVAILABLE = False
        oracledb = None

from erp_platform.connectors.base import BaseConnector, ConnectionConfig
from erp_platform.core.logging import get_logger

logger = get_logger(__name__)


class OracleConnector(BaseConnector):
    """
    Oracle database connector using python-oracledb
    """
    
    def __init__(self, config: ConnectionConfig):
        super().__init__(config)
        
        if not ORACLEDB_AVAILABLE:
            raise ImportError(
                "python-oracledb is not installed. Please install it with: pip install oracledb"
            )
        
        self.connection_pool = None
        self.connection = None
        
    async def connect(self) -> bool:
        """
        Connect to Oracle database
        """
        try:
            start_time = time.time()
            
            # Create connection pool for better performance
            loop = asyncio.get_event_loop()
            
            dsn = oracledb.makedsn(
                self.config.host,
                self.config.port or 1521,
                service_name=self.config.extra_params.get('service_name')
                or self.config.database
            )
            
            self.connection_pool = await loop.run_in_executor(
                None,
                oracledb.create_pool,
                self.config.username,
                self.config.password,
                dsn,
                1,  # min connections
                5,  # max connections
                1,  # increment
            )
            
            # Get a connection from pool to test
            self.connection = await loop.run_in_executor(
                None,
                self.connection_pool.acquire
            )
            
            self.connected = True
            self.connection_time = time.time() - start_time
            
            logger.info(
                "Connected to Oracle",
                host=self.config.host,
                database=self.config.database,
                duration=self.connection_time
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to Oracle: {e}")
            self.connected = False
            raise
    
    async def disconnect(self) -> bool:
        """
        Disconnect from Oracle database
        """
        try:
            if self.connection:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    self.connection_pool.release,
                    self.connection
                )
                self.connection = None
            
            if self.connection_pool:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    self.connection_pool.close
                )
                self.connection_pool = None
            
            self.connected = False
            logger.info("Disconnected from Oracle")
            return True
            
        except Exception as e:
            logger.error(f"Error disconnecting from Oracle: {e}")
            return False
    
    async def execute(self, query: str, params: Dict[str, Any] = None) -> Any:
        """
        Execute SQL query
        
        Args:
            query: SQL query string
            params: Query parameters
        
        Returns:
            Query result
        """
        if not self.connected or not self.connection:
            raise RuntimeError("Not connected to Oracle")
        
        try:
            loop = asyncio.get_event_loop()
            cursor = await loop.run_in_executor(
                None,
                self.connection.cursor
            )
            
            # Execute query
            if params:
                await loop.run_in_executor(
                    None,
                    cursor.execute,
                    query,
                    params
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
                # Fetch results for SELECT queries
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
        Check Oracle connection status
        """
        try:
            if not self.connection:
                return False
            
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self.connection.ping
            )
            return result is None  # ping returns None on success
            
        except Exception:
            return False
    
    async def execute_many(
        self,
        query: str,
        data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Execute bulk insert/update operations
        
        Args:
            query: SQL query with placeholders
            data: List of parameter dictionaries
        
        Returns:
            Execution result
        """
        if not self.connected or not self.connection:
            raise RuntimeError("Not connected to Oracle")
        
        try:
            loop = asyncio.get_event_loop()
            cursor = await loop.run_in_executor(
                None,
                self.connection.cursor
            )
            
            # Execute batch operation
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
        params: List[Any] = None,
        out_params: List[int] = None
    ) -> Any:
        """
        Call stored procedure
        
        Args:
            procedure_name: Name of the procedure
            params: Input parameters
            out_params: Indices of output parameters
        
        Returns:
            Procedure result
        """
        if not self.connected or not self.connection:
            raise RuntimeError("Not connected to Oracle")
        
        try:
            loop = asyncio.get_event_loop()
            cursor = await loop.run_in_executor(
                None,
                self.connection.cursor
            )
            
            # Prepare output parameters
            if out_params:
                for idx in out_params:
                    params[idx] = cursor.var(oracledb.STRING)
            
            # Call procedure
            await loop.run_in_executor(
                None,
                cursor.callproc,
                procedure_name,
                params or []
            )
            
            # Get output values
            if out_params:
                result = {}
                for idx in out_params:
                    result[f'out_{idx}'] = params[idx].getvalue()
            else:
                result = {'status': 'success'}
            
            await loop.run_in_executor(None, cursor.close)
            
            logger.info(f"Called procedure: {procedure_name}")
            return result
            
        except Exception as e:
            logger.error(f"Procedure call failed: {e}", procedure=procedure_name)
            raise
    
    async def get_table_metadata(self, table_name: str) -> Dict[str, Any]:
        """
        Get metadata for an Oracle table
        
        Args:
            table_name: Name of the table
        
        Returns:
            Table metadata
        """
        query = """
            SELECT 
                column_name,
                data_type,
                data_length,
                nullable,
                data_default
            FROM user_tab_columns
            WHERE table_name = :table_name
            ORDER BY column_id
        """
        
        columns = await self.execute(query, {'table_name': table_name.upper()})
        
        # Get table comments
        comment_query = """
            SELECT comments
            FROM user_tab_comments
            WHERE table_name = :table_name
        """
        
        comments = await self.execute(comment_query, {'table_name': table_name.upper()})
        
        return {
            'table_name': table_name,
            'description': comments[0]['COMMENTS'] if comments else '',
            'columns': columns,
        }
    
    async def begin_transaction(self):
        """Begin a transaction"""
        # Oracle starts transactions automatically
        pass
    
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