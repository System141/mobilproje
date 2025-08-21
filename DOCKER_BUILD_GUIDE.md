# Docker Build Guide - ERP Integration Platform

This guide explains how to build and run the ERP Integration Platform with different SAP connectivity options.

## Build Variants

The platform supports multiple build variants to handle different SAP connectivity requirements:

### 1. Base Variant (Default)
- **Purpose**: Core platform without SAP RFC support
- **SAP Connectivity**: None (Oracle, SQL Server only)
- **Requirements**: Standard Python dependencies only

```bash
# Build base variant
docker build --target base -t erp-platform:base .

# Or using docker-compose
docker-compose up app
```

### 2. SAP REST Variant
- **Purpose**: SAP connectivity via REST/OData APIs
- **SAP Connectivity**: HTTP-based OData services
- **Requirements**: Standard Python dependencies + requests

```bash
# Build SAP REST variant
docker build --target sap-rest \
  --build-arg BUILD_VARIANT=sap-rest \
  --build-arg INCLUDE_SAP_REST=true \
  -t erp-platform:sap-rest .

# Or using docker-compose profiles
docker-compose --profile sap-rest up app-sap-rest
```

### 3. SAP RFC Variant
- **Purpose**: Full SAP RFC/BAPI support
- **SAP Connectivity**: Direct RFC calls via PyRFC
- **Requirements**: SAP NetWeaver RFC SDK + PyRFC

```bash
# Build SAP RFC variant (requires SAP SDK)
docker build --target sap-rfc \
  --build-arg BUILD_VARIANT=sap-rfc \
  --build-arg INCLUDE_SAP_RFC=true \
  --mount type=bind,source=/path/to/nwrfcsdk,target=/opt/nwrfcsdk \
  -t erp-platform:sap-rfc .

# Or using docker-compose profiles
docker-compose --profile sap-rfc up app-sap-rfc
```

## SAP NetWeaver RFC SDK Setup (For RFC Variant)

