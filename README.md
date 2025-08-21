# Hybrid Python-to-C++ ERP Integration Platform

🚀 **FastAPI-based ERP integration platform** designed for rapid development in Python with a clear migration path to C++ for performance-critical components.

[![CI/CD Pipeline](https://github.com/your-org/erp-platform/workflows/CI/CD%20Pipeline/badge.svg)](https://github.com/your-org/erp-platform/actions)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/Docker-supported-blue.svg)](https://www.docker.com/)

## 🎯 Strategy

This project follows a **hybrid development approach**:

1. **Phase 1** (Months 1-6): Pure Python implementation for rapid prototyping and feature development
2. **Phase 2** (Months 7-12): Profile and identify performance bottlenecks  
3. **Phase 3** (12+ months): Migrate critical components to C++ while maintaining Python interfaces

## ✨ Features

- **🔥 Modern Python Stack**: FastAPI, Polars, Pydantic, structured logging
- **🔌 Multi-ERP Connectors**: SAP (PyRFC), Oracle, SQL Server with connection pooling
- **⚡ High-Performance Data Processing**: Polars DataFrames (5-10x faster than pandas)
- **📊 Production Monitoring**: Prometheus metrics, OpenTelemetry tracing, Grafana dashboards
- **🔄 Async Task Processing**: Celery with Redis for distributed processing
- **🐳 Container Ready**: Docker Compose with full development stack
- **🎯 C++ Migration Path**: pybind11 integration for performance-critical modules

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────┐
│              FastAPI Application                 │
├─────────────────────────────────────────────────┤
│  Health │ Connectors │ Processors │   Tasks     │
├─────────────────────────────────────────────────┤
│          Connection Pool Manager                 │
├──────────┬──────────┬──────────┬────────────────┤
│   SAP    │  Oracle  │ SQL Srv  │  Future C++    │
│ (PyRFC)  │(oracledb)│ (pyodbc) │  Extensions    │
└──────────┴──────────┴──────────┴────────────────┘
```

## 🚀 Quick Start

### Using Docker (Recommended)

```bash
# Clone the repository
git clone <repository-url>
cd erp-integration-platform

# Start full development stack
docker-compose up --build

# Access services
# - API Documentation: http://localhost:8000/docs
# - Grafana Dashboard: http://localhost:3000 (admin/admin)
# - Flower (Celery): http://localhost:5555
# - Prometheus: http://localhost:9090
```

### Local Development

```bash
# Install dependencies
pip install -e ".[dev]"

# Copy environment configuration
cp .env.example .env
# Edit .env with your ERP system credentials

# Run development server
uvicorn erp_platform.main:app --reload --host 0.0.0.0 --port 8000

# Run tests
pytest tests/ --cov=erp_platform
```

## 📖 Usage Examples

### SAP Integration

```python
from erp_platform.connectors import SAPConnector

# Configure SAP connection
config = ConnectionConfig(
    host="sap.company.com",
    username="your_user",
    password="your_password",
    extra_params={
        "sysnr": "00",
        "client": "100"
    }
)

# Execute BAPI
connector = SAPConnector(config)
await connector.connect()

result = await connector.call_bapi(
    "BAPI_USER_GET_DETAIL",
    {"USERNAME": "TESTUSER"}
)
```

### High-Performance Data Processing

```python
from erp_platform.processors import PolarsProcessor

processor = PolarsProcessor()

# Process large CSV files with lazy evaluation
df = await processor.process_large_file(
    "large_dataset.csv",
    operations=[
        {"type": "filter", "condition": {"column": "status", "value": "active"}},
        {"type": "group_by", "columns": ["region"], "aggregations": {"sales": "sum"}}
    ]
)

# Memory-optimized processing
optimized_df = await processor.optimize_memory(df)
```

### REST API Usage

```bash
# Health check
curl http://localhost:8000/api/v1/health

# Execute SAP function
curl -X POST "http://localhost:8000/api/v1/connectors/sap/execute" \
  -H "Content-Type: application/json" \
  -d '{"function_name": "BAPI_USER_GET_DETAIL", "parameters": {"USERNAME": "TESTUSER"}}'

# Process data with Polars
curl -X POST "http://localhost:8000/api/v1/processors/transform/polars" \
  -F "file=@data.csv" \
  -F 'operations=[{"type":"filter","condition":{"column":"status","value":"active"}}]'
```

## 🛠️ Development

### Project Structure

```
src/erp_platform/
├── core/                 # Configuration, logging, telemetry
├── connectors/           # ERP system connectors
│   ├── sap.py           # SAP connector (PyRFC)
│   ├── oracle.py        # Oracle connector (oracledb)
│   └── pool.py          # Connection pool management
├── processors/          # Data processing modules
│   └── polars_processor.py # High-performance operations
├── api/v1/              # FastAPI endpoints
└── tasks/               # Celery background tasks
```

### Adding New Connectors

1. **Create connector class**:
   ```python
   class MyERPConnector(BaseConnector):
       async def connect(self) -> bool: ...
       async def execute(self, query: str, params: Dict) -> Any: ...
   ```

2. **Add to connection pool**:
   ```python
   # In pool.py
   connector_map = {
       'myerp': MyERPConnector,
   }
   ```

3. **Create API endpoints**:
   ```python
   @router.post("/myerp/execute")
   async def execute_myerp_query(...):
   ```

### Performance Optimization

```bash
# Profile application
py-spy record -o profile.svg -d 60 uvicorn erp_platform.main:app

# Memory profiling  
mprof run uvicorn erp_platform.main:app
mprof plot

# Identify optimization candidates
python -c "
from erp_platform.processors import identify_bottlenecks
bottlenecks = identify_bottlenecks()
print('Migrate to C++:', bottlenecks)
"
```

## 📊 Performance Targets

| Metric | Current (Python) | Target (Hybrid) |
|--------|------------------|-----------------|
| API Throughput | 1,000 req/s | 5,000 req/s |
| CSV Processing (100MB) | <5 seconds | <1 second |
| Memory Usage | <2GB | <1GB |
| Connection Pool | 5-20/system | 10-50/system |

## 🏢 Teknokent Environment

Optimized for Turkish Teknokent development:

- **KVKK Compliance**: Built-in data protection features
- **Turkish Localization**: Multi-language support ready
- **University Integration**: Designed for ODTÜ/İTÜ collaboration
- **Government Support**: Documentation for TÜBİTAK/KOSGEB applications

## 🔧 Configuration

Key environment variables:

```bash
# Application
ENVIRONMENT=development
DEBUG=true
HOST=0.0.0.0
PORT=8000

# ERP Systems
SAP_ENABLED=true
SAP_HOST=your-sap-server
SAP_USER=your-username
SAP_PASSWORD=your-password

# Performance  
MAX_WORKERS=10
USE_CPP_ACCELERATION=false  # Enable when C++ modules are ready
```

## 🐳 Production Deployment

```bash
# Production with Docker Compose
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up

# Scale workers
docker-compose up --scale celery-worker=5

# Health check
curl http://localhost:8000/api/v1/health/detailed
```

## 🔮 Future C++ Integration

When performance bottlenecks are identified:

```python
# Hybrid loading pattern
try:
    from cpp_extensions import fast_data_processor
    USE_CPP = True
except ImportError:
    from python_impl import fast_data_processor  
    USE_CPP = False

result = fast_data_processor(data) if USE_CPP else slow_python_processor(data)
```

## 🧪 Testing

```bash
# Run all tests
pytest tests/

# Test specific components  
pytest tests/ -m "sap"
pytest tests/ -m "integration" 
pytest tests/ -k "connector"

# Performance tests
pytest tests/performance/ --benchmark-only
```

## 📈 Monitoring

- **Metrics**: Prometheus at http://localhost:9090
- **Dashboards**: Grafana at http://localhost:3000
- **Task Queue**: Flower at http://localhost:5555
- **Logs**: Structured JSON logs with correlation IDs

## 🤝 Contributing

1. Follow Python best practices (Black, Ruff, MyPy)
2. Write tests for new features
3. Update CLAUDE.md for architectural changes
4. Profile performance-critical code

## 📄 License

Proprietary - All rights reserved

## 🆘 Support

- **Documentation**: See [CLAUDE.md](CLAUDE.md) for detailed development guide
- **Issues**: Create GitHub issues for bugs and feature requests  
- **Performance**: Use py-spy profiling before optimization requests