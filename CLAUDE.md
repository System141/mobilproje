# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Hybrid Python-to-C++ ERP Integration Platform** - A FastAPI-based integration platform designed to start with Python for rapid development and gradually migrate performance-critical components to C++ for enterprise-grade performance. Built following modern Python practices with a clear path to C++ optimization.

## Development Strategy

This project follows a **hybrid approach**:
1. **Phase 1 (Months 1-6)**: Pure Python implementation with FastAPI, Polars, and modern async patterns
2. **Phase 2 (Months 7-12)**: Gradual migration of performance-critical components to C++ using pybind11
3. **Phase 3 (12+ months)**: Production optimization with hybrid Python-C++ architecture

## Build & Run Commands

### Quick Start
```bash
# Install dependencies
pip install -e ".[dev]"

# Run development server
uvicorn erp_platform.main:app --reload --host 0.0.0.0 --port 8000

# Using Docker
docker-compose up --build

# Run with specific environment
docker-compose --env-file .env.production up
```

### Testing
```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=erp_platform --cov-report=html

# Run specific test categories
pytest tests/ -m "unit"
pytest tests/ -m "integration"
pytest tests/ -m "sap"

# Performance profiling
py-spy record -o profile.svg -- python -m pytest tests/
```

### Code Quality
```bash
# Format code
black src/

# Lint code
ruff check src/

# Type checking
mypy src/

# Pre-commit hooks
pre-commit run --all-files
```

## Project Architecture

### Core Structure
```
src/erp_platform/
├── core/                 # Core utilities and configuration
│   ├── config.py        # Pydantic settings management
│   ├── logging.py       # Structured logging with structlog
│   └── telemetry.py     # Metrics and monitoring
├── connectors/          # ERP system connectors
│   ├── base.py          # Base connector with retry logic
│   ├── sap.py           # SAP connector using PyRFC
│   ├── oracle.py        # Oracle connector using oracledb
│   ├── sqlserver.py     # SQL Server connector using pyodbc
│   └── pool.py          # Connection pool management
├── processors/          # Data processing modules
│   ├── polars_processor.py    # High-performance data ops with Polars
│   ├── csv_processor.py       # CSV processing
│   └── json_processor.py      # JSON processing
├── api/v1/              # FastAPI endpoints
│   ├── health.py        # Health check endpoints
│   ├── connectors.py    # ERP connector endpoints
│   ├── processors.py    # Data processing endpoints
│   └── tasks.py         # Async task management
└── tasks/               # Background task definitions (Celery)
```

### Technology Stack

**Core Framework**:
- **FastAPI**: Modern async web framework with automatic OpenAPI docs
- **Polars**: High-performance DataFrame library (5-10x faster than pandas)
- **Pydantic**: Data validation and settings management
- **Structlog**: Structured logging for better observability

**ERP Connectors**:
- **PyRFC**: SAP NetWeaver RFC connectivity
- **python-oracledb**: Official Oracle database driver
- **pyodbc**: SQL Server and other ODBC connections

**Task Processing**:
- **Celery**: Distributed task queue with Redis backend
- **Redis**: In-memory data store for caching and queues

**Monitoring**:
- **Prometheus**: Metrics collection
- **OpenTelemetry**: Distributed tracing
- **Grafana**: Visualization and alerting

## Development Guidelines

### Adding New ERP Connectors

1. Create new connector in `src/erp_platform/connectors/`
2. Inherit from `BaseConnector` class
3. Implement required methods:
   ```python
   async def connect(self) -> bool
   async def disconnect(self) -> bool  
   async def execute(self, query: str, params: Dict) -> Any
   async def ping(self) -> bool
   ```
4. Add connection pool support in `pool.py`
5. Create API endpoints in `api/v1/connectors.py`

### Performance Optimization Strategy

**Identify Bottlenecks**:
```bash
# Profile production workloads
py-spy record -o profile.svg -d 60 -s

# Memory profiling
mprof run python -c "import erp_platform.main"
mprof plot

# Async profiling
python -m cProfile -s cumulative erp_platform/main.py
```

