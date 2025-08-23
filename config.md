# Claude Code Implementation Guide: Turkish Business Integration Platform

## Project Overview

A comprehensive implementation guide for building a FastAPI-based multi-tenant SaaS integration platform targeting Turkish SMEs, with full KVKK compliance, Turkish business system integrations, and modern cloud-native architecture.

## CLAUDE.md Configuration

```markdown
# Turkish Business Integration Platform

## Tech Stack
- Framework: FastAPI 0.104+ with Python 3.11
- Database: PostgreSQL 15 with Row-Level Security
- Cache: Redis 7.2 with Sentinel
- Queue: Apache Kafka 3.6
- Container: Docker 24 with Kubernetes 1.28
- Language: Python 3.11+ with type hints

## Project Structure
- src/: Main application code (domain-driven design)
- tests/: Test files mirroring src structure
- alembic/: Database migrations
- k8s/: Kubernetes manifests
- docker/: Docker configurations
- scripts/: Development and deployment scripts

## Commands
- Build: `docker-compose build`
- Test: `pytest --cov=src --cov-report=html`
- Lint: `ruff check --fix src/ tests/`
- Format: `black src/ tests/`
- Type Check: `mypy src/`
- Migrate: `alembic upgrade head`
- Run: `uvicorn src.main:app --reload`

## Code Style
- Use async/await for all I/O operations
- Follow PEP 8 with 88-char line length (Black)
- Type hints mandatory for all functions
- Pydantic for all data validation
- Domain-driven design patterns
- Turkish + English comments

## Workflow
- Feature branches from develop
- Run tests before committing
- Conventional commits (feat:, fix:, docs:)
- PR required for main branch
- Security scan before deployment

## Turkish Compliance
- KVKK data protection mandatory
- Turkish localization required
- E-invoice integration ready
- Local data residency enforced

## Do Not Touch
- alembic/versions/ (migrations)
- .env.production (secrets)
- k8s/secrets/ (sensitive configs)
```

## Project Structure

```
turkish-integration-platform/
├── CLAUDE.md                      # Claude Code configuration
├── .claude/                       # Claude-specific settings
│   ├── commands/                  # Custom slash commands
│   └── settings.json             # Tool permissions
├── src/
│   ├── __init__.py
│   ├── main.py                   # FastAPI app initialization
│   ├── config.py                 # Global configuration
│   ├── database.py               # Database connections
│   ├── core/                     # Core functionality
│   │   ├── security.py          # OAuth2/JWT implementation
│   │   ├── tenant.py            # Multi-tenant middleware
│   │   ├── kvkk.py              # KVKK compliance
│   │   └── dependencies.py      # Shared dependencies
│   ├── api/                      # API layer
│   │   ├── v1/
│   │   │   ├── auth.py         # Authentication endpoints
│   │   │   ├── tenants.py      # Tenant management
│   │   │   ├── integrations.py # Integration connectors
│   │   │   ├── workflows.py    # Workflow engine
│   │   │   └── webhooks.py     # Webhook handlers
│   │   └── gateway.py           # API gateway routing
│   ├── models/                   # Database models
│   │   ├── base.py              # Base model with tenant_id
│   │   ├── tenant.py            # Tenant model
│   │   ├── user.py              # User model
│   │   ├── integration.py       # Integration configs
│   │   └── workflow.py          # Workflow definitions
│   ├── schemas/                  # Pydantic schemas
│   │   ├── tenant.py
│   │   ├── auth.py
│   │   ├── integration.py
│   │   └── workflow.py
│   ├── services/                 # Business logic
│   │   ├── auth_service.py
│   │   ├── tenant_service.py
│   │   ├── integration_service.py
│   │   └── workflow_service.py
│   ├── integrations/            # Turkish system connectors
│   │   ├── base_connector.py
│   │   ├── netgsm/             # SMS service
│   │   ├── bulutfon/           # Phone system
│   │   ├── whatsapp/           # WhatsApp Business
│   │   ├── arvento/            # Vehicle tracking
│   │   ├── findeks/            # Credit scoring
│   │   ├── efatura/            # E-invoice
│   │   └── iyzico/             # Payment gateway
│   ├── workers/                 # Background workers
│   │   ├── kafka_consumer.py
│   │   ├── webhook_processor.py
│   │   └── workflow_executor.py
│   └── utils/                   # Utilities
│       ├── turkish.py          # Turkish localization
│       ├── cache.py            # Redis helpers
│       └── monitoring.py       # Metrics/logging
├── tests/                       # Test structure mirrors src/
├── alembic/                     # Database migrations
│   ├── alembic.ini
│   └── versions/
├── docker/
│   ├── Dockerfile.api          # Multi-stage API build
│   ├── Dockerfile.worker       # Worker container
│   └── docker-compose.yml      # Development stack
├── k8s/                         # Kubernetes manifests
│   ├── namespace.yaml
│   ├── configmap.yaml
│   ├── secrets.yaml
│   ├── deployment-api.yaml
│   ├── deployment-worker.yaml
│   ├── service.yaml
│   ├── ingress.yaml
│   └── hpa.yaml                # Horizontal pod autoscaler
├── scripts/
│   ├── setup_dev.sh           # Development setup
│   ├── create_tenant.py       # Tenant creation script
│   └── deploy.sh              # Deployment script
├── requirements/
│   ├── base.txt               # Core dependencies
│   ├── dev.txt                # Development tools
│   └── prod.txt               # Production extras
├── .env.example                # Environment template
├── pyproject.toml              # Poetry configuration
└── README.md                   # Project documentation
```

