# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# Turkish Business Integration Platform

## Tech Stack
- Framework: FastAPI 0.104+ with Python 3.11
- Database: PostgreSQL 15 with Row-Level Security for multi-tenancy
- Cache: Redis 7.2 
- Queue: Apache Kafka 3.6
- Container: Docker with multi-stage builds
- Language: Python 3.11+ with type hints

## Commands

### Development Setup
```bash
# Start full development environment
./scripts/setup_dev.sh

# Or manual setup
cd docker && docker-compose up -d --build
```

### Testing & Quality
```bash
# Run tests
pytest --cov=src --cov-report=html

# Type checking
mypy src/

# Code formatting
black src/ tests/
ruff check --fix src/ tests/

# Single test
pytest tests/test_specific.py::test_function -v
```

### Database Operations
```bash
# Run migrations
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "description"

# Reset database (development only)
docker-compose exec postgres psql -U turkuser -d turkplatform -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
```

### Application Running
```bash
# Development server
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# Production (in container)
docker-compose -f docker/docker-compose.yml up -d api
```

## Architecture Overview

This is a **multi-tenant SaaS platform** for Turkish business system integrations with strict KVKK (Turkish GDPR) compliance.

### Core Design Patterns

**Multi-Tenancy**: Every data model inherits from `TenantAwareModel` which provides:
- Automatic tenant isolation via `tenant_id` field
- Row-Level Security (RLS) at PostgreSQL level
- KVKK compliance fields (data_subject_id, legal_basis, retention_until)
- Audit trail and anonymization capabilities

**Turkish Business Integrations**: All integrations inherit from `BaseConnector` which provides:
- Standardized async HTTP client with retry logic
- Turkish phone number validation
- Bilingual error messages (Turkish/English)
- Connection pooling and rate limiting

### Key Components

**Database Layer** (`src/models/`):
- `TenantAwareModel`: Base for all tenant data with KVKK compliance
- `SystemModel`: Base for system-wide data (tenant management)
- `ConsentRecord`: KVKK consent tracking
- `AuditLogModel`: Complete audit trail for compliance

**Integration Layer** (`src/integrations/`):
- `BaseConnector`: Abstract base with HTTP client, auth, retry logic
- `NetgsmConnector`: SMS/WhatsApp via Turkish Netgsm service
- Each connector validates Turkish-specific data (phone numbers, tax IDs)

**API Layer** (`src/api/v1/`):
- All endpoints are tenant-aware via `TenantMiddleware`
- Automatic tenant extraction from subdomain or X-Tenant-ID header
- Turkish/English error responses

**Multi-Tenant Architecture**:
- `TenantMiddleware`: Extracts tenant from request, sets context
- `tenant_context`: Context variable for tenant ID throughout request
- PostgreSQL RLS policies enforce data isolation
- Connection pooling per tenant with usage quotas

## Key Architectural Concepts

### KVKK Compliance Integration
Every model that stores personal data must:
```python
class MyModel(TenantAwareModel):
    # Inherits KVKK compliance fields:
    # - data_subject_id, legal_basis, data_category
    # - retention_until, is_anonymized
    # - created_by, updated_by for audit trail
```

### Turkish Business System Pattern
All Turkish business integrations follow this pattern:
```python
class TurkishSystemConnector(BaseConnector):
    async def authenticate(self) -> bool: ...
    async def execute_action(self, action: str, payload: Dict) -> ConnectorResponse: ...
    def get_available_actions(self) -> List[str]: ...
```

### Multi-Tenant Request Flow
1. Request hits `TenantMiddleware`
2. Tenant extracted from subdomain/header
3. `tenant_context.set(tenant_id)` called
4. Database queries automatically filtered by tenant via RLS
5. All logging includes tenant_id for tracing

## Development Guidelines

### Adding New Turkish Business Integrations
1. Create connector in `src/integrations/{service_name}/`
2. Inherit from `BaseConnector`
3. Implement required abstract methods
4. Add Turkish phone/tax number validation as needed
5. Include bilingual error messages
6. Add integration tests with Turkish test data

### Database Model Guidelines
- Use `TenantAwareModel` for tenant data
- Use `SystemModel` for system-wide data (tenants, system config)  
- Include KVKK legal basis for personal data
- Set retention periods per Turkish data protection law
- Use soft deletes via `deleted_at` field

### Testing Strategy
- Unit tests for each connector with Turkish data validation
- Integration tests with real Turkish phone numbers (anonymized)
- KVKK compliance tests (consent tracking, data export, anonymization)
- Multi-tenant isolation tests

## Turkish Compliance Notes

- All personal data must have legal basis (KVKK requirement)
- Phone numbers must be Turkish mobile format (5XX XXX XXXX)
- Tax numbers validated as 10-11 digit Turkish format
- Data retention periods enforced automatically
- Audit logs required for all personal data access
- Consent records must be maintained for 3+ years

## Environment Access

Development services:
- API: http://localhost:8000/docs
- Database: localhost:5432 (turkuser/turkpass) 
- Redis: localhost:6379
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000 (admin/turkpass)

## Do Not Modify
- `alembic/versions/` (database migrations)
- `src/models/base.py` KVKK compliance fields
- `src/core/tenant.py` multi-tenant logic
- Database RLS policies in production