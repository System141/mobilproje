"""
SAP REST/OData Connector
Provides SAP connectivity using standard HTTP/REST APIs and OData services
"""

import asyncio
import json
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode, quote
import time
import xml.etree.ElementTree as ET

try:
    import requests
    from requests.auth import HTTPBasicAuth
    from requests_oauthlib import OAuth2Session
    REST_AVAILABLE = True
except ImportError:
    REST_AVAILABLE = False

from erp_platform.connectors.base import BaseConnector, ConnectionConfig
from erp_platform.core.logging import get_logger

logger = get_logger(__name__)


class SAPRestConnector(BaseConnector):
    """
    SAP connector using REST/OData APIs
    Provides an alternative to PyRFC when SAP NetWeaver RFC SDK is not available
    """
    
    def __init__(self, config: ConnectionConfig):
        super().__init__(config)
        
        if not REST_AVAILABLE:
            raise ImportError(
                "REST dependencies not available. Please install: "
                "pip install requests requests-oauthlib"
            )
        
        self.session = None
        self.base_url = None
        self.odata_services = {}
        self.csrf_token = None
        
    async def connect(self) -> bool:
        """
        Connect to SAP system via REST/OData
        """
        try:
            start_time = time.time()
            
            # Build base URL
            protocol = 'https' if self.config.port == 443 else 'http'
            port_suffix = f":{self.config.port}" if self.config.port and self.config.port not in [80, 443] else ""
            self.base_url = f"{protocol}://{self.config.host}{port_suffix}"
            
            # Create session
            self.session = requests.Session()
            
            # Configure authentication
            if self.config.username and self.config.password:
                self.session.auth = HTTPBasicAuth(self.config.username, self.config.password)
            
            # Configure headers
            self.session.headers.update({
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            })
            
            # Test connection and discover services
            await self._discover_services()
            
            # Fetch CSRF token if needed
            await self._fetch_csrf_token()
            
            self.connected = True
            self.connection_time = time.time() - start_time
            
            logger.info(
                "Connected to SAP via REST/OData",
                host=self.config.host,
                services_count=len(self.odata_services),
                duration=self.connection_time
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to SAP via REST: {e}")
            self.connected = False
            raise
    
    async def disconnect(self) -> bool:
        """
        Disconnect from SAP system
        """
        try:
            if self.session:
                self.session.close()
                self.session = None
            
            self.connected = False
            self.odata_services = {}
            self.csrf_token = None
            
            logger.info("Disconnected from SAP REST")
            return True
            
        except Exception as e:
            logger.error(f"Error disconnecting from SAP REST: {e}")
            return False
    
    async def execute(self, operation: str, params: Dict[str, Any] = None) -> Any:
        """
        Execute a REST/OData operation
        
        Args:
            operation: The operation type (read_entity, read_collection, etc.)
            params: Operation parameters
        
        Returns:
            Operation result
        """
        if not self.connected or not self.session:
            raise RuntimeError("Not connected to SAP")
        
        params = params or {}
        
        if operation == "read_entity":
            return await self._read_entity(params)
        elif operation == "read_collection":
            return await self._read_collection(params)
        elif operation == "create_entity":
            return await self._create_entity(params)
        elif operation == "update_entity":
            return await self._update_entity(params)
        elif operation == "delete_entity":
            return await self._delete_entity(params)
        elif operation == "call_function":
            return await self._call_function(params)
        else:
            raise ValueError(f"Unsupported operation: {operation}")
    
    async def ping(self) -> bool:
        """
        Check SAP connection status
        """
        try:
            if not self.session:
                return False
            
            # Simple metadata request to test connectivity
            url = f"{self.base_url}/sap/opu/odata/sap/"
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.session.get(url, timeout=10)
            )
            return response.status_code == 200
            
        except Exception:
            return False
    
    async def _discover_services(self):
        """
        Discover available OData services
        """
        try:
            url = f"{self.base_url}/sap/opu/odata/IWFND/CATALOGSERVICE;v=2/ServiceCollection"
            
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.session.get(url, timeout=self.config.timeout)
            )
            
            if response.status_code == 200:
                data = response.json()
                if 'd' in data and 'results' in data['d']:
                    for service in data['d']['results']:
                        service_id = service.get('ID', '')
                        service_title = service.get('Title', '')
                        service_url = service.get('TechnicalServiceName', '')
                        
                        self.odata_services[service_id] = {
                            'title': service_title,
                            'url': service_url,
                            'metadata_url': f"{self.base_url}/sap/opu/odata/sap/{service_url}/$metadata"
                        }
                
                logger.info(f"Discovered {len(self.odata_services)} OData services")
            
        except Exception as e:
            logger.warning(f"Could not discover OData services: {e}")
    
    async def _fetch_csrf_token(self):
        """
        Fetch CSRF token for write operations
        """
        try:
            # Use a simple service to get CSRF token
            url = f"{self.base_url}/sap/opu/odata/sap/ZEI_INTEGRATION_SRV/"
            headers = {'X-CSRF-Token': 'Fetch'}
            
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.session.get(url, headers=headers, timeout=self.config.timeout)
            )
            
            if 'x-csrf-token' in response.headers:
                self.csrf_token = response.headers['x-csrf-token']
                self.session.headers.update({'X-CSRF-Token': self.csrf_token})
                logger.debug("CSRF token obtained")
            
        except Exception as e:
            logger.warning(f"Could not fetch CSRF token: {e}")
    
    async def _read_entity(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Read a single entity
        """
        service = params.get('service')
        entity_set = params.get('entity_set')
        entity_key = params.get('entity_key')
        select_fields = params.get('select')
        expand_fields = params.get('expand')
        
        if not all([service, entity_set, entity_key]):
            raise ValueError("service, entity_set, and entity_key are required")
        
        # Build URL
        url = f"{self.base_url}/sap/opu/odata/sap/{service}/{entity_set}({entity_key})"
        
        # Add query parameters
        query_params = {}
        if select_fields:
            query_params['$select'] = ','.join(select_fields)
        if expand_fields:
            query_params['$expand'] = ','.join(expand_fields)
        
        if query_params:
            url += '?' + urlencode(query_params)
        
        # Execute request
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.session.get(url, timeout=self.config.timeout)
        )
        
        if response.status_code == 200:
            data = response.json()
            return data.get('d', data)
        else:
            raise Exception(f"Read entity failed: {response.status_code} {response.text}")
    
    async def _read_collection(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Read a collection of entities
        """
        service = params.get('service')
        entity_set = params.get('entity_set')
        filter_condition = params.get('filter')
        select_fields = params.get('select')
        order_by = params.get('orderby')
        top = params.get('top')
        skip = params.get('skip')
        
        if not all([service, entity_set]):
            raise ValueError("service and entity_set are required")
        
        # Build URL
        url = f"{self.base_url}/sap/opu/odata/sap/{service}/{entity_set}"
        
        # Add query parameters
        query_params = {}
        if filter_condition:
            query_params['$filter'] = filter_condition
        if select_fields:
            query_params['$select'] = ','.join(select_fields)
        if order_by:
            query_params['$orderby'] = order_by
        if top:
            query_params['$top'] = str(top)
        if skip:
            query_params['$skip'] = str(skip)
        
        if query_params:
            url += '?' + urlencode(query_params)
        
        # Execute request
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.session.get(url, timeout=self.config.timeout)
        )
        
        if response.status_code == 200:
            data = response.json()
            if 'd' in data and 'results' in data['d']:
                return data['d']['results']
            elif 'd' in data:
                return [data['d']]
            else:
                return [data]
        else:
            raise Exception(f"Read collection failed: {response.status_code} {response.text}")
    
    async def _create_entity(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new entity
        """
        service = params.get('service')
        entity_set = params.get('entity_set')
        entity_data = params.get('data')
        
        if not all([service, entity_set, entity_data]):
            raise ValueError("service, entity_set, and data are required")
        
        # Build URL
        url = f"{self.base_url}/sap/opu/odata/sap/{service}/{entity_set}"
        
        # Execute request
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.session.post(
                url,
                json=entity_data,
                timeout=self.config.timeout
            )
        )
        
        if response.status_code in [200, 201]:
            data = response.json()
            return data.get('d', data)
        else:
            raise Exception(f"Create entity failed: {response.status_code} {response.text}")
    
    async def _update_entity(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an existing entity
        """
        service = params.get('service')
        entity_set = params.get('entity_set')
        entity_key = params.get('entity_key')
        entity_data = params.get('data')
        
        if not all([service, entity_set, entity_key, entity_data]):
            raise ValueError("service, entity_set, entity_key, and data are required")
        
        # Build URL
        url = f"{self.base_url}/sap/opu/odata/sap/{service}/{entity_set}({entity_key})"
        
        # Execute request
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.session.put(
                url,
                json=entity_data,
                timeout=self.config.timeout
            )
        )
        
        if response.status_code in [200, 204]:
            return {"status": "updated"}
        else:
            raise Exception(f"Update entity failed: {response.status_code} {response.text}")
    
    async def _delete_entity(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Delete an entity
        """
        service = params.get('service')
        entity_set = params.get('entity_set')
        entity_key = params.get('entity_key')
        
        if not all([service, entity_set, entity_key]):
            raise ValueError("service, entity_set, and entity_key are required")
        
        # Build URL
        url = f"{self.base_url}/sap/opu/odata/sap/{service}/{entity_set}({entity_key})"
        
        # Execute request
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.session.delete(url, timeout=self.config.timeout)
        )
        
        if response.status_code in [200, 204]:
            return {"status": "deleted"}
        else:
            raise Exception(f"Delete entity failed: {response.status_code} {response.text}")
    
    async def _call_function(self, params: Dict[str, Any]) -> Any:
        """
        Call an OData function import
        """
        service = params.get('service')
        function_name = params.get('function')
        function_params = params.get('params', {})
        
        if not all([service, function_name]):
            raise ValueError("service and function are required")
        
        # Build URL with function parameters
        param_string = '&'.join([f"{k}='{v}'" for k, v in function_params.items()])
        url = f"{self.base_url}/sap/opu/odata/sap/{service}/{function_name}"
        if param_string:
            url += f"?{param_string}"
        
        # Execute request
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.session.post(url, timeout=self.config.timeout)
        )
        
        if response.status_code == 200:
            data = response.json()
            return data.get('d', data)
        else:
            raise Exception(f"Function call failed: {response.status_code} {response.text}")
    
    async def get_service_metadata(self, service_name: str) -> Dict[str, Any]:
        """
        Get metadata for a specific OData service
        """
        url = f"{self.base_url}/sap/opu/odata/sap/{service_name}/$metadata"
        
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.session.get(url, timeout=self.config.timeout)
        )
        
        if response.status_code == 200:
            # Parse XML metadata
            root = ET.fromstring(response.text)
            
            # Extract entity sets and types
            entity_sets = []
            entity_types = []
            
            # Navigate XML namespaces
            namespaces = {
                'edmx': 'http://schemas.microsoft.com/ado/2007/06/edmx',
                'edm': 'http://schemas.microsoft.com/ado/2008/09/edm'
            }
            
            # Find entity sets
            for entity_set in root.findall('.//edm:EntitySet', namespaces):
                entity_sets.append({
                    'name': entity_set.get('Name'),
                    'entity_type': entity_set.get('EntityType')
                })
            
            # Find entity types
            for entity_type in root.findall('.//edm:EntityType', namespaces):
                properties = []
                for prop in entity_type.findall('.//edm:Property', namespaces):
                    properties.append({
                        'name': prop.get('Name'),
                        'type': prop.get('Type'),
                        'nullable': prop.get('Nullable', 'true') == 'true'
                    })
                
                entity_types.append({
                    'name': entity_type.get('Name'),
                    'properties': properties
                })
            
            return {
                'service_name': service_name,
                'entity_sets': entity_sets,
                'entity_types': entity_types
            }
        else:
            raise Exception(f"Metadata request failed: {response.status_code}")
    
    def get_available_services(self) -> Dict[str, Any]:
        """
        Get list of available OData services
        """
        return self.odata_services