## Database Schema Design

```python
# src/models/base.py
from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
import uuid
from datetime import datetime

Base = declarative_base()

class TenantAwareModel(Base):
    __abstract__ = True
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# src/models/tenant.py
from sqlalchemy import Column, String, Boolean, JSON, Enum
from .base import Base

class Tenant(Base):
    __tablename__ = "tenants"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    subdomain = Column(String(63), unique=True, nullable=False)
    
    # Turkish compliance fields
    tax_number = Column(String(11))  # Vergi numarası
    tax_office = Column(String(255))  # Vergi dairesi
    kvkk_consent_date = Column(DateTime)
    verbis_registration = Column(String(255))
    
    # Subscription
    plan = Column(Enum("trial", "starter", "professional", "enterprise"))
    plan_limits = Column(JSON)  # {"api_calls": 10000, "workflows": 100}
    
    # Configuration
    settings = Column(JSON, default={})
    features = Column(JSON, default=[])
    is_active = Column(Boolean, default=True)
    
    # Turkish localization
    language = Column(String(5), default="tr-TR")
    timezone = Column(String(50), default="Europe/Istanbul")
    currency = Column(String(3), default="TRY")
```

## Multi-Tenant Implementation

```python
# src/core/tenant.py
from contextvars import ContextVar
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy import text

# Global tenant context
tenant_context: ContextVar[str] = ContextVar("tenant_context", default=None)

class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Extract tenant from subdomain or header
        host = request.headers.get("host", "")
        subdomain = host.split(".")[0] if "." in host else None
        tenant_id = request.headers.get("X-Tenant-ID") or subdomain
        
        if not tenant_id and request.url.path not in ["/health", "/docs"]:
            raise HTTPException(status_code=400, detail="Tenant bilgisi gerekli")
        
        tenant_context.set(tenant_id)
        response = await call_next(request)
        return response

# src/database.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from src.core.tenant import tenant_context

engine = create_async_engine(
    "postgresql+asyncpg://user:pass@localhost/turkplatform",
    pool_size=20,
    max_overflow=10
)

AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            # Enable RLS for tenant isolation
            tenant_id = tenant_context.get()
            if tenant_id:
                await session.execute(text(f"SET app.current_tenant = '{tenant_id}'"))
                await session.execute(text("SET SESSION ROLE tenant_user"))
            yield session
        finally:
            await session.execute(text("RESET ROLE"))
```

## OAuth2/JWT Security Implementation