**Migration Candidates** (in order of priority):
1. Mathematical computations and data transformations
2. CSV/JSON parsing for large files
3. Data validation and serialization
4. Cryptographic operations
5. Network protocol parsing

### Error Handling

- Use custom exception classes for different error types
- Implement exponential backoff with `BaseConnector`
- Log structured errors with context using structlog
- Return proper HTTP status codes in API responses

### Memory Management

- Use async context managers for resource cleanup
- Implement connection pooling to avoid resource leaks
- Profile memory usage regularly with memory-profiler
- Use Polars lazy evaluation for large datasets

## Environment Configuration

Copy `.env.example` to `.env` and configure:

**Essential Settings**:
```bash
# Application
ENVIRONMENT=development
DEBUG=true
HOST=0.0.0.0
PORT=8000

# ERP Systems (configure as needed)
SAP_ENABLED=true
SAP_HOST=your-sap-server
SAP_USER=your-user
SAP_PASSWORD=your-password

# Performance
MAX_WORKERS=10
USE_CPP_ACCELERATION=false  # Set to true when C++ modules are ready
```

## Docker & Production Deployment

```bash
# Build and run with Docker Compose
docker-compose up --build

# Production deployment
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up

# Scale services
docker-compose up --scale celery-worker=3
```

**Monitoring Stack**:
- Prometheus metrics: http://localhost:9090
- Grafana dashboards: http://localhost:3000
- Flower (Celery): http://localhost:5555

## C++ Integration (Future)

When performance optimization is needed:

1. **Profile First**: Use py-spy to identify bottlenecks
2. **Create C++ Module**: 
   ```bash
   mkdir src/cpp_extensions/your_module
   # Implement with pybind11
   ```
3. **Hybrid Loading**:
   ```python
   try:
       from cpp_extensions import optimized_function
       use_cpp = True
   except ImportError:
       from python_impl import optimized_function
       use_cpp = False
   ```

## API Usage Examples

### SAP Integration
```bash
# Execute SAP BAPI
curl -X POST "http://localhost:8000/api/v1/connectors/sap/execute" \
  -H "Content-Type: application/json" \
  -d '{"function_name": "BAPI_USER_GET_DETAIL", "parameters": {"USERNAME": "TESTUSER"}}'

# Read SAP table
curl "http://localhost:8000/api/v1/connectors/sap/read-table?table_name=MARA&max_rows=10"
```

### Data Processing
```bash
# Process CSV with Polars
curl -X POST "http://localhost:8000/api/v1/processors/transform/polars" \
  -F "file=@data.csv" \
  -F "operations=[{\"type\":\"filter\",\"condition\":{\"column\":\"status\",\"value\":\"active\"}}]"
```

## Performance Targets

**Current (Python)**:
- API throughput: 1,000+ requests/second
- CSV processing: 100MB files in <5 seconds
- Memory usage: <2GB under normal load

**Future (Hybrid)**:
- API throughput: 5,000+ requests/second  
- CSV processing: 100MB files in <1 second
- Memory usage: <1GB under normal load

## Common Issues & Solutions

**Connection Pool Exhaustion**:
```python
# Increase pool size in .env
SAP_POOL_SIZE=10
ORACLE_POOL_SIZE=10
```

**Memory Issues with Large Files**:
```python
# Use Polars lazy evaluation
df = pl.scan_csv("large_file.csv").filter(...).collect()
```

**Slow API Responses**:
```bash
# Profile specific endpoints
py-spy record -o profile.svg -d 10 -s -u http://localhost:8000/slow-endpoint
```

## Important Notes

- All ERP connections use connection pooling by default
- Async/await pattern used throughout for high concurrency
- Structured logging provides detailed request tracing
- Prometheus metrics track all connector operations
- Docker setup includes full monitoring stack
- C++ acceleration is opt-in and falls back gracefully to Python