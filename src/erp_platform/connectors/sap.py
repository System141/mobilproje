"""
SAP Connector with multiple connectivity options:
1. PyRFC (RFC/BAPI calls) - requires SAP NetWeaver RFC SDK
2. REST/OData API calls - standard HTTP-based connectivity
"""

import asyncio
import os
from typing import Any, Dict, List, Optional
import time

# Try to import PyRFC
try:
    from pyrfc import Connection
    PYRFC_AVAILABLE = True
except ImportError:
    PYRFC_AVAILABLE = False
    Connection = None

# REST/OData dependencies - these should always be available
try:
    import requests
    from requests_oauthlib import OAuth2Session
    import xml.etree.ElementTree as ET
    REST_AVAILABLE = True
except ImportError:
    REST_AVAILABLE = False

from erp_platform.connectors.base import BaseConnector, ConnectionConfig
from erp_platform.core.logging import get_logger

logger = get_logger(__name__)


class SAPConnector(BaseConnector):
    """
    SAP connector implementation supporting multiple connectivity modes:
    - RFC mode: Uses PyRFC for direct RFC/BAPI calls (requires SAP SDK)
    - REST mode: Uses HTTP/OData APIs (standard HTTP connectivity)
    """
    
    def __init__(self, config: ConnectionConfig):
        super().__init__(config)
        
        # Determine connection mode based on availability and configuration
        self.connection_mode = self._determine_connection_mode(config)
        
        # Initialize connection objects
        self.rfc_connection = None
        self.rest_session = None
        self.base_url = None
        
        logger.info(f"SAP connector initialized in {self.connection_mode} mode")
    
    def _determine_connection_mode(self, config: ConnectionConfig) -> str:
        """
        Determine which connection mode to use based on:
        1. Explicit mode setting in config
        2. PyRFC availability
        3. Environment variables
        """
        # Check for explicit mode in config
        if config.extra_params and 'connection_mode' in config.extra_params:
            requested_mode = config.extra_params['connection_mode'].lower()
            if requested_mode == 'rfc' and not PYRFC_AVAILABLE:
                logger.warning(
                    "RFC mode requested but PyRFC not available, falling back to REST mode"
                )
                return 'rest'
            return requested_mode
        
        # Check environment variable
        env_mode = os.getenv('SAP_CONNECTION_MODE', '').lower()
        if env_mode in ['rfc', 'rest']:
            if env_mode == 'rfc' and not PYRFC_AVAILABLE:
                logger.warning(
                    "RFC mode set in environment but PyRFC not available, falling back to REST mode"
                )
                return 'rest'
            return env_mode
        
        # Auto-detect based on availability
        if PYRFC_AVAILABLE:
            return 'rfc'
        elif REST_AVAILABLE:
            return 'rest'
        else:
            raise ImportError(
                "Neither PyRFC nor REST dependencies are available. "
                "Please install either:\n"
                "- For RFC mode: pip install pyrfc (requires SAP NetWeaver RFC SDK)\n"
                "- For REST mode: pip install requests requests-oauthlib"
            )
        
    async def connect(self) -> bool:
        """
        Connect to SAP system using the appropriate mode
        """
        if self.connection_mode == 'rfc':
            return await self._connect_rfc()
        else:
            return await self._connect_rest()
    
    async def _connect_rfc(self) -> bool:
        """
        Connect to SAP system using RFC
        """
        try:
            start_time = time.time()
            
            # Prepare connection parameters
            conn_params = {
                'ashost': self.config.host,
                'sysnr': self.config.extra_params.get('sysnr', '00'),
                'client': self.config.extra_params.get('client', '100'),
                'user': self.config.username,
                'passwd': self.config.password,
                'lang': self.config.extra_params.get('lang', 'EN'),
            }
            
            # Add optional parameters
            if self.config.extra_params:
                for key in ['router', 'gwhost', 'gwserv', 'group', 'sncmode']:
                    if key in self.config.extra_params:
                        conn_params[key] = self.config.extra_params[key]
            
            # Connect in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            self.rfc_connection = await loop.run_in_executor(
                None,
                lambda: Connection(**conn_params)
            )
            
            self.connected = True
            self.connection_time = time.time() - start_time
            
            logger.info(
                "Connected to SAP via RFC",
                host=self.config.host,
                client=conn_params['client'],
                duration=self.connection_time
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to SAP via RFC: {e}")
            self.connected = False
            raise
    
    async def _connect_rest(self) -> bool:
        """
        Connect to SAP system using REST/OData APIs
        """
        try:
            start_time = time.time()
            
            # Build base URL for SAP OData services
            protocol = 'https' if self.config.port == 443 else 'http'
            port_suffix = f":{self.config.port}" if self.config.port and self.config.port not in [80, 443] else ""
            self.base_url = f"{protocol}://{self.config.host}{port_suffix}"
            
            # Create requests session
            self.rest_session = requests.Session()
            
            # Configure authentication
            if self.config.username and self.config.password:
                self.rest_session.auth = (self.config.username, self.config.password)
            
            # Configure additional headers
            self.rest_session.headers.update({
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            })
            
            # Test connection with a simple metadata request
            test_url = f"{self.base_url}/sap/opu/odata/sap/ZEI_INTEGRATION_SRV/$metadata"
            
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.rest_session.get(test_url, timeout=self.config.timeout)
            )
            
            if response.status_code == 200:
                self.connected = True
                self.connection_time = time.time() - start_time
                
                logger.info(
                    "Connected to SAP via REST/OData",
                    host=self.config.host,
                    base_url=self.base_url,
                    duration=self.connection_time
                )
                
                return True
            else:
                raise Exception(f"Connection test failed with status {response.status_code}")
            
        except Exception as e:
            logger.error(f"Failed to connect to SAP via REST: {e}")
            self.connected = False
            raise
    
    async def disconnect(self) -> bool:
        """
        Disconnect from SAP system
        """
        try:
            if self.rfc_connection:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self.rfc_connection.close)
                self.rfc_connection = None
            
            self.connected = False
            logger.info("Disconnected from SAP")
            return True
            
        except Exception as e:
            logger.error(f"Error disconnecting from SAP: {e}")
            return False
    
    async def execute(self, function_name: str, params: Dict[str, Any] = None) -> Any:
        """
        Execute RFC function
        
        Args:
            function_name: Name of the RFC function/BAPI
            params: Parameters for the function
        
        Returns:
            Function result
        """
        if not self.connected or not self.rfc_connection:
            raise RuntimeError("Not connected to SAP")
        
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self.rfc_connection.call,
                function_name,
                **(params or {})
            )
            
            logger.debug(f"Executed RFC function: {function_name}")
            return result
            
        except Exception as e:
            logger.error(f"RFC execution failed: {e}", function=function_name)
            raise
    
    async def ping(self) -> bool:
        """
        Check SAP connection status
        """
        try:
            if not self.rfc_connection:
                return False
            
            # Use RFC_PING to check connection
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self.rfc_connection.ping
            )
            return True
            
        except Exception:
            return False
    
    async def call_bapi(
        self,
        bapi_name: str,
        import_params: Dict[str, Any] = None,
        table_params: Dict[str, List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        Call a BAPI function with proper parameter handling
        
        Args:
            bapi_name: BAPI function name
            import_params: Import parameters
            table_params: Table parameters
        
        Returns:
            BAPI result including export parameters and tables
        """
        params = {}
        
        if import_params:
            params.update(import_params)
        
        if table_params:
            params.update(table_params)
        
        result = await self.execute(bapi_name, params)
        
        # Check for BAPI return messages
        if 'RETURN' in result:
            return_messages = result['RETURN']
            if isinstance(return_messages, dict):
                return_messages = [return_messages]
            
            for msg in return_messages:
                if msg.get('TYPE') == 'E':
                    logger.error(f"BAPI error: {msg.get('MESSAGE')}")
                    raise Exception(f"BAPI error: {msg.get('MESSAGE')}")
                elif msg.get('TYPE') == 'W':
                    logger.warning(f"BAPI warning: {msg.get('MESSAGE')}")
        
        return result
    
    async def read_table(
        self,
        table_name: str,
        fields: List[str] = None,
        where_clause: str = None,
        max_rows: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Read SAP table using RFC_READ_TABLE
        
        Args:
            table_name: Name of the SAP table
            fields: List of fields to retrieve (None for all)
            where_clause: WHERE clause for filtering
            max_rows: Maximum number of rows to retrieve
        
        Returns:
            List of table records
        """
        params = {
            'QUERY_TABLE': table_name,
            'DELIMITER': '|',
        }
        
        # Add fields
        if fields:
            params['FIELDS'] = [{'FIELDNAME': f} for f in fields]
        
        # Add WHERE clause
        if where_clause:
            # Split WHERE clause into 72-character chunks (SAP limitation)
            options = []
            for i in range(0, len(where_clause), 72):
                options.append({'TEXT': where_clause[i:i+72]})
            params['OPTIONS'] = options
        
        # Add row limit
        if max_rows > 0:
            params['ROWCOUNT'] = max_rows
        
        result = await self.execute('RFC_READ_TABLE', params)
        
        # Parse the result
        data = result.get('DATA', [])
        fields_info = result.get('FIELDS', [])
        
        # Get field names and positions
        field_names = [f['FIELDNAME'] for f in fields_info]
        
        # Parse data rows
        records = []
        for row in data:
            values = row['WA'].split('|')
            record = {}
            for i, field_name in enumerate(field_names):
                if i < len(values):
                    record[field_name] = values[i].strip()
            records.append(record)
        
        logger.info(f"Read {len(records)} records from table {table_name}")
        return records
    
    async def get_table_metadata(self, table_name: str) -> Dict[str, Any]:
        """
        Get metadata for a SAP table
        
        Args:
            table_name: Name of the SAP table
        
        Returns:
            Table metadata including fields and descriptions
        """
        # Get table description
        desc_params = {
            'TABNAME': table_name,
        }
        
        result = await self.execute('DDIF_TABL_GET', desc_params)
        
        return {
            'table_name': table_name,
            'description': result.get('DD02V_WA', {}).get('DDTEXT', ''),
            'fields': result.get('DD03P_TAB', []),
            'indexes': result.get('DD05M_TAB', []),
        }