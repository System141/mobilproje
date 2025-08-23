"""
Netgsm SMS and WhatsApp connector for Turkish Business Integration Platform
"""

import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from pydantic import BaseModel, Field, validator
import structlog

from src.integrations.base_connector import (
    BaseConnector, 
    ConnectorConfig, 
    ConnectorResponse,
    AuthenticationError
)

logger = structlog.get_logger(__name__)


class NetgsmConfig(ConnectorConfig):
    """Netgsm specific configuration"""
    
    base_url: str = "https://api.netgsm.com.tr"
    user_code: str
    password: str
    sender_name: str = Field(default="FIRMA", max_length=11)
    
    # SMS settings
    sms_encoding: str = "TR"  # TR for Turkish characters
    sms_validity: int = Field(default=2880, ge=1, le=2880)  # Minutes (max 48 hours)
    
    # WhatsApp settings (requires Netasistan Plus)
    whatsapp_enabled: bool = False
    whatsapp_api_url: str = "https://api.netasistan.com/whatsapp"
    whatsapp_token: Optional[str] = None
    
    @validator("sender_name")
    def validate_sender_name(cls, v):
        """Validate sender name for Turkish SMS regulations"""
        if not re.match(r"^[A-Z0-9]{1,11}$", v):
            raise ValueError("Sender name must be 1-11 uppercase alphanumeric characters")
        return v


class SMSMessage(BaseModel):
    """SMS message model"""
    
    phone: str = Field(..., description="Turkish phone number")
    message: str = Field(..., max_length=1520, description="SMS content")
    sender: Optional[str] = Field(None, max_length=11, description="Sender name")
    
    @validator("phone")
    def validate_phone(cls, v):
        """Validate Turkish phone number format"""
        # Remove all non-digit characters
        phone = re.sub(r"[^\d]", "", v)
        
        # Check if it starts with country code
        if phone.startswith("90"):
            phone = phone[2:]
        elif phone.startswith("0"):
            phone = phone[1:]
        
        # Validate Turkish mobile format (5XX XXX XXXX)
        if not re.match(r"^5\d{9}$", phone):
            raise ValueError("Invalid Turkish mobile number format")
        
        return f"90{phone}"  # Return with country code
    
    @validator("message")
    def validate_message(cls, v):
        """Validate SMS message content"""
        if len(v.strip()) == 0:
            raise ValueError("Message cannot be empty")
        return v


class WhatsAppMessage(BaseModel):
    """WhatsApp message model"""
    
    phone: str = Field(..., description="Phone number with country code")
    message_type: str = Field(default="text", description="Message type")
    content: Dict[str, Any] = Field(..., description="Message content")
    
    @validator("phone")
    def validate_phone(cls, v):
        """Validate phone number for WhatsApp"""
        phone = re.sub(r"[^\d]", "", v)
        if phone.startswith("90"):
            phone = phone[2:]
        elif phone.startswith("0"):
            phone = phone[1:]
        
        if not re.match(r"^5\d{9}$", phone):
            raise ValueError("Invalid Turkish mobile number format")
        
        return f"90{phone}"


