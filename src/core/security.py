"""
Security utilities for Turkish Business Integration Platform
"""

import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Union
import secrets
import hashlib

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import redis.asyncio as redis
import structlog

from src.config import settings

logger = structlog.get_logger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# HTTP Bearer scheme for API authentication
security = HTTPBearer()

# Redis client for token blacklisting and storage
redis_client = redis.from_url(settings.redis_url, decode_responses=True)


class SecurityError(Exception):
    """Base security exception"""
    pass


class AuthenticationError(SecurityError):
    """Authentication failed"""
    pass


class AuthorizationError(SecurityError):
    """Authorization failed"""
    pass


class TokenExpiredError(SecurityError):
    """Token has expired"""
    pass


class TokenService:
    """
    JWT token management service for Turkish Business Integration Platform
    
    Handles:
    - Access token creation/verification (short-lived)
    - Refresh token creation/verification (long-lived) 
    - Token blacklisting for logout
    - Turkish user context in tokens
    """
    
    @staticmethod
    def generate_secret_key() -> str:
        """Generate a secure secret key"""
        return secrets.token_hex(32)
    
    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash password using bcrypt
        
        Args:
            password: Plain text password
            
        Returns:
            str: Hashed password
        """
        return pwd_context.hash(password)
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """
        Verify password against hash
        
        Args:
            plain_password: Plain text password
            hashed_password: Bcrypt hash
            
        Returns:
            bool: True if password matches
        """
        return pwd_context.verify(plain_password, hashed_password)
    
    @staticmethod
    async def create_access_token(data: Dict[str, Any]) -> str:
        """
        Create JWT access token (short-lived)
        
        Args:
            data: Token payload data
            
        Returns:
            str: JWT access token
        """
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
        
        to_encode.update({
            "exp": expire,
            "type": "access",
            "iat": datetime.utcnow(),
            "jti": str(uuid.uuid4()),  # JWT ID for blacklisting
        })
        
        # Ensure required fields
        if "sub" not in to_encode:
            raise ValueError("Token must include 'sub' (subject) field")
        if "tenant_id" not in to_encode:
            raise ValueError("Token must include 'tenant_id' field")
        
        token = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
        
        logger.info(
            "Access token created",
            user_id=to_encode.get("sub"),
            tenant_id=to_encode.get("tenant_id"),
            expires_at=expire.isoformat()
        )
        
        return token
    
    @staticmethod
    async def create_refresh_token(data: Dict[str, Any]) -> str:
        """
        Create JWT refresh token (long-lived)
        
        Args:
            data: Token payload data
            
        Returns:
            str: JWT refresh token
        """
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=settings.refresh_token_expire_days)
        
        to_encode.update({
            "exp": expire,
            "type": "refresh",
            "iat": datetime.utcnow(),
            "jti": str(uuid.uuid4()),
        })
        
        token = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
        
        # Store refresh token in Redis with expiration
        await redis_client.setex(
            f"refresh_token:{to_encode['sub']}:{to_encode['jti'][-8:]}",
            settings.refresh_token_expire_days * 86400,
            token
        )
        
        logger.info(
            "Refresh token created",
            user_id=to_encode.get("sub"),
            tenant_id=to_encode.get("tenant_id"),
            expires_at=expire.isoformat()
        )
        
        return token
    
    @staticmethod
    async def verify_token(token: str, token_type: str = "access") -> Dict[str, Any]:
        """
        Verify JWT token and return payload
        
        Args:
            token: JWT token to verify
            token_type: Expected token type (access/refresh)
            
        Returns:
            Dict[str, Any]: Token payload
            
        Raises:
            AuthenticationError: If token is invalid
            TokenExpiredError: If token has expired
        """
        try:
            # Decode token
            payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
            
            # Check token type
            if payload.get("type") != token_type:
                raise AuthenticationError(
                    f"Invalid token type. Expected: {token_type}, got: {payload.get('type')}"
                )
            
            # Check if token is blacklisted
            jti = payload.get("jti")
            if jti and await redis_client.exists(f"blacklist:{jti}"):
                raise AuthenticationError("Token has been revoked")
            
            # Validate required fields
            if not payload.get("sub"):
                raise AuthenticationError("Token missing subject")
            if not payload.get("tenant_id"):
                raise AuthenticationError("Token missing tenant_id")
            
            return payload
            
        except jwt.ExpiredSignatureError:
            raise TokenExpiredError("Token has expired")
        except JWTError as e:
            raise AuthenticationError(f"Token validation failed: {str(e)}")
    
    @staticmethod
    async def refresh_access_token(refresh_token: str) -> Dict[str, str]:
        """
        Create new access token from refresh token
        
        Args:
            refresh_token: Valid refresh token
            
        Returns:
            Dict[str, str]: New access token and refresh token
        """
        # Verify refresh token
        payload = await TokenService.verify_token(refresh_token, "refresh")
        
        # Create new access token
        access_token_data = {
            "sub": payload["sub"],
            "tenant_id": payload["tenant_id"],
            "email": payload.get("email"),
            "name": payload.get("name"),
            "role": payload.get("role")
        }
        
        new_access_token = await TokenService.create_access_token(access_token_data)
        
        # Optionally rotate refresh token for security
        new_refresh_token = await TokenService.create_refresh_token(access_token_data)
        
        # Blacklist old refresh token
        await TokenService.blacklist_token(refresh_token)
        
        return {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer"
        }
    
    @staticmethod
    async def blacklist_token(token: str) -> bool:
        """
        Add token to blacklist (for logout)
        
        Args:
            token: JWT token to blacklist
            
        Returns:
            bool: True if successfully blacklisted
        """
        try:
            payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
            jti = payload.get("jti")
            exp = payload.get("exp")
            
            if jti and exp:
                # Calculate remaining TTL
                ttl = exp - datetime.utcnow().timestamp()
                if ttl > 0:
                    await redis_client.setex(f"blacklist:{jti}", int(ttl), "revoked")
                    
                    logger.info("Token blacklisted", jti=jti, ttl=int(ttl))
                    return True
            
            return False
            
        except JWTError:
            return False
    
    @staticmethod
    async def cleanup_expired_tokens():
        """Clean up expired tokens from Redis (background task)"""
        try:
            # Get all blacklisted tokens
            keys = await redis_client.keys("blacklist:*")
            expired_count = 0
            
            for key in keys:
                ttl = await redis_client.ttl(key)
                if ttl <= 0:
                    await redis_client.delete(key)
                    expired_count += 1
            
            if expired_count > 0:
                logger.info(f"Cleaned up {expired_count} expired tokens")
                
        except Exception as e:
            logger.error("Token cleanup failed", error=str(e))


class PasswordService:
    """Password security utilities"""
    
    @staticmethod
    def generate_password_reset_token(email: str) -> str:
        """Generate secure password reset token"""
        data = f"{email}:{datetime.utcnow().timestamp()}:{secrets.token_hex(16)}"
        return hashlib.sha256(data.encode()).hexdigest()
    
    @staticmethod
    def validate_password_strength(password: str) -> Dict[str, Union[bool, str]]:
        """
        Validate password strength for Turkish users
        
        Args:
            password: Password to validate
            
        Returns:
            Dict with validation result and Turkish message
        """
        if len(password) < 8:
            return {
                "valid": False,
                "message": "Şifre en az 8 karakter olmalıdır",
                "message_en": "Password must be at least 8 characters"
            }
        
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password)
        
        if not (has_upper and has_lower and has_digit and has_special):
            return {
                "valid": False,
                "message": "Şifre büyük harf, küçük harf, rakam ve özel karakter içermelidir",
                "message_en": "Password must contain uppercase, lowercase, digit and special character"
            }
        
        return {
            "valid": True,
            "message": "Şifre güçlü",
            "message_en": "Password is strong"
        }


# Dependency functions for FastAPI
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """
    FastAPI dependency to get current authenticated user
    
    Args:
        credentials: HTTP Bearer token
        
    Returns:
        Dict[str, Any]: Current user data
        
    Raises:
        HTTPException: If authentication fails
    """
    try:
        token = credentials.credentials
        payload = await TokenService.verify_token(token, "access")
        return payload
        
    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "token_expired",
                "message": "Oturum süresi doldu",
                "message_en": "Token has expired"
            },
            headers={"WWW-Authenticate": "Bearer"},
        )
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "invalid_token",
                "message": "Geçersiz token",
                "message_en": str(e)
            },
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_active_user(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """
    FastAPI dependency to get current active user
    
    Args:
        current_user: Current user from get_current_user
        
    Returns:
        Dict[str, Any]: Current active user data
        
    Raises:
        HTTPException: If user is not active
    """
    if current_user.get("is_active") is False:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "user_inactive",
                "message": "Kullanıcı hesabı devre dışı",
                "message_en": "User account is inactive"
            }
        )
    
    return current_user


def require_permissions(required_permissions: list):
    """
    Decorator to require specific permissions
    
    Args:
        required_permissions: List of required permission strings
    """
    def permission_checker(current_user: Dict[str, Any] = Depends(get_current_active_user)):
        user_permissions = current_user.get("permissions", [])
        
        for permission in required_permissions:
            if permission not in user_permissions:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "error": "insufficient_permissions",
                        "message": f"'{permission}' yetkisi gerekli",
                        "message_en": f"Permission '{permission}' required",
                        "required_permissions": required_permissions,
                        "user_permissions": user_permissions
                    }
                )
        
        return current_user
    
    return permission_checker