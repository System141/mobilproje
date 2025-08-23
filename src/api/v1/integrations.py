"""
Integration endpoints for Turkish Business Integration Platform
"""

from typing import Dict, Any, List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from pydantic import BaseModel, Field, validator
import structlog

from src.core.security import get_current_active_user, require_permissions
from src.integrations.netgsm import NetgsmConnector
from src.integrations.base_connector import ConnectorConfig, ConnectorResponse
from src.services.tenant_service import tenant_service

logger = structlog.get_logger(__name__)
router = APIRouter()


class SMSRequest(BaseModel):
    """SMS sending request"""
    phone: str = Field(..., regex=r'^\+90[0-9]{10}$')
    message: str = Field(..., min_length=1, max_length=160)
    sender_name: Optional[str] = Field(None, max_length=11)
    
    
class WhatsAppRequest(BaseModel):
    """WhatsApp message request"""
    phone: str = Field(..., regex=r'^\+90[0-9]{10}$')
    message: str = Field(..., min_length=1, max_length=4096)
    message_type: str = Field(default="text", regex="^(text|template)$")
    template_name: Optional[str] = None
    template_params: Optional[Dict[str, str]] = None


class BulkSMSRequest(BaseModel):
    """Bulk SMS sending request"""
    phones: List[str] = Field(..., min_items=1, max_items=1000)
    message: str = Field(..., min_length=1, max_length=160)
    sender_name: Optional[str] = Field(None, max_length=11)
    
    @validator('phones')
    def validate_phones(cls, v):
        for phone in v:
            if not phone.match(r'^\+90[0-9]{10}$'):
                raise ValueError(f'Invalid phone format: {phone}')
        return v


class IntegrationConfigRequest(BaseModel):
    """Integration configuration request"""
    integration_type: str = Field(..., regex="^(netgsm|iyzico|efatura|bulutfon|arvento)$")
    config: Dict[str, Any] = Field(..., min_items=1)
    is_active: bool = Field(default=True)


class IntegrationTestRequest(BaseModel):
    """Integration connection test request"""
    integration_type: str = Field(..., regex="^(netgsm|iyzico|efatura|bulutfon|arvento)$")


@router.get("/")
async def get_integrations(
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """
    Get available integrations for tenant
    """
    try:
        tenant_id = current_user["tenant_id"]
        
        # Get tenant integration configurations
        result = await tenant_service.get_tenant_integrations(tenant_id)
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "get_integrations_error",
                    "message": result.get("message", "Entegrasyonlar alınamadı"),
                    "message_en": result.get("message_en", "Failed to get integrations")
                }
            )
        
        return {
            "success": True,
            "integrations": result["integrations"],
            "available_integrations": [
                {
                    "type": "netgsm",
                    "name": "NetGSM SMS & WhatsApp",
                    "description": "SMS ve WhatsApp mesajlaşma hizmeti",
                    "features": ["SMS", "WhatsApp", "Bulk SMS", "Delivery Reports"],
                    "status": "active"
                },
                {
                    "type": "iyzico", 
                    "name": "Iyzico Payment",
                    "description": "Online ödeme ve sanal pos hizmeti",
                    "features": ["Credit Card", "Installments", "3D Secure", "Refunds"],
                    "status": "planned"
                },
                {
                    "type": "efatura",
                    "name": "E-Fatura",
                    "description": "Elektronik fatura entegrasyonu",
                    "features": ["Invoice Creation", "Invoice Query", "Tax Integration"],
                    "status": "planned"
                },
                {
                    "type": "bulutfon",
                    "name": "Bulutfon VoIP",
                    "description": "Bulut tabanlı telefon sistemi",
                    "features": ["Call Management", "IVR", "Call Recording"],
                    "status": "planned"
                },
                {
                    "type": "arvento",
                    "name": "Arvento Fleet",
                    "description": "Araç takip ve filo yönetimi",
                    "features": ["Vehicle Tracking", "Route Optimization", "Reports"],
                    "status": "planned"
                }
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Get integrations error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "get_integrations_error",
                "message": "Entegrasyonlar alınırken hata oluştu",
                "message_en": "Error getting integrations"
            }
        )