```python
# src/core/security.py
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import redis.asyncio as redis

# Configuration
SECRET_KEY = "your-secret-key-from-env"
ALGORITHM = "RS256"  # Use asymmetric for production
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

# Redis for token blacklisting
redis_client = redis.from_url("redis://localhost:6379", decode_responses=True)

class TokenService:
    @staticmethod
    async def create_access_token(data: Dict[str, Any]) -> str:
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode.update({
            "exp": expire,
            "type": "access",
            "tenant_id": data.get("tenant_id")
        })
        return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    @staticmethod
    async def create_refresh_token(data: Dict[str, Any]) -> str:
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        to_encode.update({
            "exp": expire,
            "type": "refresh",
            "tenant_id": data.get("tenant_id")
        })
        token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        
        # Store refresh token in Redis
        await redis_client.setex(
            f"refresh_token:{data['sub']}:{token[-10:]}",
            REFRESH_TOKEN_EXPIRE_DAYS * 86400,
            token
        )
        return token
    
    @staticmethod
    async def verify_token(token: str) -> Dict[str, Any]:
        # Check if token is blacklisted
        if await redis_client.exists(f"blacklist:{token[-10:]}"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token geçersiz"
            )
        
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token doğrulanamadı"
            )

async def get_current_user(token: str = Depends(oauth2_scheme)):
    payload = await TokenService.verify_token(token)
    return payload
```

## Turkish Integration Connectors

```python
# src/integrations/base_connector.py
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from pydantic import BaseModel

class ConnectorConfig(BaseModel):
    api_key: Optional[str]
    api_secret: Optional[str]
    webhook_url: Optional[str]
    timeout: int = 30
    retry_count: int = 3

class BaseConnector(ABC):
    def __init__(self, config: ConnectorConfig):
        self.config = config
        self.name = self.__class__.__name__
    
    @abstractmethod
    async def authenticate(self) -> bool:
        """Authenticate with the service"""
        pass
    
    @abstractmethod
    async def test_connection(self) -> bool:
        """Test if connection is working"""
        pass
    
    @abstractmethod
    async def execute_action(self, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a specific action"""
        pass
    
    @abstractmethod
    def get_available_actions(self) -> List[str]:
        """Return list of supported actions"""
        pass

# src/integrations/netgsm/connector.py
import httpx
from typing import Dict, Any, List
from ..base_connector import BaseConnector, ConnectorConfig

class NetgsmConnector(BaseConnector):
    BASE_URL = "https://api.netgsm.com.tr"
    
    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        self.client = httpx.AsyncClient(timeout=config.timeout)
    
    async def authenticate(self) -> bool:
        """Verify API credentials"""
        response = await self.client.get(
            f"{self.BASE_URL}/balance",
            params={
                "usercode": self.config.api_key,
                "password": self.config.api_secret
            }
        )
        return response.status_code == 200
    
    async def execute_action(self, action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if action == "send_sms":
            return await self.send_sms(payload)
        elif action == "send_whatsapp":
            return await self.send_whatsapp(payload)
        else:
            raise ValueError(f"Action {action} desteklenmiyor")
    
    async def send_sms(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Send SMS via Netgsm"""
        response = await self.client.post(
            f"{self.BASE_URL}/sms/send/get",
            params={
                "usercode": self.config.api_key,
                "password": self.config.api_secret,
                "gsmno": payload["phone"],
                "message": payload["message"],
                "msgheader": payload.get("sender", "FIRMA")
            }
        )
        
        return {
            "status": "success" if "00" in response.text else "failed",
            "message_id": response.text.split(" ")[1] if "00" in response.text else None,
            "response": response.text
        }
    
    async def send_whatsapp(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Send WhatsApp message via Netasistan"""
        # Requires Netasistan Plus subscription
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json"
        }
        
        response = await self.client.post(
            "https://api.netasistan.com/whatsapp/send",
            json={
                "to": payload["phone"],
                "type": payload.get("type", "text"),
                "text": {"body": payload["message"]} if payload.get("type") == "text" else payload["content"]
            },
            headers=headers
        )
        
        return response.json()
    
    def get_available_actions(self) -> List[str]:
        return ["send_sms", "send_whatsapp", "check_balance", "get_reports"]
```

## KVKK Compliance Implementation

