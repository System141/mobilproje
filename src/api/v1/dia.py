"""
DIA ERP Integration API Endpoints
"""

from typing import Dict, Any, Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from pydantic import BaseModel, Field
import structlog

from src.core.security import get_current_user, require_permissions
from src.services.tenant_service import tenant_service
from src.integrations.dia.connector import DIAConnector
from src.integrations.dia.services import DIAService
from src.integrations.dia.config import DIAConfig, DIAModuleConfig, DIASyncConfig
from src.integrations.base_connector import ConnectorResponse


logger = structlog.get_logger(__name__)
router = APIRouter()


# Request/Response Models
class DIAConnectionRequest(BaseModel):
    """DIA connection request"""
    server_code: str = Field(..., description="DIA server code")
    api_key: str = Field(..., description="DIA API key")
    username: str = Field(..., description="DIA username")  
    password: str = Field(..., description="DIA password")
    disconnect_same_user: bool = Field(default=True, description="Disconnect same user on login")


class DIASyncRequest(BaseModel):
    """DIA sync request"""
    firma_kodu: int = Field(..., description="Firma kodu")
    donem_kodu: int = Field(default=1, description="Dönem kodu")
    modules: List[str] = Field(default=["cari_kartlar"], description="Modules to sync")
    limit: Optional[int] = Field(default=None, ge=1, le=1000, description="Sync limit")


class DIACariKartRequest(BaseModel):
    """DIA cari kart request"""
    firma_kodu: int
    donem_kodu: int = 1
    carikartkodu: str = Field(..., max_length=50)
    unvan: str = Field(..., max_length=250)
    carikarttipi: str = Field(..., regex="^(AL|SAT|ALSAT)$")
    verginumarasi: Optional[str] = Field(None, max_length=50)
    vergidairesi: Optional[str] = Field(None, max_length=100)


class DIAQueryRequest(BaseModel):
    """DIA query request"""
    firma_kodu: Optional[int] = None
    filters: Optional[Dict[str, Any]] = Field(default_factory=dict)
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)


# Dependency functions
async def get_dia_connector(
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> DIAConnector:
    """Get DIA connector for current tenant"""
    try:
        tenant_id = current_user["tenant_id"]
        
        # Get DIA config for tenant
        config_result = await tenant_service.get_integration_config(tenant_id, "dia")
        if not config_result["success"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "dia_not_configured",
                    "message": "DIA entegrasyonu yapılandırılmamış",
                    "message_en": "DIA integration not configured"
                }
            )
        
        config_data = config_result["config"]
        dia_config = DIAConfig(
            server_code=config_data["server_code"],
            api_key=config_data["api_key"],
            username=config_data["username"],
            password=config_data["password"],
            disconnect_same_user=config_data.get("disconnect_same_user", True)
        )
        
        return DIAConnector(dia_config)
        
    except Exception as e:
        logger.error("Failed to create DIA connector", error=str(e), tenant_id=current_user.get("tenant_id"))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "connector_creation_failed",
                "message": "DIA connector oluşturulamadı",
                "message_en": "Failed to create DIA connector"
            }
        )


async def get_dia_service(
    connector: DIAConnector = Depends(get_dia_connector)
) -> DIAService:
    """Get DIA service"""
    return DIAService(connector)


# API Endpoints
@router.post("/test-connection")
async def test_dia_connection(
    connector: DIAConnector = Depends(get_dia_connector),
    current_user: Dict[str, Any] = Depends(require_permissions(["integrations:read"]))
):
    """
    Test DIA connection
    """
    try:
        async with connector:
            result = await connector.test_connection()
            
            return {
                "success": result.success,
                "data": result.data,
                "message": result.message_tr,
                "message_en": result.message_en,
                "error": result.error
            }
            
    except Exception as e:
        logger.error("DIA connection test failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "connection_test_failed",
                "message": "Bağlantı testi başarısız",
                "message_en": "Connection test failed"
            }
        )