@router.post("/config")
async def configure_integration(
    request: IntegrationConfigRequest,
    current_user: Dict[str, Any] = Depends(require_permissions(["integration:config"]))
):
    """
    Configure integration for tenant (admin only)
    """
    try:
        tenant_id = current_user["tenant_id"]
        user_id = current_user["sub"]
        
        result = await tenant_service.configure_integration(
            tenant_id=tenant_id,
            integration_type=request.integration_type,
            config=request.config,
            is_active=request.is_active,
            configured_by=user_id
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "config_failed",
                    "message": result.get("message", "Entegrasyon yapılandırılamadı"),
                    "message_en": result.get("message_en", "Integration configuration failed")
                }
            )
        
        logger.info(
            "Integration configured",
            tenant_id=str(tenant_id),
            integration_type=request.integration_type,
            configured_by=str(user_id)
        )
        
        return {
            "success": True,
            "message": f"{request.integration_type} entegrasyonu yapılandırıldı",
            "message_en": f"{request.integration_type} integration configured",
            "integration": result["integration"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Configure integration error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "config_error",
                "message": "Entegrasyon yapılandırma sırasında hata oluştu",
                "message_en": "Error configuring integration"
            }
        )


@router.post("/test")
async def test_integration(
    request: IntegrationTestRequest,
    current_user: Dict[str, Any] = Depends(require_permissions(["integration:test"]))
):
    """
    Test integration connection (admin only)
    """
    try:
        tenant_id = current_user["tenant_id"]
        
        # Get integration config for tenant
        config_result = await tenant_service.get_integration_config(
            tenant_id, 
            request.integration_type
        )
        
        if not config_result["success"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "integration_not_configured",
                    "message": f"{request.integration_type} entegrasyonu yapılandırılmamış",
                    "message_en": f"{request.integration_type} integration not configured"
                }
            )
        
        config = config_result["config"]
        
        # Test connection based on integration type
        if request.integration_type == "netgsm":
            connector_config = ConnectorConfig(
                base_url="https://api.netgsm.com.tr",
                username=config.get("username"),
                password=config.get("password")
            )
            
            async with NetgsmConnector(connector_config) as connector:
                result = await connector.test_connection()
        else:
            # Other integrations would be implemented here
            result = ConnectorResponse(
                success=False,
                error="Integration not implemented yet",
                message_tr="Bu entegrasyon henüz geliştirilmemiş",
                message_en="This integration is not implemented yet"
            )
        
        logger.info(
            "Integration tested",
            tenant_id=str(tenant_id),
            integration_type=request.integration_type,
            success=result.success
        )
        
        return {
            "success": result.success,
            "message": result.message_tr or ("Bağlantı başarılı" if result.success else "Bağlantı başarısız"),
            "message_en": result.message_en or ("Connection successful" if result.success else "Connection failed"),
            "test_result": {
                "status_code": result.status_code,
                "data": result.data,
                "error": result.error,
                "timestamp": result.timestamp.isoformat()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Test integration error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "test_error",
                "message": "Entegrasyon test sırasında hata oluştu",
                "message_en": "Error testing integration"
            }
        )


@router.post("/netgsm/sms")
async def send_sms(
    request: SMSRequest,
    background_tasks: BackgroundTasks,
    current_user: Dict[str, Any] = Depends(require_permissions(["integration:sms"]))
):
    """
    Send SMS via NetGSM
    """
    try:
        tenant_id = current_user["tenant_id"]
        user_id = current_user["sub"]
        
        # Check SMS quota
        quota_result = await tenant_service.check_quota(tenant_id, "sms", 1)
        if not quota_result["success"]:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "quota_exceeded",
                    "message": quota_result.get("message", "SMS kotası aşıldı"),
                    "message_en": quota_result.get("message_en", "SMS quota exceeded")
                }
            )
        
        # Get NetGSM configuration
        config_result = await tenant_service.get_integration_config(tenant_id, "netgsm")
        
        if not config_result["success"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "netgsm_not_configured",
                    "message": "NetGSM entegrasyonu yapılandırılmamış",
                    "message_en": "NetGSM integration not configured"
                }
            )
        
        config = config_result["config"]
        
        # Create connector and send SMS
        connector_config = ConnectorConfig(
            base_url="https://api.netgsm.com.tr",
            username=config.get("username"),
            password=config.get("password")
        )
        
        async with NetgsmConnector(connector_config) as connector:
            result = await connector.send_sms(
                phone=request.phone,
                message=request.message,
                sender=request.sender_name or config.get("default_sender", "NETGSM")
            )
        
        # Update usage stats
        background_tasks.add_task(
            tenant_service.update_usage,
            tenant_id,
            "sms",
            1,
            user_id
        )
        
        logger.info(
            "SMS sent",
            tenant_id=str(tenant_id),
            phone=request.phone,
            success=result.success,
            user_id=str(user_id)
        )
        
        return {
            "success": result.success,
            "message": result.message_tr or ("SMS gönderildi" if result.success else "SMS gönderilemedi"),
            "message_en": result.message_en or ("SMS sent" if result.success else "SMS failed"),
            "sms_result": {
                "message_id": result.data.get("message_id") if result.data else None,
                "status_code": result.status_code,
                "error": result.error
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Send SMS error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "sms_error",
                "message": "SMS gönderme sırasında hata oluştu",
                "message_en": "Error sending SMS"
            }
        )


