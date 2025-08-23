"""
Multi-tenant middleware and context management for Turkish Business Integration Platform
"""

import uuid
from contextvars import ContextVar
from typing import Optional, Dict, Any

from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import structlog

logger = structlog.get_logger(__name__)

# Global tenant context variable
tenant_context: ContextVar[Optional[str]] = ContextVar("tenant_context", default=None)

# Tenant information context
tenant_info_context: ContextVar[Optional[Dict[str, Any]]] = ContextVar(
    "tenant_info_context", default=None
)


class TenantMiddleware(BaseHTTPMiddleware):
    """
    Middleware to extract and validate tenant information from requests
    
    Tenant can be identified through:
    1. Subdomain (tenant.yourdomain.com)
    2. X-Tenant-ID header
    3. Authorization token claims
    """
    
    EXCLUDED_PATHS = [
        "/health",
        "/metrics",
        "/docs",
        "/openapi.json",
        "/redoc",
        "/favicon.ico",
        "/api/v1/auth/register-tenant",
        "/api/v1/system",
    ]
    
    def __init__(self, app):
        super().__init__(app)
        self.tenant_service = None  # Will be injected during startup
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Process request and extract tenant information
        
        Args:
            request: FastAPI request object
            call_next: Next middleware in chain
            
        Returns:
            Response: HTTP response
        """
        # Skip tenant extraction for excluded paths
        if self._is_excluded_path(request.url.path):
            return await call_next(request)
        
        try:
            # Extract tenant information
            tenant_id = await self._extract_tenant_id(request)
            tenant_info = await self._get_tenant_info(tenant_id) if tenant_id else None
            
            # Validate tenant
            if not tenant_id or not tenant_info:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": "tenant_required",
                        "message": "Tenant bilgisi gerekli",
                        "message_en": "Tenant information is required"
                    }
                )
            
            # Check if tenant is active
            if not tenant_info.get("is_active", False):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "error": "tenant_inactive",
                        "message": "Tenant hesabı devre dışı",
                        "message_en": "Tenant account is inactive"
                    }
                )
            
            # Set tenant context
            tenant_context.set(tenant_id)
            tenant_info_context.set(tenant_info)
            
            # Add tenant info to request state
            request.state.tenant_id = tenant_id
            request.state.tenant_info = tenant_info
            
            # Add structured logging context
            structlog.contextvars.bind_contextvars(
                tenant_id=tenant_id,
                tenant_name=tenant_info.get("name"),
                tenant_plan=tenant_info.get("plan")
            )
            
            response = await call_next(request)
            
            # Add tenant info to response headers (for debugging)
            if tenant_info.get("debug_headers", False):
                response.headers["X-Tenant-ID"] = tenant_id
                response.headers["X-Tenant-Name"] = tenant_info.get("name", "")
            
            return response
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(
                "Tenant middleware error",
                error=str(e),
                path=request.url.path,
                method=request.method
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "tenant_processing_error",
                    "message": "Tenant işleme hatası",
                    "message_en": "Tenant processing error"
                }
            )
        finally:
            # Clear context
            tenant_context.set(None)
            tenant_info_context.set(None)
            structlog.contextvars.clear_contextvars()
    
    def _is_excluded_path(self, path: str) -> bool:
        """Check if path should be excluded from tenant processing"""
        return any(path.startswith(excluded) for excluded in self.EXCLUDED_PATHS)
    
    async def _extract_tenant_id(self, request: Request) -> Optional[str]:
        """
        Extract tenant ID from request
        
        Args:
            request: FastAPI request object
            
        Returns:
            Optional[str]: Tenant ID if found
        """
        # Method 1: Check X-Tenant-ID header
        tenant_id = request.headers.get("X-Tenant-ID")
        if tenant_id:
            return self._validate_tenant_id(tenant_id)
        
        # Method 2: Extract from subdomain
        host = request.headers.get("host", "")
        if "." in host:
            subdomain = host.split(".")[0]
            if subdomain and subdomain not in ["www", "api", "admin"]:
                # Convert subdomain to tenant ID (this would typically be a database lookup)
                return await self._subdomain_to_tenant_id(subdomain)
        
        # Method 3: Extract from Authorization token
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]
            return await self._extract_tenant_from_token(token)
        
        return None
    
    def _validate_tenant_id(self, tenant_id: str) -> Optional[str]:
        """Validate tenant ID format"""
        try:
            # Ensure it's a valid UUID
            uuid.UUID(tenant_id)
            return tenant_id
        except ValueError:
            return None
    
    async def _subdomain_to_tenant_id(self, subdomain: str) -> Optional[str]:
        """
        Convert subdomain to tenant ID
        
        This would typically involve a database lookup
        For now, we'll use a simple mapping
        """
        if self.tenant_service:
            return await self.tenant_service.get_tenant_id_by_subdomain(subdomain)
        return None
    
    async def _extract_tenant_from_token(self, token: str) -> Optional[str]:
        """Extract tenant ID from JWT token claims"""
        try:
            from src.core.security import TokenService
            payload = await TokenService.verify_token(token)
            return payload.get("tenant_id")
        except Exception:
            return None
    
    async def _get_tenant_info(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """
        Get tenant information from database
        
        Args:
            tenant_id: Tenant ID
            
        Returns:
            Optional[Dict[str, Any]]: Tenant information
        """
        if not self.tenant_service:
            # Fallback for testing - assume tenant is valid
            return {
                "id": tenant_id,
                "name": "Test Tenant",
                "subdomain": "test",
                "is_active": True,
                "plan": "trial",
                "settings": {},
                "features": []
            }
        
        return await self.tenant_service.get_tenant_info(tenant_id)


def get_current_tenant_id() -> str:
    """
    Get current tenant ID from context
    
    Returns:
        str: Current tenant ID
        
    Raises:
        HTTPException: If no tenant context is set
    """
    tenant_id = tenant_context.get()
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "no_tenant_context",
                "message": "Tenant bağlamı bulunamadı",
                "message_en": "No tenant context found"
            }
        )
    return tenant_id


def get_current_tenant_info() -> Dict[str, Any]:
    """
    Get current tenant information from context
    
    Returns:
        Dict[str, Any]: Current tenant information
        
    Raises:
        HTTPException: If no tenant context is set
    """
    tenant_info = tenant_info_context.get()
    if not tenant_info:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "no_tenant_info",
                "message": "Tenant bilgisi bulunamadı",
                "message_en": "No tenant information found"
            }
        )
    return tenant_info


def require_tenant_feature(feature: str):
    """
    Decorator to require specific tenant feature
    
    Args:
        feature: Required feature name
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            tenant_info = get_current_tenant_info()
            features = tenant_info.get("features", [])
            
            if feature not in features:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "error": "feature_not_available",
                        "message": f"{feature} özelliği bu planda mevcut değil",
                        "message_en": f"{feature} feature is not available in this plan",
                        "required_feature": feature
                    }
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def require_tenant_plan(min_plan: str):
    """
    Decorator to require minimum tenant plan
    
    Args:
        min_plan: Minimum required plan (trial, starter, professional, enterprise)
    """
    PLAN_HIERARCHY = {
        "trial": 0,
        "starter": 1, 
        "professional": 2,
        "enterprise": 3
    }
    
    def decorator(func):
        async def wrapper(*args, **kwargs):
            tenant_info = get_current_tenant_info()
            current_plan = tenant_info.get("plan", "trial")
            
            current_level = PLAN_HIERARCHY.get(current_plan, 0)
            required_level = PLAN_HIERARCHY.get(min_plan, 0)
            
            if current_level < required_level:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "error": "plan_upgrade_required",
                        "message": f"Bu özellik için {min_plan} planı gerekli",
                        "message_en": f"{min_plan} plan required for this feature",
                        "current_plan": current_plan,
                        "required_plan": min_plan
                    }
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator