"""
Tenant management endpoints for Turkish Business Integration Platform
"""

from typing import Dict, Any, List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field, validator
import structlog

from src.core.security import get_current_active_user, require_permissions
from src.services.tenant_service import tenant_service
from src.services.kvkk_service import kvkk_service, DataExportRequest, AnonymizationRequest

logger = structlog.get_logger(__name__)
router = APIRouter()


class TenantUpdateRequest(BaseModel):
    """Tenant update request"""
    company_name: Optional[str] = Field(None, min_length=2, max_length=100)
    phone: Optional[str] = Field(None, regex=r'^\+90[0-9]{10}$')
    address: Optional[str] = Field(None, max_length=500)
    website: Optional[str] = Field(None, max_length=200)
    industry: Optional[str] = Field(None, max_length=100)
    

class UserCreateRequest(BaseModel):
    """Create new user request"""
    email: str = Field(..., max_length=255)
    first_name: str = Field(..., min_length=2, max_length=50)
    last_name: str = Field(..., min_length=2, max_length=50)
    phone: Optional[str] = Field(None, regex=r'^\+90[0-9]{10}$')
    role: str = Field(default="user", regex="^(admin|user|viewer)$")
    permissions: List[str] = Field(default_factory=list)


class UserUpdateRequest(BaseModel):
    """Update user request"""
    first_name: Optional[str] = Field(None, min_length=2, max_length=50)
    last_name: Optional[str] = Field(None, min_length=2, max_length=50)
    phone: Optional[str] = Field(None, regex=r'^\+90[0-9]{10}$')
    role: Optional[str] = Field(None, regex="^(admin|user|viewer)$")
    permissions: Optional[List[str]] = None
    is_active: Optional[bool] = None


class PlanUpgradeRequest(BaseModel):
    """Plan upgrade request"""
    plan: str = Field(..., regex="^(starter|professional|enterprise)$")
    billing_period: str = Field(default="monthly", regex="^(monthly|yearly)$")


@router.get("/info")
async def get_tenant_info(current_user: Dict[str, Any] = Depends(get_current_active_user)):
    """
    Get current tenant information
    """
    try:
        tenant_id = current_user["tenant_id"]
        result = await tenant_service.get_tenant_by_id(tenant_id)
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "tenant_not_found",
                    "message": "Şirket bilgileri bulunamadı",
                    "message_en": "Tenant not found"
                }
            )
        
        return {
            "success": True,
            "tenant": result["tenant"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Get tenant info error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "get_tenant_error",
                "message": "Şirket bilgileri alınırken hata oluştu",
                "message_en": "Error getting tenant information"
            }
        )


@router.put("/info")
async def update_tenant_info(
    request: TenantUpdateRequest,
    current_user: Dict[str, Any] = Depends(require_permissions(["tenant:update"]))
):
    """
    Update tenant information (admin only)
    """
    try:
        tenant_id = current_user["tenant_id"]
        user_id = current_user["sub"]
        
        # Prepare update data
        update_data = {}
        for field, value in request.dict(exclude_unset=True).items():
            if value is not None:
                update_data[field] = value
        
        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "no_data",
                    "message": "Güncellenecek veri yok",
                    "message_en": "No data to update"
                }
            )
        
        result = await tenant_service.update_tenant(
            tenant_id=tenant_id,
            update_data=update_data,
            updated_by=user_id
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "update_failed",
                    "message": result.get("message", "Güncelleme başarısız"),
                    "message_en": result.get("message_en", "Update failed")
                }
            )
        
        logger.info(
            "Tenant updated",
            tenant_id=str(tenant_id),
            updated_by=str(user_id),
            fields=list(update_data.keys())
        )
        
        return {
            "success": True,
            "message": "Şirket bilgileri güncellendi",
            "message_en": "Tenant information updated",
            "tenant": result["tenant"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Update tenant error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "update_tenant_error",
                "message": "Güncelleme sırasında hata oluştu",
                "message_en": "Error updating tenant information"
            }
        )


@router.get("/users")
async def get_tenant_users(
    current_user: Dict[str, Any] = Depends(require_permissions(["user:read"])),
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None, max_length=100)
):
    """
    Get tenant users with pagination and search
    """
    try:
        tenant_id = current_user["tenant_id"]
        
        result = await tenant_service.get_tenant_users(
            tenant_id=tenant_id,
            page=page,
            size=size,
            search=search
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "get_users_error",
                    "message": result.get("message", "Kullanıcılar alınamadı"),
                    "message_en": result.get("message_en", "Failed to get users")
                }
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Get tenant users error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "get_users_error",
                "message": "Kullanıcı listesi alınırken hata oluştu",
                "message_en": "Error getting user list"
            }
        )


@router.post("/users")
async def create_user(
    request: UserCreateRequest,
    current_user: Dict[str, Any] = Depends(require_permissions(["user:create"]))
):
    """
    Create new user (admin only)
    """
    try:
        tenant_id = current_user["tenant_id"]
        created_by = current_user["sub"]
        
        result = await tenant_service.create_user(
            tenant_id=tenant_id,
            email=request.email,
            first_name=request.first_name,
            last_name=request.last_name,
            phone=request.phone,
            role=request.role,
            permissions=request.permissions,
            created_by=created_by
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "user_creation_failed",
                    "message": result.get("message", "Kullanıcı oluşturulamadı"),
                    "message_en": result.get("message_en", "User creation failed")
                }
            )
        
        logger.info(
            "User created",
            tenant_id=str(tenant_id),
            user_id=str(result["user_id"]),
            email=request.email,
            created_by=str(created_by)
        )
        
        return {
            "success": True,
            "message": "Kullanıcı başarıyla oluşturuldu",
            "message_en": "User created successfully",
            "user_id": str(result["user_id"]),
            "user": result["user"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Create user error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "create_user_error",
                "message": "Kullanıcı oluşturma sırasında hata oluştu",
                "message_en": "Error creating user"
            }
        )


@router.put("/users/{user_id}")
async def update_user(
    user_id: str,
    request: UserUpdateRequest,
    current_user: Dict[str, Any] = Depends(require_permissions(["user:update"]))
):
    """
    Update user information (admin only)
    """
    try:
        tenant_id = current_user["tenant_id"]
        updated_by = current_user["sub"]
        
        # Prepare update data
        update_data = {}
        for field, value in request.dict(exclude_unset=True).items():
            if value is not None:
                update_data[field] = value
        
        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "no_data",
                    "message": "Güncellenecek veri yok",
                    "message_en": "No data to update"
                }
            )
        
        result = await tenant_service.update_user(
            tenant_id=tenant_id,
            user_id=user_id,
            update_data=update_data,
            updated_by=updated_by
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "update_failed",
                    "message": result.get("message", "Güncelleme başarısız"),
                    "message_en": result.get("message_en", "Update failed")
                }
            )
        
        logger.info(
            "User updated",
            tenant_id=str(tenant_id),
            user_id=user_id,
            updated_by=str(updated_by),
            fields=list(update_data.keys())
        )
        
        return {
            "success": True,
            "message": "Kullanıcı bilgileri güncellendi",
            "message_en": "User information updated",
            "user": result["user"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Update user error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "update_user_error",
                "message": "Kullanıcı güncelleme sırasında hata oluştu",
                "message_en": "Error updating user"
            }
        )


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    current_user: Dict[str, Any] = Depends(require_permissions(["user:delete"]))
):
    """
    Delete user (admin only)
    """
    try:
        tenant_id = current_user["tenant_id"]
        deleted_by = current_user["sub"]
        
        # Prevent self-deletion
        if user_id == deleted_by:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "cannot_delete_self",
                    "message": "Kendi hesabınızı silemezsiniz",
                    "message_en": "Cannot delete your own account"
                }
            )
        
        result = await tenant_service.delete_user(
            tenant_id=tenant_id,
            user_id=user_id,
            deleted_by=deleted_by
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "delete_failed",
                    "message": result.get("message", "Silme işlemi başarısız"),
                    "message_en": result.get("message_en", "Delete failed")
                }
            )
        
        logger.info(
            "User deleted",
            tenant_id=str(tenant_id),
            user_id=user_id,
            deleted_by=str(deleted_by)
        )
        
        return {
            "success": True,
            "message": "Kullanıcı başarıyla silindi",
            "message_en": "User deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Delete user error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "delete_user_error",
                "message": "Kullanıcı silme sırasında hata oluştu",
                "message_en": "Error deleting user"
            }
        )


@router.get("/subscription")
async def get_subscription_info(
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """
    Get tenant subscription information
    """
    try:
        tenant_id = current_user["tenant_id"]
        result = await tenant_service.get_subscription_info(tenant_id)
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "subscription_error",
                    "message": result.get("message", "Abonelik bilgileri alınamadı"),
                    "message_en": result.get("message_en", "Failed to get subscription info")
                }
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Get subscription info error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "subscription_error",
                "message": "Abonelik bilgileri alınırken hata oluştu",
                "message_en": "Error getting subscription information"
            }
        )


@router.post("/subscription/upgrade")
async def upgrade_subscription(
    request: PlanUpgradeRequest,
    current_user: Dict[str, Any] = Depends(require_permissions(["tenant:billing"]))
):
    """
    Upgrade tenant subscription plan (admin only)
    """
    try:
        tenant_id = current_user["tenant_id"]
        user_id = current_user["sub"]
        
        result = await tenant_service.upgrade_tenant_plan(
            tenant_id=tenant_id,
            new_plan=request.plan,
            billing_period=request.billing_period,
            upgraded_by=user_id
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "upgrade_failed",
                    "message": result.get("message", "Plan yükseltme başarısız"),
                    "message_en": result.get("message_en", "Plan upgrade failed")
                }
            )
        
        logger.info(
            "Subscription upgraded",
            tenant_id=str(tenant_id),
            new_plan=request.plan,
            billing_period=request.billing_period,
            upgraded_by=str(user_id)
        )
        
        return {
            "success": True,
            "message": f"Plan {request.plan} seviyesine yükseltildi",
            "message_en": f"Plan upgraded to {request.plan}",
            "subscription": result["subscription"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Upgrade subscription error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "upgrade_error",
                "message": "Plan yükseltme sırasında hata oluştu",
                "message_en": "Error upgrading subscription"
            }
        )


@router.get("/usage")
async def get_usage_stats(
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """
    Get tenant usage statistics
    """
    try:
        tenant_id = current_user["tenant_id"]
        result = await tenant_service.get_usage_stats(tenant_id)
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "usage_stats_error",
                    "message": result.get("message", "Kullanım istatistikleri alınamadı"),
                    "message_en": result.get("message_en", "Failed to get usage statistics")
                }
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Get usage stats error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "usage_stats_error",
                "message": "Kullanım istatistikleri alınırken hata oluştu",
                "message_en": "Error getting usage statistics"
            }
        )


@router.post("/kvkk/export-data")
async def export_user_data(
    request: DataExportRequest,
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """
    Export user data for KVKK compliance (data portability right)
    """
    try:
        tenant_id = current_user["tenant_id"]
        
        # Users can only export their own data unless they have admin rights
        if (str(request.data_subject_id) != current_user["sub"] and 
            "kvkk:export_all" not in current_user.get("permissions", [])):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "insufficient_permissions",
                    "message": "Sadece kendi verilerinizi dışa aktarabilirsiniz",
                    "message_en": "You can only export your own data"
                }
            )
        
        result = await kvkk_service.export_user_data(tenant_id, request)
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "export_failed",
                    "message": result.get("message", "Veri dışa aktarımı başarısız"),
                    "message_en": result.get("message_en", "Data export failed")
                }
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Export user data error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "export_error",
                "message": "Veri dışa aktarma sırasında hata oluştu",
                "message_en": "Error exporting user data"
            }
        )


@router.post("/kvkk/anonymize-data")
async def anonymize_user_data(
    request: AnonymizationRequest,
    current_user: Dict[str, Any] = Depends(require_permissions(["kvkk:anonymize"]))
):
    """
    Anonymize user data for KVKK compliance (right to erasure) - Admin only
    """
    try:
        tenant_id = current_user["tenant_id"]
        performed_by = current_user["sub"]
        
        result = await kvkk_service.anonymize_user_data(
            tenant_id, 
            request,
            performed_by
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "anonymization_failed",
                    "message": result.get("message", "Veri anonimleştirme başarısız"),
                    "message_en": result.get("message_en", "Data anonymization failed")
                }
            )
        
        logger.info(
            "User data anonymized",
            tenant_id=str(tenant_id),
            data_subject_id=str(request.data_subject_id),
            performed_by=str(performed_by)
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Anonymize user data error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "anonymization_error",
                "message": "Veri anonimleştirme sırasında hata oluştu",
                "message_en": "Error anonymizing user data"
            }
        )


@router.get("/status")
async def tenant_status():
    """Get tenant service status"""
    return {
        "status": "active",
        "service": "Tenant Management API",
        "version": "1.0.0",
        "features": [
            "Tenant Information Management",
            "User Management",
            "Subscription Management",
            "Usage Statistics",
            "KVKK Compliance",
            "Data Export & Anonymization"
        ]
    }