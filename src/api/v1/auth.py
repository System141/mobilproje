"""
Authentication endpoints for Turkish Business Integration Platform
"""

from datetime import datetime, timedelta
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, Field, validator
import structlog

from src.core.security import (
    TokenService, 
    PasswordService, 
    AuthenticationError, 
    TokenExpiredError,
    get_current_user,
    get_current_active_user
)
from src.services.tenant_service import tenant_service
from src.services.kvkk_service import kvkk_service, ConsentRequest
from src.models.tenant import User

logger = structlog.get_logger(__name__)
security = HTTPBearer()

router = APIRouter()


class LoginRequest(BaseModel):
    """Login request model"""
    email: EmailStr
    password: str = Field(..., min_length=1)
    remember_me: bool = False
    
    
class LoginResponse(BaseModel):
    """Login response model"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: Dict[str, Any]
    tenant: Dict[str, Any]
    

class RefreshTokenRequest(BaseModel):
    """Refresh token request model"""
    refresh_token: str
    

class RegisterRequest(BaseModel):
    """User registration request"""
    email: EmailStr
    password: str = Field(..., min_length=8)
    first_name: str = Field(..., min_length=2, max_length=50)
    last_name: str = Field(..., min_length=2, max_length=50)
    phone: str = Field(..., regex=r'^\+90[0-9]{10}$')
    
    # Tenant information
    company_name: str = Field(..., min_length=2, max_length=100)
    tax_number: str = Field(..., regex=r'^[0-9]{10}$')
    
    # KVKK consent
    marketing_consent: bool = False
    analytics_consent: bool = False
    
    @validator('password')
    def validate_password(cls, v):
        result = PasswordService.validate_password_strength(v)
        if not result['valid']:
            raise ValueError(result['message_en'])
        return v


class PasswordChangeRequest(BaseModel):
    """Password change request"""
    current_password: str
    new_password: str = Field(..., min_length=8)
    
    @validator('new_password')
    def validate_password(cls, v):
        result = PasswordService.validate_password_strength(v)
        if not result['valid']:
            raise ValueError(result['message_en'])
        return v


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, http_request: Request):
    """
    Authenticate user and return JWT tokens
    """
    try:
        # Authenticate user via tenant service
        auth_result = await tenant_service.authenticate_user(
            email=request.email,
            password=request.password
        )
        
        if not auth_result["success"]:
            logger.warning(
                "Login failed",
                email=request.email,
                ip_address=http_request.client.host
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error": "invalid_credentials",
                    "message": "E-posta veya şifre hatalı",
                    "message_en": "Invalid email or password"
                }
            )
        
        user_data = auth_result["user"]
        tenant_data = auth_result["tenant"]
        
        # Check if user is active
        if not user_data.get("is_active"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "user_inactive",
                    "message": "Kullanıcı hesabı devre dışı",
                    "message_en": "User account is inactive"
                }
            )
        
        # Check if tenant is active
        if not tenant_data.get("is_active"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "tenant_inactive",
                    "message": "Şirket hesabı devre dışı",
                    "message_en": "Company account is inactive"
                }
            )
        
        # Create token payload
        token_data = {
            "sub": user_data["id"],
            "tenant_id": tenant_data["id"],
            "email": user_data["email"],
            "name": f"{user_data['first_name']} {user_data['last_name']}",
            "role": user_data["role"],
            "permissions": user_data.get("permissions", []),
            "is_active": user_data["is_active"]
        }
        
        # Generate tokens
        access_token = await TokenService.create_access_token(token_data)
        refresh_token = await TokenService.create_refresh_token(token_data)
        
        logger.info(
            "User logged in",
            user_id=user_data["id"],
            tenant_id=tenant_data["id"],
            email=user_data["email"],
            ip_address=http_request.client.host
        )
        
        return LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=1800,  # 30 minutes
            user=user_data,
            tenant=tenant_data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Login error", error=str(e), email=request.email)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "login_error",
                "message": "Giriş işlemi sırasında hata oluştu",
                "message_en": "An error occurred during login"
            }
        )


@router.post("/register")
async def register(request: RegisterRequest, http_request: Request):
    """
    Register new user and tenant
    """
    try:
        # Create tenant and user
        result = await tenant_service.create_tenant(
            company_name=request.company_name,
            tax_number=request.tax_number,
            admin_email=request.email,
            admin_password=request.password,
            admin_first_name=request.first_name,
            admin_last_name=request.last_name,
            admin_phone=request.phone
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "registration_failed",
                    "message": result.get("message", "Kayıt işlemi başarısız"),
                    "message_en": result.get("message_en", "Registration failed")
                }
            )
        
        tenant_id = result["tenant_id"]
        user_id = result["user_id"]
        
        # Record KVKK consents if given
        if request.marketing_consent:
            marketing_consent = ConsentRequest(
                data_subject_id=user_id,
                purpose="marketing",
                legal_basis="explicit_consent",
                data_categories=["contact_info", "preferences"],
                consent_text="E-posta ve SMS ile pazarlama mesajları almayı kabul ediyorum",
                retention_period="until_withdrawal",
                ip_address=http_request.client.host,
                user_agent=http_request.headers.get("User-Agent")
            )
            
            await kvkk_service.record_consent(tenant_id, marketing_consent)
        
        if request.analytics_consent:
            analytics_consent = ConsentRequest(
                data_subject_id=user_id,
                purpose="analytics",
                legal_basis="explicit_consent",
                data_categories=["usage_data", "behavioral_data"],
                consent_text="Hizmet iyileştirme amaçlı analitik verilerimin işlenmesini kabul ediyorum",
                retention_period="2 years",
                expires_at=datetime.utcnow() + timedelta(days=730),
                ip_address=http_request.client.host,
                user_agent=http_request.headers.get("User-Agent")
            )
            
            await kvkk_service.record_consent(tenant_id, analytics_consent)
        
        logger.info(
            "User registered",
            user_id=str(user_id),
            tenant_id=str(tenant_id),
            email=request.email,
            company_name=request.company_name
        )
        
        return {
            "success": True,
            "message": "Kayıt işlemi başarılı",
            "message_en": "Registration successful",
            "tenant_id": str(tenant_id),
            "user_id": str(user_id)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Registration error", error=str(e), email=request.email)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "registration_error",
                "message": "Kayıt işlemi sırasında hata oluştu",
                "message_en": "An error occurred during registration"
            }
        )


@router.post("/refresh", response_model=Dict[str, str])
async def refresh_token(request: RefreshTokenRequest):
    """
    Refresh access token using refresh token
    """
    try:
        result = await TokenService.refresh_access_token(request.refresh_token)
        
        logger.info("Token refreshed")
        
        return result
        
    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "token_expired",
                "message": "Refresh token süresi doldu",
                "message_en": "Refresh token has expired"
            }
        )
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "invalid_token",
                "message": "Geçersiz refresh token",
                "message_en": str(e)
            }
        )
    except Exception as e:
        logger.error("Token refresh error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "token_refresh_error",
                "message": "Token yenileme sırasında hata oluştu",
                "message_en": "An error occurred during token refresh"
            }
        )


@router.post("/logout")
async def logout(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Logout user by blacklisting current token
    """
    try:
        token = credentials.credentials
        success = await TokenService.blacklist_token(token)
        
        if success:
            logger.info("User logged out")
            return {
                "success": True,
                "message": "Başarıyla çıkış yapıldı",
                "message_en": "Logged out successfully"
            }
        else:
            return {
                "success": False,
                "message": "Çıkış işlemi başarısız",
                "message_en": "Logout failed"
            }
            
    except Exception as e:
        logger.error("Logout error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "logout_error",
                "message": "Çıkış işlemi sırasında hata oluştu",
                "message_en": "An error occurred during logout"
            }
        )