class NetgsmConnector(BaseConnector):
    """
    Netgsm SMS and WhatsApp connector
    
    Supports:
    - SMS sending via Netgsm API
    - WhatsApp messaging via Netasistan
    - Delivery reports
    - Balance checking
    - Contact management
    """
    
    def __init__(self, config: NetgsmConfig):
        super().__init__(config)
        self.config: NetgsmConfig = config
        self.balance: Optional[float] = None
        self.last_balance_check: Optional[datetime] = None
    
    async def authenticate(self) -> bool:
        """
        Test authentication with Netgsm API
        
        Returns:
            bool: True if authentication successful
        """
        try:
            response = await self._make_request(
                method="GET",
                endpoint="/balance/list/get",
                params={
                    "usercode": self.config.user_code,
                    "password": self.config.password
                },
                auth_required=False
            )
            
            if response.success and response.data and "00" in str(response.data):
                self._authenticated = True
                
                # Parse balance from response
                try:
                    balance_text = str(response.data)
                    # Format: "00 123.45" where 123.45 is the balance
                    if " " in balance_text:
                        self.balance = float(balance_text.split(" ")[1])
                        self.last_balance_check = datetime.utcnow()
                except (ValueError, IndexError):
                    pass
                
                self.logger.info("Authentication successful", balance=self.balance)
                return True
            else:
                self._authenticated = False
                self.logger.error("Authentication failed", response=response.data)
                return False
                
        except Exception as e:
            self._authenticated = False
            self.logger.error("Authentication error", error=str(e))
            return False
    
    async def test_connection(self) -> ConnectorResponse:
        """Test connection to Netgsm API"""
        try:
            # Check balance to test connection
            balance_response = await self.check_balance()
            
            if balance_response.success:
                return ConnectorResponse(
                    success=True,
                    data={
                        "service": "Netgsm",
                        "status": "connected",
                        "balance": self.balance,
                        "features": {
                            "sms": True,
                            "whatsapp": self.config.whatsapp_enabled,
                            "delivery_reports": True
                        }
                    },
                    message_tr="Netgsm bağlantısı başarılı",
                    message_en="Netgsm connection successful"
                )
            else:
                return ConnectorResponse(
                    success=False,
                    error="Connection test failed",
                    error_code="CONNECTION_TEST_FAILED",
                    message_tr="Netgsm bağlantı testi başarısız",
                    message_en="Netgsm connection test failed"
                )
                
        except Exception as e:
            return ConnectorResponse(
                success=False,
                error=str(e),
                error_code="CONNECTION_ERROR",
                message_tr="Bağlantı hatası",
                message_en="Connection error"
            )
    
    def get_available_actions(self) -> List[str]:
        """Get list of supported actions"""
        actions = [
            "send_sms",
            "check_balance", 
            "get_delivery_report",
            "get_sms_history",
            "validate_phone"
        ]
        
        if self.config.whatsapp_enabled:
            actions.extend([
                "send_whatsapp",
                "get_whatsapp_status"
            ])
        
        return actions
    
    async def execute_action(self, action: str, payload: Dict[str, Any]) -> ConnectorResponse:
        """Execute specific action"""
        try:
            if action == "send_sms":
                message = SMSMessage(**payload)
                return await self.send_sms(message)
            
            elif action == "send_whatsapp":
                if not self.config.whatsapp_enabled:
                    return ConnectorResponse(
                        success=False,
                        error="WhatsApp feature not enabled",
                        error_code="FEATURE_DISABLED",
                        message_tr="WhatsApp özelliği aktif değil",
                        message_en="WhatsApp feature not enabled"
                    )
                
                message = WhatsAppMessage(**payload)
                return await self.send_whatsapp(message)
            
            elif action == "check_balance":
                return await self.check_balance()
            
            elif action == "get_delivery_report":
                message_id = payload.get("message_id")
                if not message_id:
                    return ConnectorResponse(
                        success=False,
                        error="Message ID required",
                        error_code="MISSING_PARAMETER"
                    )
                return await self.get_delivery_report(message_id)
            
            elif action == "validate_phone":
                phone = payload.get("phone")
                if not phone:
                    return ConnectorResponse(
                        success=False,
                        error="Phone number required",
                        error_code="MISSING_PARAMETER"
                    )
                return await self.validate_phone(phone)
            
            else:
                return ConnectorResponse(
                    success=False,
                    error=f"Action '{action}' not supported",
                    error_code="UNSUPPORTED_ACTION",
                    message_tr=f"'{action}' işlemi desteklenmiyor",
                    message_en=f"Action '{action}' not supported"
                )
                
        except Exception as e:
            self.logger.error("Action execution error", action=action, error=str(e))
            return ConnectorResponse(
                success=False,
                error=str(e),
                error_code="EXECUTION_ERROR",
                message_tr="İşlem çalıştırma hatası",
                message_en="Action execution error"
            )
    
    async def send_sms(self, message: SMSMessage) -> ConnectorResponse:
        """
        Send SMS via Netgsm API
        
        Args:
            message: SMS message to send
            
        Returns:
            ConnectorResponse: Send result
        """
        try:
            # Prepare parameters
            params = {
                "usercode": self.config.user_code,
                "password": self.config.password,
                "gsmno": message.phone,
                "message": message.message,
                "msgheader": message.sender or self.config.sender_name,
                "filter": "0",  # No filtering
                "encoding": self.config.sms_encoding
            }
            
            response = await self._make_request(
                method="GET",
                endpoint="/sms/send/get",
                params=params
            )
            
            if response.success and response.data:
                response_text = str(response.data)
                
                # Parse Netgsm response codes
                if response_text.startswith("00"):
                    # Success - extract message ID
                    parts = response_text.split(" ")
                    message_id = parts[1] if len(parts) > 1 else None
                    
                    return ConnectorResponse(
                        success=True,
                        data={
                            "message_id": message_id,
                            "phone": message.phone,
                            "status": "sent",
                            "cost": self._calculate_sms_cost(message.message),
                            "response": response_text
                        },
                        message_tr="SMS başarıyla gönderildi",
                        message_en="SMS sent successfully"
                    )
                else:
                    # Error - map error codes
                    error_message = self._map_sms_error(response_text)
                    return ConnectorResponse(
                        success=False,
                        error=error_message,
                        error_code=f"SMS_ERROR_{response_text}",
                        data={"response": response_text},
                        message_tr=error_message,
                        message_en=error_message
                    )
            
            return ConnectorResponse(
                success=False,
                error="Invalid response from Netgsm",
                error_code="INVALID_RESPONSE",
                message_tr="Netgsm'den geçersiz yanıt",
                message_en="Invalid response from Netgsm"
            )
            
        except Exception as e:
            self.logger.error("SMS send error", error=str(e))
            return ConnectorResponse(
                success=False,
                error=str(e),
                error_code="SMS_SEND_ERROR",
                message_tr="SMS gönderme hatası",
                message_en="SMS send error"
            )
    
    async def send_whatsapp(self, message: WhatsAppMessage) -> ConnectorResponse:
        """
        Send WhatsApp message via Netasistan API
        
        Args:
            message: WhatsApp message to send
            
        Returns:
            ConnectorResponse: Send result
        """
        if not self.config.whatsapp_enabled or not self.config.whatsapp_token:
            return ConnectorResponse(
                success=False,
                error="WhatsApp not configured",
                error_code="WHATSAPP_NOT_CONFIGURED",
                message_tr="WhatsApp yapılandırılmamış",
                message_en="WhatsApp not configured"
            )
        
        try:
            headers = {
                "Authorization": f"Bearer {self.config.whatsapp_token}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "to": message.phone,
                "type": message.message_type,
                **message.content
            }
            
            # Use different base URL for WhatsApp
            original_base_url = self.client.base_url if self.client else None
            
            if self.client:
                self.client.base_url = self.config.whatsapp_api_url
            
            try:
                response = await self._make_request(
                    method="POST",
                    endpoint="/send",
                    json=payload,
                    headers=headers
                )
            finally:
                # Restore original base URL
                if self.client and original_base_url:
                    self.client.base_url = original_base_url
            
            if response.success:
                return ConnectorResponse(
                    success=True,
                    data=response.data,
                    message_tr="WhatsApp mesajı başarıyla gönderildi",
                    message_en="WhatsApp message sent successfully"
                )
            else:
                return response
                
        except Exception as e:
            self.logger.error("WhatsApp send error", error=str(e))
            return ConnectorResponse(
                success=False,
                error=str(e),
                error_code="WHATSAPP_SEND_ERROR",
                message_tr="WhatsApp gönderme hatası",
                message_en="WhatsApp send error"
            )
    
    async def check_balance(self) -> ConnectorResponse:
        """Check SMS balance"""
        try:
            response = await self._make_request(
                method="GET",
                endpoint="/balance/list/get",
                params={
                    "usercode": self.config.user_code,
                    "password": self.config.password
                }
            )
            
            if response.success and response.data:
                response_text = str(response.data)
                
                if response_text.startswith("00"):
                    # Parse balance
                    parts = response_text.split(" ")
                    balance = float(parts[1]) if len(parts) > 1 else 0.0
                    
                    self.balance = balance
                    self.last_balance_check = datetime.utcnow()
                    
                    return ConnectorResponse(
                        success=True,
                        data={
                            "balance": balance,
                            "currency": "TL",
                            "last_updated": self.last_balance_check.isoformat()
                        },
                        message_tr=f"Bakiye: {balance} TL",
                        message_en=f"Balance: {balance} TL"
                    )
                else:
                    error_message = self._map_balance_error(response_text)
                    return ConnectorResponse(
                        success=False,
                        error=error_message,
                        error_code=f"BALANCE_ERROR_{response_text}",
                        message_tr=error_message,
                        message_en=error_message
                    )
            
            return ConnectorResponse(
                success=False,
                error="Could not retrieve balance",
                error_code="BALANCE_RETRIEVE_ERROR",
                message_tr="Bakiye alınamadı",
                message_en="Could not retrieve balance"
            )
            
        except Exception as e:
            return ConnectorResponse(
                success=False,
                error=str(e),
                error_code="BALANCE_CHECK_ERROR",
                message_tr="Bakiye sorgulama hatası",
                message_en="Balance check error"
            )
    
    async def get_delivery_report(self, message_id: str) -> ConnectorResponse:
        """Get SMS delivery report"""
        try:
            response = await self._make_request(
                method="GET",
                endpoint="/sms/report",
                params={
                    "usercode": self.config.user_code,
                    "password": self.config.password,
                    "msgid": message_id
                }
            )
            
            if response.success:
                return ConnectorResponse(
                    success=True,
                    data={
                        "message_id": message_id,
                        "status": response.data,
                        "timestamp": datetime.utcnow().isoformat()
                    },
                    message_tr="Teslimat raporu alındı",
                    message_en="Delivery report retrieved"
                )
            else:
                return response
                
        except Exception as e:
            return ConnectorResponse(
                success=False,
                error=str(e),
                error_code="DELIVERY_REPORT_ERROR",
                message_tr="Teslimat raporu hatası",
                message_en="Delivery report error"
            )
    
    async def validate_phone(self, phone: str) -> ConnectorResponse:
        """Validate Turkish phone number format"""
        try:
            # Try to create SMSMessage to validate phone
            SMSMessage(phone=phone, message="test")
            
            return ConnectorResponse(
                success=True,
                data={
                    "phone": phone,
                    "is_valid": True,
                    "formatted": SMSMessage(phone=phone, message="test").phone
                },
                message_tr="Telefon numarası geçerli",
                message_en="Phone number is valid"
            )
            
        except ValueError as e:
            return ConnectorResponse(
                success=False,
                error=str(e),
                error_code="INVALID_PHONE",
                data={
                    "phone": phone,
                    "is_valid": False
                },
                message_tr="Geçersiz telefon numarası",
                message_en="Invalid phone number"
            )
    
    def _calculate_sms_cost(self, message: str) -> float:
        """Calculate SMS cost based on message length"""
        # Basic cost calculation (this should be configured per account)
        length = len(message)
        if length <= 160:
            return 0.05  # 5 kuruş per SMS
        else:
            # Multi-part SMS
            parts = (length + 152) // 153  # 153 chars per part for multi-part
            return 0.05 * parts
    
    def _map_sms_error(self, error_code: str) -> str:
        """Map Netgsm SMS error codes to Turkish messages"""
        error_map = {
            "01": "Mesaj gövdesi hatalı",
            "02": "Mesaj başlığı hatalı", 
            "03": "Kullanıcı adı veya şifre hatalı",
            "04": "Müşteri tanımlı başlık gönderilemez",
            "05": "Mesaj gönderim hatası",
            "06": "Yetersiz bakiye",
            "07": "Zaman aşımı hatası",
            "08": "Sistem hatası",
            "09": "Operatör hatası"
        }
        
        return error_map.get(error_code, f"Bilinmeyen hata: {error_code}")
    
    def _map_balance_error(self, error_code: str) -> str:
        """Map balance check error codes"""
        error_map = {
            "30": "Kullanıcı adı veya şifre hatalı",
            "40": "Sistem hatası"
        }
        
        return error_map.get(error_code, f"Bakiye sorgulama hatası: {error_code}")