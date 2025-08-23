"""
Webhook endpoints for Turkish Business Integration Platform
"""

import hmac
import hashlib
from typing import Dict, Any, List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks
from pydantic import BaseModel, Field, HttpUrl
import structlog

from src.core.security import get_current_active_user, require_permissions
from src.services.tenant_service import tenant_service

logger = structlog.get_logger(__name__)
router = APIRouter()


class WebhookCreateRequest(BaseModel):
    """Webhook creation request"""
    name: str = Field(..., min_length=2, max_length=100)
    url: HttpUrl = Field(..., description="Webhook endpoint URL")
    events: List[str] = Field(..., min_items=1, description="List of events to subscribe to")
    secret: Optional[str] = Field(None, min_length=32, max_length=128, description="Webhook secret for HMAC verification")
    is_active: bool = Field(default=True)
    retry_count: int = Field(default=3, ge=0, le=10)
    timeout: int = Field(default=10, ge=5, le=60)


class WebhookUpdateRequest(BaseModel):
    """Webhook update request"""
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    url: Optional[HttpUrl] = None
    events: Optional[List[str]] = Field(None, min_items=1)
    secret: Optional[str] = Field(None, min_length=32, max_length=128)
    is_active: Optional[bool] = None
    retry_count: Optional[int] = Field(None, ge=0, le=10)
    timeout: Optional[int] = Field(None, ge=5, le=60)


@router.get("/")
async def get_webhooks(
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """
    Get all webhooks for tenant
    """
    try:
        tenant_id = current_user["tenant_id"]
        
        result = await tenant_service.get_tenant_webhooks(tenant_id)
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "get_webhooks_error",
                    "message": result.get("message", "Webhook'lar alınamadı"),
                    "message_en": result.get("message_en", "Failed to get webhooks")
                }
            )
        
        return {
            "success": True,
            "webhooks": result["webhooks"],
            "available_events": [
                {
                    "event": "user.created",
                    "description": "Yeni kullanıcı oluşturulduğunda",
                    "description_en": "When a new user is created"
                },
                {
                    "event": "user.updated", 
                    "description": "Kullanıcı bilgileri güncellendiğinde",
                    "description_en": "When user information is updated"
                },
                {
                    "event": "user.deleted",
                    "description": "Kullanıcı silindiğinde",
                    "description_en": "When a user is deleted"
                },
                {
                    "event": "tenant.updated",
                    "description": "Şirket bilgileri güncellendiğinde",
                    "description_en": "When tenant information is updated"
                },
                {
                    "event": "subscription.upgraded",
                    "description": "Abonelik yükseltildiğinde",
                    "description_en": "When subscription is upgraded"
                },
                {
                    "event": "integration.configured",
                    "description": "Entegrasyon yapılandırıldığında",
                    "description_en": "When integration is configured"
                },
                {
                    "event": "sms.sent",
                    "description": "SMS gönderildiğinde",
                    "description_en": "When SMS is sent"
                },
                {
                    "event": "sms.delivered",
                    "description": "SMS teslim edildiğinde",
                    "description_en": "When SMS is delivered"
                },
                {
                    "event": "whatsapp.sent",
                    "description": "WhatsApp mesajı gönderildiğinde",
                    "description_en": "When WhatsApp message is sent"
                },
                {
                    "event": "whatsapp.delivered",
                    "description": "WhatsApp mesajı teslim edildiğinde",
                    "description_en": "When WhatsApp message is delivered"
                },
                {
                    "event": "kvkk.consent_given",
                    "description": "KVKK onayı verildiğinde",
                    "description_en": "When KVKK consent is given"
                },
                {
                    "event": "kvkk.consent_withdrawn",
                    "description": "KVKK onayı geri çekildiğinde",
                    "description_en": "When KVKK consent is withdrawn"
                },
                {
                    "event": "kvkk.data_exported",
                    "description": "Veri dışa aktarıldığında",
                    "description_en": "When data is exported"
                },
                {
                    "event": "kvkk.data_anonymized",
                    "description": "Veri anonimleştirildiğinde",
                    "description_en": "When data is anonymized"
                }
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Get webhooks error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "get_webhooks_error",
                "message": "Webhook'lar alınırken hata oluştu",
                "message_en": "Error getting webhooks"
            }
        )


