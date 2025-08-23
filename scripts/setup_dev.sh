#!/bin/bash

# Turkish Business Integration Platform - Development Setup
set -e

echo "🇹🇷 Turkish Business Integration Platform - Development Setup"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# Check dependencies
print_status "Checking dependencies..."

command -v docker >/dev/null 2>&1 || { 
    print_error "Docker gerekli. Lütfen Docker'ı yükleyin."
    exit 1; 
}

command -v docker-compose >/dev/null 2>&1 || { 
    print_error "Docker Compose gerekli. Lütfen Docker Compose'u yükleyin."
    exit 1; 
}

print_success "Dependencies check completed"

# Create environment file if it doesn't exist
if [ ! -f .env ]; then
    print_status "Creating environment configuration..."
    cp .env.example .env
    print_warning "⚠️  .env dosyasını ihtiyaçlarınıza göre düzenleyin"
else
    print_status "Environment file already exists"
fi

# Start infrastructure services
print_status "Starting infrastructure services..."
cd docker
docker-compose up -d postgres redis zookeeper kafka

# Wait for services to be ready
print_status "Waiting for services to start..."
sleep 30

# Check service health
print_status "Checking service health..."

# Check PostgreSQL
if docker-compose exec postgres pg_isready -U turkuser -d turkplatform >/dev/null 2>&1; then
    print_success "✅ PostgreSQL is ready"
else
    print_error "❌ PostgreSQL is not ready"
    exit 1
fi

# Check Redis
if docker-compose exec redis redis-cli ping >/dev/null 2>&1; then
    print_success "✅ Redis is ready"
else
    print_error "❌ Redis is not ready"  
    exit 1
fi

# Build and start API
print_status "Building and starting API..."
docker-compose up -d --build api

# Wait for API to start
print_status "Waiting for API to start..."
sleep 20

# Check API health
if curl -f http://localhost:8000/health >/dev/null 2>&1; then
    print_success "✅ API is ready"
else
    print_warning "⚠️  API might need more time to start"
fi

# Start monitoring services
print_status "Starting monitoring services..."
docker-compose up -d prometheus grafana

# Start worker
print_status "Starting background worker..."
docker-compose up -d worker

print_success "🎉 Development environment is ready!"

echo ""
echo "🔗 Available Services:"
echo "   📊 API Documentation: http://localhost:8000/docs"
echo "   💚 Health Check: http://localhost:8000/health"
echo "   📈 Prometheus: http://localhost:9090"
echo "   📊 Grafana: http://localhost:3000 (admin/turkpass)"
echo "   🗄️  PostgreSQL: localhost:5432 (turkuser/turkpass)"
echo "   🔴 Redis: localhost:6379"
echo ""
echo "⚡ Next Steps:"
echo "   1. Visit http://localhost:8000/docs for API documentation"
echo "   2. Check logs: docker-compose logs -f api"
echo "   3. Run tests: docker-compose exec api pytest"
echo "   4. Stop services: docker-compose down"
echo ""
print_success "Happy coding! 🚀"