```python
# src/core/kvkk.py
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.consent import ConsentRecord
from src.schemas.kvkk import ConsentRequest, DataExportRequest

class KVKKComplianceService:
    """KVKK (Turkish GDPR) compliance service"""
    
    @staticmethod
    async def record_consent(
        db: AsyncSession,
        tenant_id: str,
        user_id: str,
        consent_data: ConsentRequest
    ) -> ConsentRecord:
        """Record user consent for data processing"""
        consent = ConsentRecord(
            tenant_id=tenant_id,
            user_id=user_id,
            purpose=consent_data.purpose,
            legal_basis=consent_data.legal_basis,
            data_categories=consent_data.data_categories,
            retention_period=consent_data.retention_period,
            ip_address=consent_data.ip_address,
            consent_text=consent_data.consent_text,
            given_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=consent_data.retention_period)
        )
        
        db.add(consent)
        await db.commit()
        return consent
    
    @staticmethod
    async def export_user_data(
        db: AsyncSession,
        tenant_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """Export all user data for KVKK data portability"""
        # Collect data from all tables
        user_data = {
            "user_info": await self._get_user_info(db, user_id),
            "consents": await self._get_consent_history(db, user_id),
            "integrations": await self._get_integration_data(db, user_id),
            "workflows": await self._get_workflow_data(db, user_id),
            "audit_logs": await self._get_audit_logs(db, user_id),
            "exported_at": datetime.utcnow().isoformat(),
            "tenant_id": tenant_id
        }
        
        # Log the export request
        await self._log_data_export(db, tenant_id, user_id)
        
        return user_data
    
    @staticmethod
    async def delete_user_data(
        db: AsyncSession,
        tenant_id: str,
        user_id: str,
        reason: str
    ) -> bool:
        """Delete user data per KVKK right to erasure"""
        # Verify deletion is allowed
        if await self._has_legal_retention_requirement(db, user_id):
            raise HTTPException(
                status_code=400,
                detail="Yasal saklama süresi nedeniyle veri silinemez"
            )
        
        # Anonymize instead of hard delete for audit trail
        await self._anonymize_user_data(db, tenant_id, user_id)
        
        # Log the deletion request
        await self._log_data_deletion(db, tenant_id, user_id, reason)
        
        return True
    
    @staticmethod
    async def get_data_breach_notification(
        breach_details: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate KVKK breach notification (72-hour requirement)"""
        return {
            "notification_id": str(uuid.uuid4()),
            "breach_date": breach_details["date"],
            "discovery_date": datetime.utcnow().isoformat(),
            "affected_data_categories": breach_details["categories"],
            "affected_user_count": breach_details["user_count"],
            "risk_level": breach_details["risk_level"],
            "mitigation_measures": breach_details["measures"],
            "notification_deadline": (datetime.utcnow() + timedelta(hours=72)).isoformat(),
            "kvkk_notification_required": breach_details["risk_level"] in ["high", "critical"]
        }
```

## E-Invoice Integration

```python
# src/integrations/efatura/connector.py
import httpx
import xml.etree.ElementTree as ET
from typing import Dict, Any
from datetime import datetime
from ..base_connector import BaseConnector

class EFaturaConnector(BaseConnector):
    """Turkish e-invoice system integration"""
    
    GIB_URL = "https://efaturatest.gib.gov.tr"  # Test environment
    
    async def create_invoice(self, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create UBL-TR 1.2 compliant e-invoice"""
        
        # Build UBL-TR XML
        ubl_xml = self._build_ubl_invoice(invoice_data)
        
        # Sign with qualified electronic signature
        signed_xml = await self._sign_invoice(ubl_xml)
        
        # Send to GIB for approval
        response = await self.client.post(
            f"{self.GIB_URL}/efatura/gonder",
            content=signed_xml,
            headers={
                "Content-Type": "application/xml",
                "Authorization": f"Bearer {self.config.api_key}"
            }
        )
        
        if response.status_code == 200:
            return {
                "status": "success",
                "invoice_uuid": self._extract_uuid(response.text),
                "gib_response": response.text
            }
        else:
            raise HTTPException(
                status_code=400,
                detail=f"E-fatura gönderilemedi: {response.text}"
            )
    
    def _build_ubl_invoice(self, data: Dict[str, Any]) -> str:
        """Build UBL-TR 1.2 compliant XML"""
        root = ET.Element("{urn:oasis:names:specification:ubl:schema:xsd:Invoice-2}Invoice")
        
        # Add required UBL-TR elements
        ET.SubElement(root, "UBLVersionID").text = "2.1"
        ET.SubElement(root, "CustomizationID").text = "TR1.2"
        ET.SubElement(root, "ProfileID").text = "TEMELFATURA"
        ET.SubElement(root, "ID").text = data["invoice_number"]
        ET.SubElement(root, "UUID").text = str(uuid.uuid4())
        ET.SubElement(root, "IssueDate").text = datetime.utcnow().strftime("%Y-%m-%d")
        
        # Add supplier and customer party
        self._add_party_info(root, "AccountingSupplierParty", data["supplier"])
        self._add_party_info(root, "AccountingCustomerParty", data["customer"])
        
        # Add invoice lines
        for line in data["lines"]:
            self._add_invoice_line(root, line)
        
        # Add totals
        self._add_monetary_totals(root, data["totals"])
        
        return ET.tostring(root, encoding="utf-8").decode()
```

