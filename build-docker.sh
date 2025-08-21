#!/bin/bash

# Docker Build Script for ERP Integration Platform
# Supports multiple build variants with optional SAP connectivity

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
VARIANT="base"
TAG_PREFIX="erp-platform"
PUSH_TO_REGISTRY=false
REGISTRY=""
SAP_SDK_PATH=""

# Function to print usage
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Build ERP Integration Platform Docker images with different SAP connectivity options"
    echo ""
    echo "Options:"
    echo "  -v, --variant VARIANT     Build variant: base, sap-rest, sap-rfc (default: base)"
    echo "  -t, --tag TAG_PREFIX      Image tag prefix (default: erp-platform)"
    echo "  -p, --push                Push to container registry"
    echo "  -r, --registry REGISTRY   Container registry URL"
    echo "  -s, --sap-sdk PATH        Path to SAP NetWeaver RFC SDK (for RFC variant)"
    echo "  -h, --help                Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Build base variant"
    echo "  $0 -v sap-rest                       # Build SAP REST variant"
    echo "  $0 -v sap-rfc -s /opt/nwrfcsdk      # Build SAP RFC variant with SDK"
    echo "  $0 -v sap-rest -p -r my-registry.io # Build and push to registry"
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
        -v|--variant)
            VARIANT="$2"
            shift 2
            ;;
        -t|--tag)
            TAG_PREFIX="$2"
            shift 2
            ;;
        -p|--push)
            PUSH_TO_REGISTRY=true
            shift
            ;;
        -r|--registry)
            REGISTRY="$2"
            shift 2
            ;;
        -s|--sap-sdk)
            SAP_SDK_PATH="$2"
            shift 2
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

# Validate variant
if [[ ! "$VARIANT" =~ ^(base|sap-rest|sap-rfc)$ ]]; then
    print_error "Invalid variant: $VARIANT. Must be one of: base, sap-rest, sap-rfc"
    exit 1
fi

# Validate SAP SDK path for RFC variant
if [[ "$VARIANT" == "sap-rfc" && -z "$SAP_SDK_PATH" ]]; then
    print_error "SAP SDK path is required for RFC variant. Use -s option."
    exit 1
fi

if [[ "$VARIANT" == "sap-rfc" && ! -d "$SAP_SDK_PATH" ]]; then
    print_error "SAP SDK path does not exist: $SAP_SDK_PATH"
    exit 1
fi

# Set build arguments based on variant
BUILD_ARGS=""
TARGET="production"
case $VARIANT in
    "base")
        BUILD_ARGS="--build-arg BUILD_VARIANT=base --build-arg INCLUDE_SAP_RFC=false --build-arg INCLUDE_SAP_REST=false"
        TARGET="base"
        ;;
    "sap-rest")
        BUILD_ARGS="--build-arg BUILD_VARIANT=sap-rest --build-arg INCLUDE_SAP_RFC=false --build-arg INCLUDE_SAP_REST=true"
        TARGET="sap-rest"
        ;;
    "sap-rfc")
        BUILD_ARGS="--build-arg BUILD_VARIANT=sap-rfc --build-arg INCLUDE_SAP_RFC=true --build-arg INCLUDE_SAP_REST=true"
        TARGET="sap-rfc"
        ;;
esac

# Set image tag
if [[ -n "$REGISTRY" ]]; then
    IMAGE_TAG="$REGISTRY/$TAG_PREFIX:$VARIANT"
else
    IMAGE_TAG="$TAG_PREFIX:$VARIANT"
fi

# Print build information
print_status "Building ERP Integration Platform"
echo "  Variant: $VARIANT"
echo "  Target: $TARGET"
echo "  Image tag: $IMAGE_TAG"
if [[ "$VARIANT" == "sap-rfc" ]]; then
    echo "  SAP SDK path: $SAP_SDK_PATH"
fi
echo ""

# Build command construction
BUILD_CMD="docker build"
BUILD_CMD="$BUILD_CMD --target $TARGET"
BUILD_CMD="$BUILD_CMD $BUILD_ARGS"
BUILD_CMD="$BUILD_CMD -t $IMAGE_TAG"

# Add SAP SDK mount for RFC variant
if [[ "$VARIANT" == "sap-rfc" ]]; then
    BUILD_CMD="$BUILD_CMD --mount type=bind,source=$SAP_SDK_PATH,target=/opt/nwrfcsdk"
fi

BUILD_CMD="$BUILD_CMD ."

# Execute build
print_status "Executing build command:"
echo "  $BUILD_CMD"
echo ""

if ! eval "$BUILD_CMD"; then
    print_error "Build failed!"
    exit 1
fi

print_success "Build completed: $IMAGE_TAG"

# Push to registry if requested
if [[ "$PUSH_TO_REGISTRY" == true ]]; then
    if [[ -z "$REGISTRY" ]]; then
        print_error "Registry URL is required for push operation. Use -r option."
        exit 1
    fi
    
    print_status "Pushing image to registry: $REGISTRY"
    
    if ! docker push "$IMAGE_TAG"; then
        print_error "Push failed!"
        exit 1
    fi
    
    print_success "Image pushed: $IMAGE_TAG"
fi

# Show next steps
echo ""
print_status "Next steps:"
case $VARIANT in
    "base")
        echo "  # Run the container:"
        echo "  docker run -p 8000:8000 $IMAGE_TAG"
        echo ""
        echo "  # Or use docker-compose:"
        echo "  docker-compose up app"
        ;;
    "sap-rest")
        echo "  # Run the container:"
        echo "  docker run -p 8000:8000 -e SAP_CONNECTION_MODE=rest $IMAGE_TAG"
        echo ""
        echo "  # Or use docker-compose:"
        echo "  docker-compose --profile sap-rest up app-sap-rest"
        ;;
    "sap-rfc")
        echo "  # Run the container with SAP SDK mounted:"
        echo "  docker run -p 8000:8000 -v $SAP_SDK_PATH:/opt/nwrfcsdk:ro \\"
        echo "    -e SAP_CONNECTION_MODE=rfc $IMAGE_TAG"
        echo ""
        echo "  # Or use docker-compose:"
        echo "  docker-compose --profile sap-rfc up app-sap-rfc"
        ;;
esac

echo ""
print_status "For more information, see DOCKER_BUILD_GUIDE.md"