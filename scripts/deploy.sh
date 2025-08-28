#!/bin/bash

# ==============================================
# AIVideoMaker Deployment Script
# ==============================================

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Check if Docker is installed
check_docker() {
    if ! command -v docker &> /dev/null; then
        error "Docker is not installed. Please install Docker first."
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        error "Docker Compose is not installed. Please install Docker Compose first."
    fi
    
    success "Docker and Docker Compose are installed"
}

# Check if .env file exists
check_env() {
    if [ ! -f ".env" ]; then
        warning ".env file not found"
        log "Creating .env from .env.example..."
        
        if [ -f ".env.example" ]; then
            cp .env.example .env
            warning "Please edit .env file with your configuration before running the application"
            echo "Key variables to configure:"
            echo "  - SECRET_KEY and JWT_SECRET_KEY (generate with: openssl rand -hex 32)"
            echo "  - POSTGRES_PASSWORD and REDIS_PASSWORD"
            echo "  - OAuth credentials (Google, Microsoft, Apple)"
            echo "  - Stripe keys for payments"
            echo "  - Email configuration"
            echo "  - BASE_URL and FRONTEND_URL"
            return 1
        else
            error ".env.example file not found"
        fi
    else
        success ".env file found"
    fi
}

# Generate SSL certificates (self-signed for development)
generate_ssl() {
    log "Setting up SSL certificates..."
    
    mkdir -p nginx/ssl
    
    if [ ! -f "nginx/ssl/cert.pem" ] || [ ! -f "nginx/ssl/key.pem" ]; then
        log "Generating self-signed SSL certificate..."
        
        openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
            -keyout nginx/ssl/key.pem \
            -out nginx/ssl/cert.pem \
            -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"
        
        success "SSL certificate generated"
        warning "Using self-signed certificate. Replace with proper SSL certificate in production."
    else
        success "SSL certificates already exist"
    fi
}

# Build and start services
deploy() {
    log "Starting AIVideoMaker deployment..."
    
    # Build images
    log "Building Docker images..."
    docker-compose build --no-cache
    
    # Start services
    log "Starting services..."
    docker-compose up -d
    
    # Wait for services to be ready
    log "Waiting for services to start..."
    sleep 10
    
    # Check service health
    log "Checking service health..."
    
    # Check PostgreSQL
    if docker-compose exec postgres pg_isready -U postgres -d aivideomaker > /dev/null 2>&1; then
        success "PostgreSQL is ready"
    else
        warning "PostgreSQL might not be ready yet"
    fi
    
    # Check Redis
    if docker-compose exec redis redis-cli ping > /dev/null 2>&1; then
        success "Redis is ready"
    else
        warning "Redis might not be ready yet"
    fi
    
    # Run database migrations
    log "Running database migrations..."
    docker-compose exec app alembic upgrade head
    
    success "Deployment completed successfully!"
    
    # Show access information
    echo ""
    echo "==============================================  "
    echo "🚀 AIVideoMaker is now running!"
    echo "=============================================="
    echo "📱 Application: https://localhost (or your domain)"
    echo "🔧 Admin Dashboard: https://localhost/admin"
    echo "📊 API Documentation: https://localhost/docs"
    echo "=============================================="
    echo ""
    echo "📋 Service Status:"
    docker-compose ps
}

# Stop services
stop() {
    log "Stopping AIVideoMaker services..."
    docker-compose down
    success "Services stopped"
}

# Restart services
restart() {
    log "Restarting AIVideoMaker services..."
    docker-compose restart
    success "Services restarted"
}

# View logs
logs() {
    if [ -n "$1" ]; then
        docker-compose logs -f "$1"
    else
        docker-compose logs -f
    fi
}

# Update application
update() {
    log "Updating AIVideoMaker..."
    
    # Pull latest code (if using git)
    if [ -d ".git" ]; then
        git pull origin main
    fi
    
    # Rebuild and restart
    docker-compose down
    docker-compose build --no-cache
    docker-compose up -d
    
    # Run migrations
    sleep 10
    docker-compose exec app alembic upgrade head
    
    success "Update completed"
}

# Backup database
backup() {
    log "Creating database backup..."
    
    BACKUP_FILE="backup_$(date +%Y%m%d_%H%M%S).sql"
    
    docker-compose exec postgres pg_dump -U postgres aivideomaker > "$BACKUP_FILE"
    
    success "Database backup saved as $BACKUP_FILE"
}

# Show help
show_help() {
    echo "AIVideoMaker Deployment Script"
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  deploy    - Deploy the application (build and start all services)"
    echo "  stop      - Stop all services"
    echo "  restart   - Restart all services"
    echo "  logs      - Show logs from all services"
    echo "  logs [service] - Show logs from specific service"
    echo "  update    - Update and redeploy the application"
    echo "  backup    - Create database backup"
    echo "  ssl       - Generate SSL certificates"
    echo "  status    - Show service status"
    echo "  help      - Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 deploy         # Deploy the application"
    echo "  $0 logs app       # Show application logs"
    echo "  $0 logs postgres  # Show database logs"
}

# Show status
show_status() {
    echo "AIVideoMaker Service Status:"
    echo "============================"
    docker-compose ps
    echo ""
    echo "Resource Usage:"
    echo "==============="
    docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" $(docker-compose ps -q) 2>/dev/null || echo "Unable to show resource usage"
}

# Main script logic
case "$1" in
    deploy)
        check_docker
        if ! check_env; then
            error "Please configure .env file before deploying"
        fi
        generate_ssl
        deploy
        ;;
    stop)
        stop
        ;;
    restart)
        restart
        ;;
    logs)
        logs "$2"
        ;;
    update)
        update
        ;;
    backup)
        backup
        ;;
    ssl)
        generate_ssl
        ;;
    status)
        show_status
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo "Unknown command: $1"
        echo ""
        show_help
        exit 1
        ;;
esac