@router.post("/setup")
async def setup_dia_integration(
    request: DIAConnectionRequest,
    current_user: Dict[str, Any] = Depends(require_permissions(["integrations:write"]))
):
    """
    Setup DIA integration for current tenant
    """
    try:
        tenant_id = current_user["tenant_id"]
        
        # Test connection first
        test_config = DIAConfig(
            server_code=request.server_code,
            api_key=request.api_key,
            username=request.username,
            password=request.password,
            disconnect_same_user=request.disconnect_same_user
        )
        
        async with DIAConnector(test_config) as connector:
            test_result = await connector.test_connection()
            
            if not test_result.success:
                return {
                    "success": False,
                    "error": test_result.error,
                    "message": "DIA bağlantı testi başarısız",
                    "message_en": "DIA connection test failed"
                }
        
        # Save configuration
        config_data = {
            "server_code": request.server_code,
            "api_key": request.api_key,
            "username": request.username,
            "password": request.password,  # Should be encrypted in production
            "disconnect_same_user": request.disconnect_same_user,
            "setup_at": "utcnow()"
        }
        
        save_result = await tenant_service.save_integration_config(
            tenant_id, 
            "dia", 
            config_data
        )
        
        if save_result["success"]:
            return {
                "success": True,
                "message": "DIA entegrasyonu başarıyla kuruldu",
                "message_en": "DIA integration setup successful",
                "data": {
                    "server_code": request.server_code,
                    "username": request.username,
                    "setup_at": config_data["setup_at"]
                }
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "setup_failed",
                    "message": "Kurulum kaydedilemedi",
                    "message_en": "Failed to save setup"
                }
            )
            
    except Exception as e:
        logger.error("DIA setup failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "setup_error",
                "message": "Kurulum sırasında hata oluştu",
                "message_en": "Error during setup"
            }
        )


@router.get("/info")
async def get_dia_info(
    connector: DIAConnector = Depends(get_dia_connector),
    current_user: Dict[str, Any] = Depends(require_permissions(["integrations:read"]))
):
    """
    Get DIA system information
    """
    try:
        async with connector:
            # Get kontör info
            kontor_result = await connector.get_kontor_info()
            
            # Get firma/dönem list
            firma_result = await connector.get_firma_donem_list()
            
            # Get available actions
            actions = connector.get_available_actions()
            
            # Get connector stats
            stats = connector.get_stats()
            
            return {
                "success": True,
                "data": {
                    "kontor_info": kontor_result.data if kontor_result.success else None,
                    "firma_donem": firma_result.data if firma_result.success else None,
                    "available_actions": actions,
                    "connector_stats": stats
                },
                "message": "DIA bilgileri alındı",
                "message_en": "DIA information retrieved"
            }
            
    except Exception as e:
        logger.error("Get DIA info failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "info_error",
                "message": "Bilgi alınırken hata oluştu",
                "message_en": "Error getting information"
            }
        )


@router.post("/sync")
async def sync_dia_data(
    request: DIASyncRequest,
    dia_service: DIAService = Depends(get_dia_service),
    current_user: Dict[str, Any] = Depends(require_permissions(["integrations:write"]))
):
    """
    Sync data from DIA to local database
    """
    try:
        tenant_id = UUID(current_user["tenant_id"])
        results = {}
        
        # Sync requested modules
        if "cari_kartlar" in request.modules:
            logger.info("Syncing cari kartlar", tenant_id=str(tenant_id))
            result = await dia_service.sync_cari_kartlar(
                tenant_id=tenant_id,
                firma_kodu=request.firma_kodu,
                donem_kodu=request.donem_kodu,
                limit=request.limit
            )
            results["cari_kartlar"] = {
                "success": result.success,
                "data": result.data,
                "error": result.error
            }
        
        if "stok_kartlar" in request.modules:
            logger.info("Syncing stok kartlar", tenant_id=str(tenant_id))
            result = await dia_service.sync_stok_kartlar(
                tenant_id=tenant_id,
                firma_kodu=request.firma_kodu,
                donem_kodu=request.donem_kodu,
                limit=request.limit
            )
            results["stok_kartlar"] = {
                "success": result.success,
                "data": result.data,
                "error": result.error
            }
        
        # Check if all syncs were successful
        all_success = all(r["success"] for r in results.values())
        
        return {
            "success": all_success,
            "data": {
                "tenant_id": str(tenant_id),
                "firma_kodu": request.firma_kodu,
                "donem_kodu": request.donem_kodu,
                "modules": request.modules,
                "results": results
            },
            "message": "Senkronizasyon tamamlandı" if all_success else "Senkronizasyon kısmen başarılı",
            "message_en": "Synchronization completed" if all_success else "Synchronization partially successful"
        }
        
    except Exception as e:
        logger.error("DIA sync failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "sync_error",
                "message": "Senkronizasyon sırasında hata oluştu",
                "message_en": "Error during synchronization"
            }
        )