### Prerequisites
1. Download SAP NetWeaver RFC SDK from [SAP Support Portal](https://support.sap.com/)
2. Extract the SDK to a local directory (e.g., `/opt/nwrfcsdk`)

### Installation Steps
1. **Download SDK**:
   - Log in to SAP Support Portal
   - Navigate to Software Downloads
   - Search for "SAP NW RFC SDK"
   - Download the appropriate version for your OS

2. **Extract SDK**:
   ```bash
   # Example extraction
   mkdir -p /opt/nwrfcsdk
   cd /opt/nwrfcsdk
   unzip /path/to/nwrfc750P_X-xxxxxxx.zip
   ```

3. **Set Permissions**:
   ```bash
   chmod -R 755 /opt/nwrfcsdk
   ```

4. **Update Docker Compose**:
   ```yaml
   # In docker-compose.override.yml
   services:
     app:
       volumes:
         - /opt/nwrfcsdk:/opt/nwrfcsdk:ro
   ```

## Quick Start Commands

### Option 1: Base Platform (No SAP)
```bash
# Start with basic ERP support (Oracle, SQL Server)
docker-compose up -d
```

### Option 2: SAP REST Support
```bash
# Start with SAP REST/OData support
docker-compose --profile sap-rest up -d app-sap-rest
```

### Option 3: Full SAP RFC Support
```bash
# Prerequisites: SAP NetWeaver RFC SDK installed
cp docker-compose.override.example.yml docker-compose.override.yml
# Edit docker-compose.override.yml to configure SAP RFC settings
docker-compose --profile sap-rfc up -d app-sap-rfc
```

## Environment Configuration

### Base Configuration
```bash
# Core settings
ENVIRONMENT=development
DEBUG=true
REDIS_URL=redis://redis:6379/0

# Database connections
ORACLE_HOST=your-oracle-host
ORACLE_PORT=1521
ORACLE_SERVICE=your-service

SQLSERVER_HOST=your-sqlserver-host
SQLSERVER_PORT=1433
SQLSERVER_DATABASE=your-database
```

### SAP REST Configuration
```bash
# SAP REST settings
SAP_CONNECTION_MODE=rest
SAP_HOST=your-sap-host.com
SAP_PORT=8000
SAP_USERNAME=your-username
SAP_PASSWORD=your-password

# Optional: Service-specific settings
SAP_CLIENT=100
SAP_LANG=EN
```

### SAP RFC Configuration
```bash
# SAP RFC settings
SAP_CONNECTION_MODE=rfc
ERP_PLATFORM_SAP_RFC_ENABLED=true
SAPNWRFC_HOME=/opt/nwrfcsdk
LD_LIBRARY_PATH=/opt/nwrfcsdk/lib

# SAP connection parameters
SAP_HOST=your-sap-host.com
SAP_SYSNR=00
SAP_CLIENT=100
SAP_USERNAME=your-username
SAP_PASSWORD=your-password
SAP_LANG=EN
```

## Troubleshooting

### PyRFC Installation Issues

**Problem**: `ERROR: Could not find a version that satisfies the requirement pyrfc>=3.0`

**Solution**: This is expected when SAP NetWeaver RFC SDK is not available. Use one of these approaches:

1. **Use SAP REST variant** (recommended for most cases):
   ```bash
   docker-compose --profile sap-rest up app-sap-rest
   ```

2. **Install SAP SDK and use RFC variant**:
   - Download SAP NetWeaver RFC SDK
   - Mount it in the container
   - Use the `sap-rfc` profile

3. **Build without SAP support**:
   ```bash
   docker-compose up app  # Base variant
   ```

### Common Build Errors

**Error**: `failed to solve: target stage "sap-rfc" could not be found`

**Fix**: Use the correct target name:
```bash
docker build --target production .  # Not sap-rfc directly
```

**Error**: `RuntimeError: Not connected to SAP`

**Fix**: Check your SAP connection configuration and network connectivity.

### Testing Connectivity

```bash
# Test base platform
curl http://localhost:8000/api/v1/health

# Test SAP REST connectivity
curl http://localhost:8001/api/v1/health

# Test SAP RFC connectivity  
curl http://localhost:8002/api/v1/health
```

## Development Workflow

### Local Development
```bash
# Start services
docker-compose up -d redis postgres

# Run application locally
cd src
python -m erp_platform.main

# Or use Docker with hot reload
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up
```

### Testing Different Variants
```bash
# Test base variant
docker-compose up app
curl http://localhost:8000/api/v1/connectors

# Test SAP REST variant
docker-compose --profile sap-rest up app-sap-rest
curl http://localhost:8001/api/v1/connectors

# Test SAP RFC variant (if SDK available)
docker-compose --profile sap-rfc up app-sap-rfc
curl http://localhost:8002/api/v1/connectors
```

## Production Deployment

### Security Considerations
1. **Use secrets management** for passwords
2. **Enable HTTPS** with proper certificates
3. **Configure firewall rules** for SAP connectivity
4. **Use non-root users** in containers
5. **Scan images** for vulnerabilities

### Resource Requirements
- **Base variant**: 512MB RAM, 1 CPU core
- **SAP REST variant**: 1GB RAM, 1 CPU core
- **SAP RFC variant**: 2GB RAM, 2 CPU cores (due to SAP SDK overhead)

### Scaling
```bash
# Scale workers
docker-compose up --scale celery-worker=3

# Use multiple app instances with load balancer
docker-compose up --scale app=3
```

## Support

### SAP Connectivity Options Comparison

| Feature | Base | SAP REST | SAP RFC |
|---------|------|----------|---------|
| PyRFC Dependency | ❌ | ❌ | ✅ |
| SAP SDK Required | ❌ | ❌ | ✅ |
| HTTP/OData APIs | ❌ | ✅ | ✅ |
| Direct RFC/BAPI Calls | ❌ | ❌ | ✅ |
| Table Read Access | ❌ | ✅ | ✅ |
| Real-time Data | ❌ | ✅ | ✅ |
| Transaction Support | ❌ | Limited | ✅ |
| Setup Complexity | Low | Medium | High |

### Getting Help
1. Check the application logs: `docker-compose logs app`
2. Verify network connectivity to SAP systems
3. Confirm SAP user permissions and roles
4. Review the SAP connection configuration

For SAP-specific issues, consult your SAP system administrator.