@router.post("/netgsm/whatsapp")
async def send_whatsapp(
    request: WhatsAppRequest,
    background_tasks: BackgroundTasks,
    current_user: Dict[str, Any] = Depends(require_permissions(["integration:whatsapp"]))
):
    """
    Send WhatsApp message via NetGSM
    """
    try:
        tenant_id = current_user["tenant_id"]
        user_id = current_user["sub"]
        
        # Check WhatsApp quota
        quota_result = await tenant_service.check_quota(tenant_id, "whatsapp", 1)
        if not quota_result["success"]:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "quota_exceeded",
                    "message": quota_result.get("message", "WhatsApp kotası aşıldı"),
                    "message_en": quota_result.get("message_en", "WhatsApp quota exceeded")
                }
            )
        
        # Get NetGSM configuration
        config_result = await tenant_service.get_integration_config(tenant_id, "netgsm")
        
        if not config_result["success"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "netgsm_not_configured",
                    "message": "NetGSM entegrasyonu yapılandırılmamış",
                    "message_en": "NetGSM integration not configured"
                }
            )
        
        config = config_result["config"]
        
        # Create connector and send WhatsApp message
        connector_config = ConnectorConfig(
            base_url="https://api.netgsm.com.tr",
            username=config.get("username"),
            password=config.get("password")
        )
        
        async with NetgsmConnector(connector_config) as connector:
            if request.message_type == "template":
                result = await connector.send_whatsapp_template(
                    phone=request.phone,
                    template_name=request.template_name,
                    params=request.template_params or {}
                )
            else:
                result = await connector.send_whatsapp_message(
                    phone=request.phone,
                    message=request.message
                )
        
        # Update usage stats
        background_tasks.add_task(
            tenant_service.update_usage,
            tenant_id,
            "whatsapp",
            1,
            user_id
        )
        
        logger.info(
            "WhatsApp sent",
            tenant_id=str(tenant_id),
            phone=request.phone,
            message_type=request.message_type,
            success=result.success,
            user_id=str(user_id)
        )
        
        return {
            "success": result.success,
            "message": result.message_tr or ("WhatsApp mesajı gönderildi" if result.success else "WhatsApp mesajı gönderilemedi"),
            "message_en": result.message_en or ("WhatsApp sent" if result.success else "WhatsApp failed"),
            "whatsapp_result": {
                "message_id": result.data.get("message_id") if result.data else None,
                "status_code": result.status_code,
                "error": result.error
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Send WhatsApp error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "whatsapp_error",
                "message": "WhatsApp gönderme sırasında hata oluştu",
                "message_en": "Error sending WhatsApp"
            }
        )


