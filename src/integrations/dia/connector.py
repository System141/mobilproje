"""
DIA ERP Connector Implementation
"""

import asyncio
import json
from typing import Dict, Any, Optional, List, Union
from datetime import datetime, timedelta
from decimal import Decimal
from urllib.parse import urljoin

import structlog
from pydantic import ValidationError

from src.integrations.base_connector import (
    BaseConnector, 
    ConnectorResponse, 
    AuthenticationError,
    ConnectorError
)
from .config import DIAConfig, DIAModuleConfig
from .models import (
    DIAResponse, 
    DIALoginResponse, 
    DIAFirmaDonem,
    DIACariKart,
    DIAStokKart,
    DIAFaturaFisi,
    DIAListRequest,
    DIACreateRequest,
    DIAUpdateRequest,
    DIADeleteRequest
)


logger = structlog.get_logger(__name__)


class DIAConnector(BaseConnector):
    """
    DIA ERP System Connector
    
    Provides integration with DIA ERP system via JSON REST Web Service API
    """
    
    def __init__(self, config: DIAConfig, module_config: Optional[DIAModuleConfig] = None):
        super().__init__(config)
        self.dia_config = config
        self.module_config = module_config or DIAModuleConfig()
        
        # Session management
        self._session_id: Optional[str] = None
        self._session_expires_at: Optional[datetime] = None
        self._firma_donem_cache: Dict[str, Any] = {}
        
        # Module endpoints
        self._endpoints = {
            # Authentication
            "login": "/SIS/json",
            "logout": "/SIS/json", 
            "kontor_sorgula": "/SIS/json",
            "yetkili_firma_donem": "/SIS/json",
            
            # SCF Module
            "scf_carikart_listele": "/SCF/json",
            "scf_carikart_getir": "/SCF/json",
            "scf_carikart_ekle": "/SCF/json",
            "scf_carikart_guncelle": "/SCF/json",
            "scf_carikart_sil": "/SCF/json",
            
            "scf_stokkart_listele": "/SCF/json",
            "scf_stokkart_getir": "/SCF/json",
            "scf_stokkart_ekle": "/SCF/json",
            "scf_stokkart_guncelle": "/SCF/json",
            "scf_stokkart_sil": "/SCF/json",
            
            "scf_faturafisi_listele": "/SCF/json",
            "scf_faturafisi_getir": "/SCF/json",
            "scf_faturafisi_ekle": "/SCF/json",
            "scf_faturafisi_guncelle": "/SCF/json",
            "scf_faturafisi_sil": "/SCF/json",
        }
        
        self.logger = structlog.get_logger("connector.dia")
    
    async def authenticate(self) -> bool:
        """
        DIA authentication with session management
        """
        try:
            login_data = {
                "login": {
                    "username": self.dia_config.username,
                    "password": self.dia_config.password,
                    "disconnect_same_user": str(self.dia_config.disconnect_same_user),
                    "params": {"apikey": self.dia_config.api_key}
                }
            }
            
            response = await self._make_request(
                method="POST",
                endpoint=self._endpoints["login"],
                json=login_data,
                auth_required=False
            )
            
            if not response.success:
                self.logger.error("DIA authentication failed", error=response.error)
                return False
            
            # Parse DIA response
            try:
                dia_response = DIALoginResponse(**response.data)
            except ValidationError as e:
                self.logger.error("Invalid DIA login response", error=str(e), data=response.data)
                return False
            
            if not dia_response.is_success:
                self.logger.error("DIA login rejected", code=dia_response.code, message=dia_response.msg)
                return False
            
            # Store session info
            self._session_id = dia_response.session_id
            self._session_expires_at = datetime.utcnow() + timedelta(seconds=self.dia_config.session_timeout)
            self._authenticated = True
            
            self.logger.info(
                "DIA authentication successful",
                session_id=self._session_id[:10] + "..." if self._session_id else None,
                expires_at=self._session_expires_at
            )
            
            # Load firma/dönem bilgileri
            await self._load_firma_donem_cache()
            
            return True
            
        except Exception as e:
            self.logger.error("DIA authentication error", error=str(e))
            return False
    
    async def test_connection(self) -> ConnectorResponse:
        """
        Test DIA connection by checking kontör
        """
        try:
            if not self._authenticated:
                success = await self.authenticate()
                if not success:
                    return ConnectorResponse(
                        success=False,
                        error="Authentication failed",
                        error_code="AUTH_FAILED",
                        message_tr="Kimlik doğrulama başarısız",
                        message_en="Authentication failed"
                    )
            
            # Test with kontör sorgula
            kontor_data = {
                "sis_kontor_sorgula": {
                    "session_id": self._session_id
                }
            }
            
            response = await self._make_request(
                method="POST",
                endpoint=self._endpoints["kontor_sorgula"],
                json=kontor_data
            )
            
            if response.success:
                return ConnectorResponse(
                    success=True,
                    data={
                        "status": "connected",
                        "session_active": True,
                        "kontor_info": response.data
                    },
                    message_tr="DIA bağlantısı başarılı",
                    message_en="DIA connection successful"
                )
            else:
                return ConnectorResponse(
                    success=False,
                    error=response.error,
                    error_code="CONNECTION_FAILED",
                    message_tr="DIA bağlantı testi başarısız",
                    message_en="DIA connection test failed"
                )
                
        except Exception as e:
            self.logger.error("DIA connection test failed", error=str(e))
            return ConnectorResponse(
                success=False,
                error=str(e),
                error_code="TEST_ERROR",
                message_tr="Bağlantı testi sırasında hata",
                message_en="Error during connection test"
            )
    
    def get_available_actions(self) -> List[str]:
        """
        Return available DIA actions
        """
        actions = [
            "authenticate",
            "test_connection", 
            "get_kontor_info",
            "get_firma_donem_list"
        ]
        
        if self.module_config.scf_enabled:
            actions.extend([
                "scf_cari_listele",
                "scf_cari_getir", 
                "scf_cari_ekle",
                "scf_cari_guncelle",
                "scf_cari_sil",
                "scf_stok_listele",
                "scf_stok_getir",
                "scf_stok_ekle", 
                "scf_stok_guncelle",
                "scf_stok_sil",
                "scf_fatura_listele",
                "scf_fatura_getir",
                "scf_fatura_ekle",
                "scf_fatura_guncelle",
                "scf_fatura_sil"
            ])
        
        return actions
    
    async def execute_action(self, action: str, payload: Dict[str, Any]) -> ConnectorResponse:
        """
        Execute DIA action
        """
        try:
            self.logger.info("Executing DIA action", action=action)
            
            # Route to appropriate handler
            if action == "authenticate":
                success = await self.authenticate()
                return ConnectorResponse(
                    success=success,
                    data={"authenticated": success},
                    message_tr="Kimlik doğrulama tamamlandı" if success else "Kimlik doğrulama başarısız",
                    message_en="Authentication completed" if success else "Authentication failed"
                )
            
            elif action == "test_connection":
                return await self.test_connection()
            
            elif action == "get_kontor_info":
                return await self.get_kontor_info()
            
            elif action == "get_firma_donem_list":
                return await self.get_firma_donem_list()
            
            # SCF Module actions
            elif action.startswith("scf_cari_"):
                return await self._execute_scf_cari_action(action, payload)
            
            elif action.startswith("scf_stok_"):
                return await self._execute_scf_stok_action(action, payload)
            
            elif action.startswith("scf_fatura_"):
                return await self._execute_scf_fatura_action(action, payload)
            
            else:
                return ConnectorResponse(
                    success=False,
                    error=f"Unknown action: {action}",
                    error_code="UNKNOWN_ACTION",
                    message_tr="Bilinmeyen işlem",
                    message_en="Unknown action"
                )
                
        except Exception as e:
            self.logger.error("Action execution failed", action=action, error=str(e))
            return ConnectorResponse(
                success=False,
                error=str(e),
                error_code="ACTION_ERROR",
                message_tr="İşlem sırasında hata oluştu",
                message_en="Error during action execution"
            )
    
    async def get_kontor_info(self) -> ConnectorResponse:
        """
        Get kontör information
        """
        await self.ensure_authenticated()
        
        kontor_data = {
            "sis_kontor_sorgula": {
                "session_id": self._session_id
            }
        }
        
        response = await self._make_request(
            method="POST",
            endpoint=self._endpoints["kontor_sorgula"], 
            json=kontor_data
        )
        
        if response.success:
            try:
                dia_response = DIAResponse(**response.data)
                if dia_response.is_success:
                    return ConnectorResponse(
                        success=True,
                        data=dia_response.data,
                        message_tr="Kontör bilgisi alındı",
                        message_en="Kontör information retrieved"
                    )
                else:
                    return ConnectorResponse(
                        success=False,
                        error=dia_response.msg,
                        error_code=dia_response.code,
                        message_tr="Kontör bilgisi alınamadı",
                        message_en="Failed to get kontör information"
                    )
            except ValidationError as e:
                return ConnectorResponse(
                    success=False,
                    error=str(e),
                    error_code="PARSE_ERROR"
                )
        
        return response
    
    async def get_firma_donem_list(self) -> ConnectorResponse:
        """
        Get authorized firma and dönem list
        """
        await self.ensure_authenticated()
        
        yetkiler_data = {
            "sis_yetkili_firma_donem_sube_depo": {
                "session_id": self._session_id
            }
        }
        
        response = await self._make_request(
            method="POST",
            endpoint=self._endpoints["yetkili_firma_donem"],
            json=yetkiler_data
        )
        
        if response.success:
            try:
                dia_response = DIAResponse(**response.data)
                if dia_response.is_success:
                    return ConnectorResponse(
                        success=True,
                        data=dia_response.data,
                        message_tr="Yetki bilgileri alındı",
                        message_en="Authorization information retrieved"
                    )
                else:
                    return ConnectorResponse(
                        success=False,
                        error=dia_response.msg,
                        error_code=dia_response.code
                    )
            except ValidationError as e:
                return ConnectorResponse(
                    success=False,
                    error=str(e),
                    error_code="PARSE_ERROR"
                )
        
        return response
    
    async def _load_firma_donem_cache(self):
        """
        Load and cache firma/dönem information
        """
        try:
            result = await self.get_firma_donem_list()
            if result.success:
                self._firma_donem_cache = result.data
                self.logger.info("Firma/dönem cache loaded", cache_size=len(self._firma_donem_cache))
        except Exception as e:
            self.logger.warning("Failed to load firma/dönem cache", error=str(e))
    
    def get_session_id(self) -> Optional[str]:
        """
        Get current session ID
        """
        if self._is_session_expired():
            return None
        return self._session_id
    
    def _is_session_expired(self) -> bool:
        """
        Check if session has expired
        """
        if not self._session_expires_at:
            return True
        return datetime.utcnow() >= self._session_expires_at
    
    async def ensure_authenticated(self):
        """
        Ensure connector is authenticated with session check
        """
        if not self._authenticated or self._is_session_expired():
            success = await self.authenticate()
            if not success:
                raise AuthenticationError("DIA authentication failed")
    
    async def logout(self) -> bool:
        """
        Logout from DIA
        """
        if not self._session_id:
            return True
        
        try:
            logout_data = {
                "logout": {
                    "session_id": self._session_id
                }
            }
            
            await self._make_request(
                method="POST",
                endpoint=self._endpoints["logout"],
                json=logout_data,
                auth_required=False
            )
            
            self._session_id = None
            self._session_expires_at = None
            self._authenticated = False
            self._firma_donem_cache.clear()
            
            self.logger.info("DIA logout successful")
            return True
            
        except Exception as e:
            self.logger.error("DIA logout failed", error=str(e))
            return False
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Clean logout on context exit
        """
        await self.logout()
        await super().__aexit__(exc_type, exc_val, exc_tb)
    
    # SCF Module specific methods will be implemented in the next part
    async def _execute_scf_cari_action(self, action: str, payload: Dict[str, Any]) -> ConnectorResponse:
        """Execute SCF Cari actions"""
        # This will be implemented in the service layer
        return ConnectorResponse(
            success=False,
            error="SCF Cari actions not implemented yet",
            error_code="NOT_IMPLEMENTED"
        )
    
    async def _execute_scf_stok_action(self, action: str, payload: Dict[str, Any]) -> ConnectorResponse:
        """Execute SCF Stok actions"""
        # This will be implemented in the service layer  
        return ConnectorResponse(
            success=False,
            error="SCF Stok actions not implemented yet",
            error_code="NOT_IMPLEMENTED"
        )
    
    async def _execute_scf_fatura_action(self, action: str, payload: Dict[str, Any]) -> ConnectorResponse:
        """Execute SCF Fatura actions"""
        # This will be implemented in the service layer
        return ConnectorResponse(
            success=False,
            error="SCF Fatura actions not implemented yet", 
            error_code="NOT_IMPLEMENTED"
        )