@router.post("/")
async def create_webhook(
    request: WebhookCreateRequest,
    current_user: Dict[str, Any] = Depends(require_permissions(["webhook:create"]))
):
    """
    Create new webhook (admin only)
    """
    try:
        tenant_id = current_user["tenant_id"]
        user_id = current_user["sub"]
        
        # Validate events
        valid_events = [
            "user.created", "user.updated", "user.deleted",
            "tenant.updated", "subscription.upgraded", "integration.configured",
            "sms.sent", "sms.delivered", "whatsapp.sent", "whatsapp.delivered",
            "kvkk.consent_given", "kvkk.consent_withdrawn", "kvkk.data_exported", "kvkk.data_anonymized"
        ]
        
        for event in request.events:
            if event not in valid_events:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": "invalid_event",
                        "message": f"Geçersiz event: {event}",
                        "message_en": f"Invalid event: {event}",
                        "valid_events": valid_events
                    }
                )
        
        result = await tenant_service.create_webhook(
            tenant_id=tenant_id,
            name=request.name,
            url=str(request.url),
            events=request.events,
            secret=request.secret,
            is_active=request.is_active,
            retry_count=request.retry_count,
            timeout=request.timeout,
            created_by=user_id
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "webhook_creation_failed",
                    "message": result.get("message", "Webhook oluşturulamadı"),
                    "message_en": result.get("message_en", "Webhook creation failed")
                }
            )
        
        logger.info(
            "Webhook created",
            tenant_id=str(tenant_id),
            webhook_id=str(result["webhook_id"]),
            url=str(request.url),
            events=request.events,
            created_by=str(user_id)
        )
        
        return {
            "success": True,
            "message": "Webhook başarıyla oluşturuldu",
            "message_en": "Webhook created successfully",
            "webhook_id": str(result["webhook_id"]),
            "webhook": result["webhook"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Create webhook error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "create_webhook_error",
                "message": "Webhook oluşturma sırasında hata oluştu",
                "message_en": "Error creating webhook"
            }
        )


@router.get("/{webhook_id}")
async def get_webhook(
    webhook_id: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user)
):
    """
    Get specific webhook by ID
    """
    try:
        tenant_id = current_user["tenant_id"]
        
        result = await tenant_service.get_webhook_by_id(tenant_id, webhook_id)
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "webhook_not_found",
                    "message": "Webhook bulunamadı",
                    "message_en": "Webhook not found"
                }
            )
        
        return {
            "success": True,
            "webhook": result["webhook"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Get webhook error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "get_webhook_error",
                "message": "Webhook bilgileri alınırken hata oluştu",
                "message_en": "Error getting webhook information"
            }
        )