@router.post("/netgsm/bulk-sms")
async def send_bulk_sms(
    request: BulkSMSRequest,
    background_tasks: BackgroundTasks,
    current_user: Dict[str, Any] = Depends(require_permissions(["integration:bulk_sms"]))
):
    """
    Send bulk SMS via NetGSM
    """
    try:
        tenant_id = current_user["tenant_id"]
        user_id = current_user["sub"]
        
        sms_count = len(request.phones)
        
        # Check SMS quota
        quota_result = await tenant_service.check_quota(tenant_id, "sms", sms_count)
        if not quota_result["success"]:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "quota_exceeded",
                    "message": quota_result.get("message", "SMS kotası aşıldı"),
                    "message_en": quota_result.get("message_en", "SMS quota exceeded")
                }
            )
        
        # Get NetGSM configuration
        config_result = await tenant_service.get_integration_config(tenant_id, "netgsm")
        
        if not config_result["success"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "netgsm_not_configured",
                    "message": "NetGSM entegrasyonu yapılandırılmamış",
                    "message_en": "NetGSM integration not configured"
                }
            )
        
        config = config_result["config"]
        
        # Create connector and send bulk SMS
        connector_config = ConnectorConfig(
            base_url="https://api.netgsm.com.tr",
            username=config.get("username"),
            password=config.get("password")
        )
        
        async with NetgsmConnector(connector_config) as connector:
            result = await connector.send_bulk_sms(
                phones=request.phones,
                message=request.message,
                sender=request.sender_name or config.get("default_sender", "NETGSM")
            )
        
        # Update usage stats
        successful_count = result.data.get("successful_count", 0) if result.data else 0
        background_tasks.add_task(
            tenant_service.update_usage,
            tenant_id,
            "sms",
            successful_count,
            user_id
        )
        
        logger.info(
            "Bulk SMS sent",
            tenant_id=str(tenant_id),
            total_count=sms_count,
            successful_count=successful_count,
            success=result.success,
            user_id=str(user_id)
        )
        
        return {
            "success": result.success,
            "message": result.message_tr or f"{successful_count}/{sms_count} SMS gönderildi",
            "message_en": result.message_en or f"{successful_count}/{sms_count} SMS sent",
            "bulk_result": {
                "total_count": sms_count,
                "successful_count": successful_count,
                "failed_count": sms_count - successful_count,
                "status_code": result.status_code,
                "error": result.error,
                "details": result.data
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Send bulk SMS error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "bulk_sms_error",
                "message": "Toplu SMS gönderme sırasında hata oluştu",
                "message_en": "Error sending bulk SMS"
            }
        )


@router.get("/netgsm/reports")
async def get_sms_reports(
    current_user: Dict[str, Any] = Depends(require_permissions(["integration:reports"])),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    message_type: Optional[str] = Query(None, regex="^(sms|whatsapp)$")
):
    """
    Get SMS/WhatsApp delivery reports from NetGSM
    """
    try:
        tenant_id = current_user["tenant_id"]
        
        # Get NetGSM configuration
        config_result = await tenant_service.get_integration_config(tenant_id, "netgsm")
        
        if not config_result["success"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "netgsm_not_configured",
                    "message": "NetGSM entegrasyonu yapılandırılmamış",
                    "message_en": "NetGSM integration not configured"
                }
            )
        
        config = config_result["config"]
        
        # Create connector and get reports
        connector_config = ConnectorConfig(
            base_url="https://api.netgsm.com.tr",
            username=config.get("username"),
            password=config.get("password")
        )
        
        async with NetgsmConnector(connector_config) as connector:
            result = await connector.get_reports(
                start_date=start_date,
                end_date=end_date,
                message_type=message_type
            )
        
        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "reports_failed",
                    "message": result.message_tr or "Raporlar alınamadı",
                    "message_en": result.message_en or "Failed to get reports"
                }
            )
        
        return {
            "success": True,
            "reports": result.data,
            "message": "Raporlar başarıyla alındı",
            "message_en": "Reports retrieved successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Get SMS reports error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "reports_error",
                "message": "Rapor alma sırasında hata oluştu",
                "message_en": "Error getting reports"
            }
        )


@router.get("/status")
async def integration_status():
    """Get integration service status"""
    return {
        "status": "active",
        "service": "Integration API",
        "version": "1.0.0",
        "available_integrations": {
            "netgsm": {
                "status": "active",
                "features": ["SMS", "WhatsApp", "Bulk SMS", "Reports"]
            },
            "iyzico": {
                "status": "planned",
                "features": ["Payments", "Refunds", "Installments"]
            },
            "efatura": {
                "status": "planned", 
                "features": ["Invoice Creation", "Tax Integration"]
            },
            "bulutfon": {
                "status": "planned",
                "features": ["VoIP", "Call Management"]
            },
            "arvento": {
                "status": "planned",
                "features": ["Fleet Tracking", "Route Optimization"]
            }
        }
    }