@router.get("/me")
async def get_current_user_info(current_user: Dict[str, Any] = Depends(get_current_active_user)):
    """
    Get current user information
    """
    return {
        "success": True,
        "user": current_user
    }


@router.post("/change-password")
async def change_password(
    request: PasswordChangeRequest,
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """
    Change user password
    """
    try:
        result = await tenant_service.change_user_password(
            user_id=current_user["sub"],
            current_password=request.current_password,
            new_password=request.new_password
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "password_change_failed",
                    "message": result.get("message", "Şifre değiştirilemedi"),
                    "message_en": result.get("message_en", "Password change failed")
                }
            )
        
        logger.info("Password changed", user_id=current_user["sub"])
        
        return {
            "success": True,
            "message": "Şifre başarıyla değiştirildi",
            "message_en": "Password changed successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Password change error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "password_change_error",
                "message": "Şifre değiştirme sırasında hata oluştu",
                "message_en": "An error occurred during password change"
            }
        )


@router.get("/status")
async def auth_status():
    """Get authentication service status"""
    return {
        "status": "active",
        "service": "Authentication API",
        "version": "1.0.0",
        "features": [
            "JWT Authentication",
            "User Registration", 
            "Password Management",
            "KVKK Consent Management",
            "Token Refresh"
        ]
    }