@router.put("/{webhook_id}")
async def update_webhook(
    webhook_id: str,
    request: WebhookUpdateRequest,
    current_user: Dict[str, Any] = Depends(require_permissions(["webhook:update"]))
):
    """
    Update webhook (admin only)
    """
    try:
        tenant_id = current_user["tenant_id"]
        user_id = current_user["sub"]
        
        # Prepare update data
        update_data = {}
        for field, value in request.dict(exclude_unset=True).items():
            if value is not None:
                if field == "url":
                    update_data[field] = str(value)
                else:
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
        
        # Validate events if provided
        if "events" in update_data:
            valid_events = [
                "user.created", "user.updated", "user.deleted",
                "tenant.updated", "subscription.upgraded", "integration.configured",
                "sms.sent", "sms.delivered", "whatsapp.sent", "whatsapp.delivered",
                "kvkk.consent_given", "kvkk.consent_withdrawn", "kvkk.data_exported", "kvkk.data_anonymized"
            ]
            
            for event in update_data["events"]:
                if event not in valid_events:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail={
                            "error": "invalid_event",
                            "message": f"Geçersiz event: {event}",
                            "message_en": f"Invalid event: {event}",
                            "valid_events": valid_events
                        }
                    )
        
        result = await tenant_service.update_webhook(
            tenant_id=tenant_id,
            webhook_id=webhook_id,
            update_data=update_data,
            updated_by=user_id
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "webhook_update_failed",
                    "message": result.get("message", "Webhook güncellenemedi"),
                    "message_en": result.get("message_en", "Webhook update failed")
                }
            )
        
        logger.info(
            "Webhook updated",
            tenant_id=str(tenant_id),
            webhook_id=webhook_id,
            updated_by=str(user_id),
            fields=list(update_data.keys())
        )
        
        return {
            "success": True,
            "message": "Webhook başarıyla güncellendi",
            "message_en": "Webhook updated successfully",
            "webhook": result["webhook"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Update webhook error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "update_webhook_error",
                "message": "Webhook güncelleme sırasında hata oluştu",
                "message_en": "Error updating webhook"
            }
        )


@router.delete("/{webhook_id}")
async def delete_webhook(
    webhook_id: str,
    current_user: Dict[str, Any] = Depends(require_permissions(["webhook:delete"]))
):
    """
    Delete webhook (admin only)
    """
    try:
        tenant_id = current_user["tenant_id"]
        user_id = current_user["sub"]
        
        result = await tenant_service.delete_webhook(
            tenant_id=tenant_id,
            webhook_id=webhook_id,
            deleted_by=user_id
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "webhook_delete_failed",
                    "message": result.get("message", "Webhook silinemedi"),
                    "message_en": result.get("message_en", "Webhook delete failed")
                }
            )
        
        logger.info(
            "Webhook deleted",
            tenant_id=str(tenant_id),
            webhook_id=webhook_id,
            deleted_by=str(user_id)
        )
        
        return {
            "success": True,
            "message": "Webhook başarıyla silindi",
            "message_en": "Webhook deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Delete webhook error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "delete_webhook_error",
                "message": "Webhook silme sırasında hata oluştu",
                "message_en": "Error deleting webhook"
            }
        )


@router.post("/{webhook_id}/test")
async def test_webhook(
    webhook_id: str,
    background_tasks: BackgroundTasks,
    current_user: Dict[str, Any] = Depends(require_permissions(["webhook:test"]))
):
    """
    Test webhook by sending a test event (admin only)
    """
    try:
        tenant_id = current_user["tenant_id"]
        user_id = current_user["sub"]
        
        # Get webhook details
        webhook_result = await tenant_service.get_webhook_by_id(tenant_id, webhook_id)
        
        if not webhook_result["success"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "webhook_not_found",
                    "message": "Webhook bulunamadı",
                    "message_en": "Webhook not found"
                }
            )
        
        webhook = webhook_result["webhook"]
        
        # Create test payload
        test_payload = {
            "event": "webhook.test",
            "timestamp": datetime.utcnow().isoformat(),
            "tenant_id": str(tenant_id),
            "webhook_id": webhook_id,
            "test": True,
            "data": {
                "message": "Bu bir test webhook'udur",
                "message_en": "This is a test webhook",
                "triggered_by": str(user_id)
            }
        }
        
        # Schedule webhook delivery
        background_tasks.add_task(
            tenant_service.send_webhook,
            webhook_id=webhook_id,
            payload=test_payload
        )
        
        logger.info(
            "Webhook test triggered",
            tenant_id=str(tenant_id),
            webhook_id=webhook_id,
            url=webhook["url"],
            triggered_by=str(user_id)
        )
        
        return {
            "success": True,
            "message": "Test webhook'u gönderildi",
            "message_en": "Test webhook sent",
            "test_payload": test_payload
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Test webhook error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "test_webhook_error",
                "message": "Webhook test sırasında hata oluştu",
                "message_en": "Error testing webhook"
            }
        )


