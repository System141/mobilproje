#!/bin/bash

# Cython Build Script for ERP Platform
# Builds optimized Cython extensions for production deployment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
BUILD_TYPE="release"
PARALLEL_JOBS=$(nproc)
CLEAN_BUILD=false
PROFILE_BUILD=false
ANNOTATE=false

# Function to print usage
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Build Cython extensions for ERP Platform"
    echo ""
    echo "Options:"
    echo "  -t, --type TYPE          Build type: debug, release (default: release)"
    echo "  -j, --jobs JOBS          Number of parallel jobs (default: $(nproc))"
    echo "  -c, --clean              Clean build directory before building"
    echo "  -p, --profile            Enable profiling in Cython modules"
    echo "  -a, --annotate           Generate HTML annotation files"
    echo "  -h, --help               Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                       # Release build with default settings"
    echo "  $0 -t debug -p -a        # Debug build with profiling and annotations"
    echo "  $0 -c -j 8               # Clean release build with 8 parallel jobs"
}

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -t|--type)
            BUILD_TYPE="$2"
            shift 2
            ;;
        -j|--jobs)
            PARALLEL_JOBS="$2"
            shift 2
            ;;
        -c|--clean)
            CLEAN_BUILD=true
            shift
            ;;
        -p|--profile)
            PROFILE_BUILD=true
            shift
            ;;
        -a|--annotate)
            ANNOTATE=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Validate build type
if [[ ! "$BUILD_TYPE" =~ ^(debug|release)$ ]]; then
    print_error "Invalid build type: $BUILD_TYPE. Must be: debug, release"
    exit 1
fi

print_status "Building Cython extensions for ERP Platform"
echo "  Build type: $BUILD_TYPE"
echo "  Parallel jobs: $PARALLEL_JOBS"
echo "  Clean build: $CLEAN_BUILD"
echo "  Profile build: $PROFILE_BUILD"
echo "  Generate annotations: $ANNOTATE"
echo ""

# Check dependencies
print_status "Checking dependencies..."

if ! python -c "import Cython" 2>/dev/null; then
    print_error "Cython not found. Install with: pip install cython"
    exit 1
fi

if ! python -c "import numpy" 2>/dev/null; then
    print_error "NumPy not found. Install with: pip install numpy"
    exit 1
fi

print_success "All dependencies found"

# Clean build directory if requested
if [[ "$CLEAN_BUILD" == true ]]; then
    print_status "Cleaning build directory..."
    rm -rf build/
    rm -rf src/erp_platform/cython_modules/*.c
    rm -rf src/erp_platform/cython_modules/*.so
    rm -rf src/erp_platform/cython_modules/*.html
    print_success "Build directory cleaned"
fi

# Set up environment variables
export CYTHONIZE_FORCE=1
export CYTHON_TRACE=0

if [[ "$PROFILE_BUILD" == true ]]; then
    export CYTHON_TRACE=1
    print_status "Profiling enabled in Cython modules"
fi

# Prepare build command
BUILD_CMD="python setup_cython.py build_ext --inplace"

if [[ "$PARALLEL_JOBS" -gt 1 ]]; then
    BUILD_CMD="$BUILD_CMD --parallel $PARALLEL_JOBS"
fi

# Set compiler optimizations based on build type
if [[ "$BUILD_TYPE" == "release" ]]; then
    export CFLAGS="-O3 -march=native -ffast-math -DNDEBUG"
    export CPPFLAGS="-O3 -march=native -ffast-math -DNDEBUG"
    print_status "Using release optimizations (-O3 -march=native)"
else
    export CFLAGS="-O0 -g -DDEBUG"
    export CPPFLAGS="-O0 -g -DDEBUG"
    print_status "Using debug settings (-O0 -g)"
fi

# Create build directory
mkdir -p build/cython

# Execute build
print_status "Building Cython extensions..."
echo "Command: $BUILD_CMD"
echo ""

if ! eval "$BUILD_CMD"; then
    print_error "Cython build failed!"
    exit 1
fi

print_success "Cython extensions built successfully"

# Generate annotations if requested
if [[ "$ANNOTATE" == true ]]; then
    print_status "Generating HTML annotations..."
    
    # Re-run with annotation enabled
    python -c "
import os
os.environ['CYTHON_ANNOTATE'] = '1'
exec(open('setup_cython.py').read())
"
    
    if ls src/erp_platform/cython_modules/*.html >/dev/null 2>&1; then
        print_success "HTML annotations generated in src/erp_platform/cython_modules/"
    else
        print_warning "No HTML annotations found"
    fi
fi

# Verify build results
print_status "Verifying build results..."
BUILT_MODULES=0

for module in csv_processor_cy json_processor_cy sap_transformer_cy math_utils_cy string_utils_cy; do
    if ls src/erp_platform/cython_modules/${module}.*.so >/dev/null 2>&1 || \
       ls src/erp_platform/cython_modules/${module}.pyd >/dev/null 2>&1; then
        print_success "✓ ${module} built successfully"
        BUILT_MODULES=$((BUILT_MODULES + 1))
    else
        print_warning "✗ ${module} not found"
    fi
done

echo ""
print_success "Build completed: $BUILT_MODULES/5 modules built"

# Performance test
print_status "Running performance test..."
python -c "
try:
    from erp_platform.cython_modules import CYTHON_AVAILABLE
    if CYTHON_AVAILABLE:
        print('✓ Cython modules are available and importable')
        
        # Quick performance test
        import time
        import numpy as np
        from erp_platform.cython_modules import fast_sum
        
        # Test data
        test_data = np.random.random(100000)
        
        # Cython version
        start = time.time()
        result_cy = fast_sum(test_data)
        cython_time = time.time() - start
        
        # NumPy version
        start = time.time()
        result_np = np.sum(test_data)
        numpy_time = time.time() - start
        
        speedup = numpy_time / cython_time if cython_time > 0 else 1
        print(f'Performance test: {speedup:.2f}x speedup over NumPy')
    else:
        print('✗ Cython modules not available - falling back to Python')
except Exception as e:
    print(f'✗ Performance test failed: {e}')
"

# Show next steps
echo ""
print_status "Next steps:"
echo "  # Test the installation:"
echo "  python -c \"from erp_platform.cython_modules import CYTHON_AVAILABLE; print('Cython available:', CYTHON_AVAILABLE)\""
echo ""
echo "  # Run performance benchmarks:"
echo "  python scripts/benchmark_cython.py"
echo ""
echo "  # For production deployment:"
echo "  pip install -e ."
echo "  python -c \"import erp_platform.cython_modules; print('Production modules loaded')\""

if [[ "$BUILD_TYPE" == "debug" ]]; then
    echo ""
    print_warning "Debug build completed. For production, use:"
    echo "  $0 -t release -c"
fi

print_success "Cython build process completed!"