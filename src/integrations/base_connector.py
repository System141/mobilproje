"""
Base connector for Turkish Business Integration Platform
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from datetime import datetime

import httpx
from pydantic import BaseModel, Field
import structlog

logger = structlog.get_logger(__name__)


class ConnectorConfig(BaseModel):
    """Base configuration for all connectors"""
    
    # Authentication
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    access_token: Optional[str] = None
    
    # Connection settings
    base_url: str
    timeout: int = Field(default=30, ge=5, le=300)
    retry_count: int = Field(default=3, ge=0, le=10)
    retry_delay: float = Field(default=1.0, ge=0.1, le=60.0)
    
    # Request settings
    user_agent: str = "TurkishIntegrationPlatform/1.0"
    headers: Dict[str, str] = Field(default_factory=dict)
    
    # Features
    webhook_url: Optional[str] = None
    enable_logging: bool = True
    enable_metrics: bool = True
    
    class Config:
        extra = "forbid"


class ConnectorResponse(BaseModel):
    """Standard response format for all connectors"""
    
    success: bool
    status_code: Optional[int] = None
    data: Any = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    request_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Turkish localized messages
    message_tr: Optional[str] = None
    message_en: Optional[str] = None


class ConnectorError(Exception):
    """Base exception for connector errors"""
    
    def __init__(
        self, 
        message: str, 
        error_code: str = "CONNECTOR_ERROR",
        status_code: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class AuthenticationError(ConnectorError):
    """Authentication failed"""
    
    def __init__(self, message: str = "Kimlik doğrulama hatası"):
        super().__init__(
            message=message,
            error_code="AUTHENTICATION_ERROR",
            status_code=401
        )


class RateLimitError(ConnectorError):
    """Rate limit exceeded"""
    
    def __init__(self, message: str = "Rate limit aşıldı", retry_after: Optional[int] = None):
        super().__init__(
            message=message,
            error_code="RATE_LIMIT_ERROR",
            status_code=429,
            details={"retry_after": retry_after}
        )


class BaseConnector(ABC):
    """
    Base class for all Turkish business system connectors
    
    Provides common functionality for:
    - HTTP requests with retry logic
    - Error handling and logging
    - Authentication management
    - Rate limiting
    - Metrics collection
    """
    
    def __init__(self, config: ConnectorConfig):
        self.config = config
        self.name = self.__class__.__name__
        self.client: Optional[httpx.AsyncClient] = None
        self._authenticated = False
        self._auth_expires_at: Optional[datetime] = None
        self._request_count = 0
        self._error_count = 0
        
        # Setup logging
        self.logger = structlog.get_logger(f"connector.{self.name.lower()}")
        
        if config.enable_logging:
            self.logger = self.logger.bind(connector=self.name)
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self._initialize_client()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self._close_client()
    
    async def _initialize_client(self):
        """Initialize HTTP client with proper configuration"""
        headers = {
            "User-Agent": self.config.user_agent,
            **self.config.headers
        }
        
        self.client = httpx.AsyncClient(
            base_url=self.config.base_url,
            timeout=self.config.timeout,
            headers=headers,
            follow_redirects=True
        )
        
        self.logger.info("HTTP client initialized", base_url=self.config.base_url)
    
    async def _close_client(self):
        """Close HTTP client"""
        if self.client:
            await self.client.aclose()
            self.client = None
            self.logger.info("HTTP client closed")
    
    @abstractmethod
    async def authenticate(self) -> bool:
        """
        Authenticate with the service
        
        Returns:
            bool: True if authentication successful
        """
        pass
    
    @abstractmethod
    async def test_connection(self) -> ConnectorResponse:
        """
        Test if connection is working
        
        Returns:
            ConnectorResponse: Test result
        """
        pass
    
    @abstractmethod
    def get_available_actions(self) -> List[str]:
        """
        Return list of supported actions
        
        Returns:
            List[str]: Available actions
        """
        pass
    
    @abstractmethod
    async def execute_action(self, action: str, payload: Dict[str, Any]) -> ConnectorResponse:
        """
        Execute a specific action
        
        Args:
            action: Action name
            payload: Action parameters
            
        Returns:
            ConnectorResponse: Action result
        """
        pass
    
    async def ensure_authenticated(self):
        """Ensure connector is authenticated"""
        if not self._authenticated or self._is_auth_expired():
            success = await self.authenticate()
            if not success:
                raise AuthenticationError("Kimlik doğrulama başarısız")
    
    def _is_auth_expired(self) -> bool:
        """Check if authentication has expired"""
        if not self._auth_expires_at:
            return False
        return datetime.utcnow() >= self._auth_expires_at
    
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        auth_required: bool = True
    ) -> ConnectorResponse:
        """
        Make HTTP request with retry logic and error handling
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            data: Form data
            json: JSON data
            params: Query parameters
            headers: Additional headers
            auth_required: Whether authentication is required
            
        Returns:
            ConnectorResponse: Request result
        """
        if not self.client:
            await self._initialize_client()
        
        if auth_required:
            await self.ensure_authenticated()
        
        # Prepare request
        request_headers = headers or {}
        
        # Retry logic
        for attempt in range(self.config.retry_count + 1):
            try:
                self.logger.debug(
                    "Making request",
                    method=method,
                    endpoint=endpoint,
                    attempt=attempt + 1
                )
                
                response = await self.client.request(
                    method=method,
                    url=endpoint,
                    data=data,
                    json=json,
                    params=params,
                    headers=request_headers
                )
                
                self._request_count += 1
                
                # Handle response
                return await self._handle_response(response)
                
            except httpx.TimeoutException as e:
                self._error_count += 1
                if attempt == self.config.retry_count:
                    self.logger.error("Request timeout", endpoint=endpoint, error=str(e))
                    return ConnectorResponse(
                        success=False,
                        error="Request timeout",
                        error_code="TIMEOUT_ERROR",
                        message_tr="İstek zaman aşımına uğradı",
                        message_en="Request timed out"
                    )
                
                await asyncio.sleep(self.config.retry_delay * (attempt + 1))
                
            except httpx.RequestError as e:
                self._error_count += 1
                if attempt == self.config.retry_count:
                    self.logger.error("Request error", endpoint=endpoint, error=str(e))
                    return ConnectorResponse(
                        success=False,
                        error=str(e),
                        error_code="REQUEST_ERROR",
                        message_tr="İstek hatası",
                        message_en="Request error"
                    )
                
                await asyncio.sleep(self.config.retry_delay * (attempt + 1))
            
            except Exception as e:
                self._error_count += 1
                self.logger.error("Unexpected error", endpoint=endpoint, error=str(e))
                return ConnectorResponse(
                    success=False,
                    error=str(e),
                    error_code="UNEXPECTED_ERROR",
                    message_tr="Beklenmeyen hata",
                    message_en="Unexpected error"
                )
        
        return ConnectorResponse(
            success=False,
            error="Max retries exceeded",
            error_code="MAX_RETRIES_ERROR",
            message_tr="Maksimum deneme sayısı aşıldı",
            message_en="Maximum retries exceeded"
        )
    
    async def _handle_response(self, response: httpx.Response) -> ConnectorResponse:
        """
        Handle HTTP response and convert to ConnectorResponse
        
        Args:
            response: HTTP response
            
        Returns:
            ConnectorResponse: Processed response
        """
        # Log response
        self.logger.debug(
            "Response received",
            status_code=response.status_code,
            content_type=response.headers.get("content-type")
        )
        
        # Handle different status codes
        if response.status_code == 401:
            self._authenticated = False
            raise AuthenticationError()
        
        elif response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            raise RateLimitError(
                retry_after=int(retry_after) if retry_after else None
            )
        
        elif response.status_code >= 400:
            error_data = {}
            try:
                error_data = response.json()
            except:
                pass
            
            return ConnectorResponse(
                success=False,
                status_code=response.status_code,
                error=error_data.get("message", response.reason_phrase),
                error_code=f"HTTP_{response.status_code}",
                data=error_data,
                message_tr=error_data.get("message_tr", "İstek başarısız"),
                message_en=error_data.get("message_en", "Request failed")
            )
        
        # Handle successful responses
        try:
            data = response.json()
        except:
            data = response.text
        
        return ConnectorResponse(
            success=True,
            status_code=response.status_code,
            data=data
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get connector statistics"""
        return {
            "name": self.name,
            "authenticated": self._authenticated,
            "request_count": self._request_count,
            "error_count": self._error_count,
            "success_rate": (
                (self._request_count - self._error_count) / max(self._request_count, 1)
            ) * 100,
            "config": {
                "base_url": self.config.base_url,
                "timeout": self.config.timeout,
                "retry_count": self.config.retry_count
            }
        }
    
    def reset_stats(self):
        """Reset connector statistics"""
        self._request_count = 0
        self._error_count = 0