@router.get("/sync-status")
async def get_sync_status(
    dia_service: DIAService = Depends(get_dia_service),
    current_user: Dict[str, Any] = Depends(require_permissions(["integrations:read"]))
):
    """
    Get synchronization status
    """
    try:
        tenant_id = UUID(current_user["tenant_id"])
        result = await dia_service.get_sync_status(tenant_id)
        
        return {
            "success": result.success,
            "data": result.data,
            "message": result.message_tr,
            "message_en": result.message_en,
            "error": result.error
        }
        
    except Exception as e:
        logger.error("Get sync status failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "status_error",
                "message": "Durum sorgulanamadı",
                "message_en": "Failed to query status"
            }
        )


# Cari Kart Endpoints
@router.get("/cari-kartlar")
async def list_cari_kartlar(
    query: DIAQueryRequest = Depends(),
    dia_service: DIAService = Depends(get_dia_service),
    current_user: Dict[str, Any] = Depends(require_permissions(["integrations:read"]))
):
    """
    List cari kartlar from local database
    """
    try:
        tenant_id = UUID(current_user["tenant_id"])
        result = await dia_service.get_cari_kartlar(
            tenant_id=tenant_id,
            firma_kodu=query.firma_kodu,
            limit=query.limit,
            offset=query.offset,
            filters=query.filters
        )
        
        return {
            "success": result.success,
            "data": result.data,
            "message": result.message_tr,
            "message_en": result.message_en,
            "error": result.error
        }
        
    except Exception as e:
        logger.error("List cari kartlar failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "list_error",
                "message": "Cari kartlar listelenemedi",
                "message_en": "Failed to list cari kartlar"
            }
        )


@router.post("/cari-kartlar")
async def create_cari_kart(
    request: DIACariKartRequest,
    dia_service: DIAService = Depends(get_dia_service),
    current_user: Dict[str, Any] = Depends(require_permissions(["integrations:write"]))
):
    """
    Create new cari kart in DIA
    """
    try:
        tenant_id = UUID(current_user["tenant_id"])
        cari_data = request.dict(exclude={"firma_kodu", "donem_kodu"})
        
        result = await dia_service.create_cari_kart(
            tenant_id=tenant_id,
            firma_kodu=request.firma_kodu,
            donem_kodu=request.donem_kodu,
            cari_data=cari_data
        )
        
        if result.success:
            return {
                "success": True,
                "data": result.data,
                "message": result.message_tr,
                "message_en": result.message_en
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": result.error_code,
                    "message": result.message_tr or result.error,
                    "message_en": result.message_en or result.error
                }
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Create cari kart failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "create_error",
                "message": "Cari kart oluşturulamadı",
                "message_en": "Failed to create cari kart"
            }
        )


@router.get("/status")
async def get_dia_status(
    current_user: Dict[str, Any] = Depends(require_permissions(["integrations:read"]))
):
    """
    Get DIA integration status
    """
    try:
        tenant_id = current_user["tenant_id"]
        
        # Check if DIA is configured
        config_result = await tenant_service.get_integration_config(tenant_id, "dia")
        configured = config_result["success"]
        
        status_info = {
            "integration": "dia",
            "configured": configured,
            "endpoints": {
                "/test-connection": "Test DIA connection",
                "/setup": "Setup DIA integration",
                "/info": "Get DIA system information",
                "/sync": "Sync data from DIA",
                "/sync-status": "Get synchronization status",
                "/cari-kartlar": "Cari kart operations"
            },
            "features": [
                "Session-based authentication",
                "Multi-company support",
                "Real-time data synchronization", 
                "CRUD operations",
                "Smart foreign key resolution",
                "Kontör tracking",
                "Error handling and retry logic"
            ]
        }
        
        if configured:
            config = config_result["config"]
            status_info["config"] = {
                "server_code": config.get("server_code"),
                "username": config.get("username"),
                "setup_at": config.get("setup_at")
            }
        
        return {
            "success": True,
            "data": status_info,
            "message": "DIA durumu alındı",
            "message_en": "DIA status retrieved"
        }
        
    except Exception as e:
        logger.error("Get DIA status failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "status_error",
                "message": "Durum bilgisi alınamadı",
                "message_en": "Failed to get status information"
            }
        )