## Testing Strategy

```python
# tests/conftest.py
import pytest
import asyncio
from typing import AsyncGenerator
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from src.main import app
from src.database import Base
from src.core.tenant import tenant_context

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
async def test_db() -> AsyncGenerator[AsyncSession, None]:
    """Create test database with tenant isolation"""
    engine = create_async_engine(
        "postgresql+asyncpg://test:test@localhost/test_turkplatform"
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # Set test tenant context
        tenant_context.set("test-tenant-id")
        yield session
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()

@pytest.fixture
async def client(test_db) -> AsyncGenerator[AsyncClient, None]:
    """Create test client with authentication"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        client.headers["X-Tenant-ID"] = "test-tenant-id"
        yield client

@pytest.fixture
async def authenticated_client(client) -> AsyncClient:
    """Client with valid JWT token"""
    # Create test user and get token
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "test@example.com", "password": "Test123!"}
    )
    token = response.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client

# tests/test_integrations.py
import pytest
from unittest.mock import patch, AsyncMock

@pytest.mark.asyncio
async def test_netgsm_sms_sending(authenticated_client):
    """Test SMS sending via Netgsm"""
    with patch("src.integrations.netgsm.connector.httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = AsyncMock(
            status_code=200,
            text="00 123456789"
        )
        
        response = await authenticated_client.post(
            "/api/v1/integrations/netgsm/send-sms",
            json={
                "phone": "+905551234567",
                "message": "Test mesajı"
            }
        )
        
        assert response.status_code == 200
        assert response.json()["status"] == "success"
        assert response.json()["message_id"] == "123456789"

@pytest.mark.asyncio
async def test_kvkk_consent_recording(authenticated_client, test_db):
    """Test KVKK consent recording"""
    response = await authenticated_client.post(
        "/api/v1/kvkk/consent",
        json={
            "purpose": "marketing",
            "legal_basis": "explicit_consent",
            "data_categories": ["contact", "preferences"],
            "retention_period": 365,
            "consent_text": "Pazarlama bildirimleri için onay veriyorum"
        }
    )
    
    assert response.status_code == 201
    assert response.json()["purpose"] == "marketing"
    assert response.json()["expires_at"] is not None
```

## Docker Configuration

```dockerfile
# docker/Dockerfile.api
FROM python:3.11-slim as builder

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements/base.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY src/ src/
COPY alembic/ alembic/
COPY alembic.ini .

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')"

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```yaml
# docker/docker-compose.yml
version: '3.9'

services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: turkplatform
      POSTGRES_USER: turkuser
      POSTGRES_PASSWORD: turkpass
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./scripts/init_db.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "5432:5432"

  redis:
    image: redis:7.2-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"

  kafka:
    image: confluentinc/cp-kafka:7.5.0
    depends_on:
      - zookeeper
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://localhost:9092
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
    ports:
      - "9092:9092"

  zookeeper:
    image: confluentinc/cp-zookeeper:7.5.0
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181
      ZOOKEEPER_TICK_TIME: 2000

  api:
    build:
      context: .
      dockerfile: docker/Dockerfile.api
    depends_on:
      - postgres
      - redis
      - kafka
    environment:
      DATABASE_URL: postgresql+asyncpg://turkuser:turkpass@postgres/turkplatform
      REDIS_URL: redis://redis:6379
      KAFKA_BOOTSTRAP_SERVERS: kafka:9092
    ports:
      - "8000:8000"
    volumes:
      - ./src:/app/src
    command: uvicorn src.main:app --reload --host 0.0.0.0

  worker:
    build:
      context: .
      dockerfile: docker/Dockerfile.worker
    depends_on:
      - postgres
      - redis
      - kafka
    environment:
      DATABASE_URL: postgresql+asyncpg://turkuser:turkpass@postgres/turkplatform
      REDIS_URL: redis://redis:6379
      KAFKA_BOOTSTRAP_SERVERS: kafka:9092
    command: python -m src.workers.kafka_consumer

volumes:
  postgres_data:
  redis_data:
```

## Kubernetes Deployment

```yaml
# k8s/deployment-api.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: turkplatform-api
  namespace: turkplatform
spec:
  replicas: 3
  selector:
    matchLabels:
      app: turkplatform-api
  template:
    metadata:
      labels:
        app: turkplatform-api
    spec:
      containers:
      - name: api
        image: turkplatform/api:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: turkplatform-secrets
              key: database-url
        - name: REDIS_URL
          valueFrom:
            secretKeyRef:
              name: turkplatform-secrets
              key: redis-url
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: turkplatform-api
  namespace: turkplatform
spec:
  selector:
    app: turkplatform-api
  ports:
  - port: 80
    targetPort: 8000
  type: ClusterIP
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: turkplatform-api-hpa
  namespace: turkplatform
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: turkplatform-api
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

## Development Workflow

```bash
#!/bin/bash
# scripts/setup_dev.sh

echo "🚀 Turkish Integration Platform - Development Setup"

# Check dependencies
command -v docker >/dev/null 2>&1 || { echo "Docker gerekli"; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "Python 3.11+ gerekli"; exit 1; }

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements/dev.txt

# Copy environment template
cp .env.example .env
echo "⚠️  .env dosyasını düzenleyin"

# Start Docker services
docker-compose up -d postgres redis kafka

# Wait for services
echo "Servisler başlatılıyor..."
sleep 10

# Run migrations
alembic upgrade head

# Create test tenant
python scripts/create_tenant.py \
  --name "Test Firma" \
  --subdomain "test" \
  --plan "trial"

echo "✅ Kurulum tamamlandı!"
echo "Çalıştırmak için: uvicorn src.main:app --reload"
```

## Best Practices and Guidelines

### Security Checklist
- [ ] JWT tokens with RS256 algorithm in production
- [ ] Refresh token rotation implemented
- [ ] Rate limiting per tenant configured
- [ ] CORS properly configured for production domains
- [ ] Security headers (HSTS, CSP, X-Frame-Options) enabled
- [ ] Input validation with Pydantic on all endpoints
- [ ] SQL injection prevention via parameterized queries
- [ ] XSS protection in all user inputs
- [ ] KVKK consent tracking implemented
- [ ] Data encryption at rest and in transit

### Performance Optimization
- [ ] Database connection pooling configured
- [ ] Redis caching for frequently accessed data
- [ ] Async operations for all I/O
- [ ] Database indexes on tenant_id and frequently queried fields
- [ ] Pagination on all list endpoints
- [ ] Response compression enabled
- [ ] CDN for static assets
- [ ] Horizontal scaling with Kubernetes HPA

### Turkish Compliance
- [ ] KVKK VERBIS registration completed
- [ ] Data localization in Turkish data centers
- [ ] Turkish language support throughout
- [ ] E-invoice integration ready
- [ ] Turkish payment gateways integrated
- [ ] Local phone number for support
- [ ] Terms of service in Turkish
- [ ] Privacy policy compliant with KVKK

### Monitoring and Observability
- [ ] Prometheus metrics exposed
- [ ] Grafana dashboards configured
- [ ] Structured logging with correlation IDs
- [ ] Error tracking with Sentry
- [ ] APM with OpenTelemetry
- [ ] Health check endpoints
- [ ] Tenant-aware metrics
- [ ] SLA monitoring

## Conclusion

This implementation guide provides a production-ready foundation for building a Turkish business integration platform with FastAPI. The architecture supports thousands of tenants, complies with Turkish regulations, and integrates with key Turkish business services.

Key features implemented:
- Multi-tenant architecture with PostgreSQL RLS
- KVKK compliance framework
- OAuth2/JWT authentication with refresh tokens
- Turkish business system integrations
- Event-driven architecture with Kafka
- Comprehensive testing strategy
- Docker/Kubernetes deployment
- Production-ready security and monitoring

The platform is designed to scale horizontally, maintain data isolation between tenants, and provide a robust foundation for building integration workflows targeting the Turkish SME market.

Next steps for production deployment:
1. Configure production secrets and environment variables
2. Set up Turkish cloud infrastructure (preferably in Istanbul region)
3. Complete KVKK VERBIS registration
4. Implement production monitoring and alerting
5. Conduct security audit and penetration testing
6. Establish 24/7 Turkish language support
7. Create comprehensive API documentation
8. Build admin dashboard for tenant management