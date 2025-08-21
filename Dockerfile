# Multi-stage build for ERP Integration Platform
# Build arguments to control which components are included
ARG BUILD_VARIANT=base
ARG INCLUDE_SAP_RFC=false
ARG INCLUDE_SAP_REST=true

# ============================================================================
# Stage 1: Base Python Builder
# ============================================================================
FROM python:3.11-slim AS base-builder

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    cmake \
    make \
    unixodbc-dev \
    libxml2-dev \
    libxslt-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements files
COPY requirements-base.txt .
COPY requirements-sap-rest.txt .
COPY pyproject.toml .
COPY src/ ./src/

# Install base Python dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements-base.txt

# Install SAP REST dependencies if needed
RUN if [ "$INCLUDE_SAP_REST" = "true" ]; then \
        pip install --no-cache-dir -r requirements-sap-rest.txt; \
    fi

# Install the package itself
RUN pip install --no-cache-dir -e .

# ============================================================================
# Stage 2: SAP RFC Builder (Optional - only if SAP RFC SDK is available)
# ============================================================================
FROM base-builder AS sap-rfc-builder

# This stage assumes SAP NetWeaver RFC SDK is available
# It should be mounted as a volume or copied during build
# Example: docker build --build-arg INCLUDE_SAP_RFC=true --mount type=bind,source=/path/to/nwrfcsdk,target=/opt/nwrfcsdk

# Environment variables for SAP RFC SDK
ENV SAPNWRFC_HOME=/opt/nwrfcsdk
ENV LD_LIBRARY_PATH=$SAPNWRFC_HOME/lib:$LD_LIBRARY_PATH
ENV PATH=$SAPNWRFC_HOME/bin:$PATH

# Install PyRFC if SAP RFC SDK is available
RUN if [ "$INCLUDE_SAP_RFC" = "true" ] && [ -d "/opt/nwrfcsdk" ]; then \
        pip install --no-cache-dir pyrfc>=3.0; \
    fi

# ============================================================================
# Stage 3: C++ Builder (for future C++ extensions)
# ============================================================================
FROM gcc:12 AS cpp-builder

WORKDIR /app

# Install CMake and other build tools
RUN apt-get update && apt-get install -y \
    cmake \
    ninja-build \
    && rm -rf /var/lib/apt/lists/*

# Copy C++ extensions (when implemented)
COPY src/cpp_extensions/ ./cpp_extensions/

# Build C++ extensions (placeholder)
RUN mkdir -p build && cd build && \
    echo "C++ extensions will be built here"

# ============================================================================
# Stage 4: Production Runtime
# ============================================================================
FROM python:3.11-slim AS production

WORKDIR /app

# Build arguments
ARG BUILD_VARIANT=base
ARG INCLUDE_SAP_RFC=false

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    unixodbc \
    libpq5 \
    libxml2 \
    libxslt1.1 \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from appropriate builder stage
COPY --from=base-builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=base-builder /usr/local/bin /usr/local/bin

# Conditionally copy SAP RFC components if built
RUN if [ "$INCLUDE_SAP_RFC" = "true" ]; then \
        mkdir -p /opt/nwrfcsdk; \
    fi

# Copy application code
COPY src/ ./src/

# Create non-root user
RUN useradd -m -u 1000 erpuser && \
    chown -R erpuser:erpuser /app

USER erpuser

# Set environment variables
ENV PYTHONPATH=/app/src:$PYTHONPATH
ENV PYTHONUNBUFFERED=1
ENV ERP_PLATFORM_BUILD_VARIANT=${BUILD_VARIANT}
ENV ERP_PLATFORM_SAP_RFC_ENABLED=${INCLUDE_SAP_RFC}

# Set SAP RFC environment if enabled
RUN if [ "$INCLUDE_SAP_RFC" = "true" ]; then \
        echo 'export SAPNWRFC_HOME=/opt/nwrfcsdk' >> ~/.bashrc && \
        echo 'export LD_LIBRARY_PATH=$SAPNWRFC_HOME/lib:$LD_LIBRARY_PATH' >> ~/.bashrc; \
    fi

# Expose ports
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.path.append('/app/src'); from erp_platform.api.v1.health import health_check; print('OK')" || exit 1

# Run application
CMD ["uvicorn", "erp_platform.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ============================================================================
# Build Variants
# ============================================================================

# Base variant (default) - No SAP RFC support
FROM production AS base
ENV ERP_PLATFORM_BUILD_VARIANT=base

# SAP REST variant - SAP connectivity via REST/OData APIs
FROM production AS sap-rest
ENV ERP_PLATFORM_BUILD_VARIANT=sap-rest

# SAP RFC variant - Full SAP RFC support (requires SAP SDK)
FROM production AS sap-rfc
ARG INCLUDE_SAP_RFC=true
COPY --from=sap-rfc-builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
ENV ERP_PLATFORM_BUILD_VARIANT=sap-rfc
ENV ERP_PLATFORM_SAP_RFC_ENABLED=true