@router.get("/{webhook_id}/logs")
async def get_webhook_logs(
    webhook_id: str,
    current_user: Dict[str, Any] = Depends(get_current_active_user),
    limit: int = 50,
    offset: int = 0
):
    """
    Get webhook delivery logs
    """
    try:
        tenant_id = current_user["tenant_id"]
        
        result = await tenant_service.get_webhook_logs(
            tenant_id=tenant_id,
            webhook_id=webhook_id,
            limit=limit,
            offset=offset
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "get_logs_error",
                    "message": result.get("message", "Webhook logları alınamadı"),
                    "message_en": result.get("message_en", "Failed to get webhook logs")
                }
            )
        
        return {
            "success": True,
            "logs": result["logs"],
            "total": result["total"],
            "limit": limit,
            "offset": offset
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Get webhook logs error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "get_logs_error",
                "message": "Webhook logları alınırken hata oluştu",
                "message_en": "Error getting webhook logs"
            }
        )


@router.post("/delivery/{delivery_id}/retry")
async def retry_webhook_delivery(
    delivery_id: str,
    background_tasks: BackgroundTasks,
    current_user: Dict[str, Any] = Depends(require_permissions(["webhook:retry"]))
):
    """
    Retry failed webhook delivery (admin only)
    """
    try:
        tenant_id = current_user["tenant_id"]
        user_id = current_user["sub"]
        
        result = await tenant_service.retry_webhook_delivery(
            tenant_id=tenant_id,
            delivery_id=delivery_id,
            retried_by=user_id
        )
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "retry_failed",
                    "message": result.get("message", "Webhook yeniden gönderim başarısız"),
                    "message_en": result.get("message_en", "Webhook retry failed")
                }
            )
        
        # Schedule retry
        background_tasks.add_task(
            tenant_service.send_webhook,
            webhook_id=result["webhook_id"],
            payload=result["payload"],
            delivery_id=delivery_id
        )
        
        logger.info(
            "Webhook delivery retried",
            tenant_id=str(tenant_id),
            delivery_id=delivery_id,
            retried_by=str(user_id)
        )
        
        return {
            "success": True,
            "message": "Webhook yeniden gönderimi başlatıldı",
            "message_en": "Webhook retry initiated"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Retry webhook delivery error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "retry_error",
                "message": "Webhook yeniden gönderim sırasında hata oluştu",
                "message_en": "Error retrying webhook delivery"
            }
        )


# Webhook receivers for external services
@router.post("/receive/netgsm")
async def receive_netgsm_webhook(request: Request):
    """
    Receive delivery reports from NetGSM
    """
    try:
        payload = await request.json()
        
        # Process NetGSM delivery report
        # This would typically update message status and trigger tenant webhooks
        logger.info("NetGSM webhook received", payload=payload)
        
        # Here you would:
        # 1. Validate the webhook signature if NetGSM provides one
        # 2. Update message delivery status in database
        # 3. Trigger tenant webhooks for sms.delivered or whatsapp.delivered events
        
        return {"success": True, "message": "Webhook received"}
        
    except Exception as e:
        logger.error("NetGSM webhook error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "webhook_processing_error"}
        )


@router.get("/status")
async def webhook_status():
    """Get webhook service status"""
    return {
        "status": "active",
        "service": "Webhook API",
        "version": "1.0.0",
        "features": [
            "Webhook Management",
            "Event Subscriptions", 
            "HMAC Signature Verification",
            "Delivery Retry Logic",
            "Delivery Logs",
            "External Webhook Receivers"
        ],
        "supported_events": [
            "user.created", "user.updated", "user.deleted",
            "tenant.updated", "subscription.upgraded", "integration.configured",
            "sms.sent", "sms.delivered", "whatsapp.sent", "whatsapp.delivered",
            "kvkk.consent_given", "kvkk.consent_withdrawn", "kvkk.data_exported", "kvkk.data_anonymized"
        ]
    }