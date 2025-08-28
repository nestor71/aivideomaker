#!/bin/bash

# ==============================================
# AIVideoMaker Production Setup Script
# ==============================================

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

log() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   error "This script should not be run as root for security reasons."
fi

# Check operating system
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="linux"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
else
    error "Unsupported operating system: $OSTYPE"
fi

log "Setting up AIVideoMaker for production on $OS..."

# Install Docker if not present
install_docker() {
    if ! command -v docker &> /dev/null; then
        log "Installing Docker..."
        
        if [[ "$OS" == "linux" ]]; then
            # Install Docker on Linux
            curl -fsSL https://get.docker.com -o get-docker.sh
            sh get-docker.sh
            sudo usermod -aG docker $USER
            rm get-docker.sh
            
            # Install Docker Compose
            sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
            sudo chmod +x /usr/local/bin/docker-compose
            
        elif [[ "$OS" == "macos" ]]; then
            # Install Docker Desktop on macOS
            if command -v brew &> /dev/null; then
                brew install --cask docker
            else
                error "Please install Homebrew first or install Docker Desktop manually"
            fi
        fi
        
        success "Docker installed successfully"
        warning "Please log out and back in, or restart your system, then run this script again"
        exit 0
    else
        success "Docker is already installed"
    fi
}

# Setup firewall rules (Linux only)
setup_firewall() {
    if [[ "$OS" == "linux" ]] && command -v ufw &> /dev/null; then
        log "Setting up firewall rules..."
        
        # Enable UFW if not already enabled
        sudo ufw --force enable
        
        # Allow SSH
        sudo ufw allow ssh
        
        # Allow HTTP and HTTPS
        sudo ufw allow 80/tcp
        sudo ufw allow 443/tcp
        
        # Optionally allow direct access to app (for debugging)
        # sudo ufw allow 8000/tcp
        
        # Show status
        sudo ufw status
        
        success "Firewall configured"
    fi
}

# Setup SSL certificates with Let's Encrypt
setup_letsencrypt() {
    read -p "Do you want to setup Let's Encrypt SSL certificates? (y/N): " -r
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        read -p "Enter your domain name: " DOMAIN
        read -p "Enter your email for Let's Encrypt: " EMAIL
        
        if [[ -z "$DOMAIN" || -z "$EMAIL" ]]; then
            error "Domain and email are required for Let's Encrypt"
        fi
        
        log "Setting up Let's Encrypt SSL for $DOMAIN..."
        
        # Install certbot
        if [[ "$OS" == "linux" ]]; then
            if command -v apt-get &> /dev/null; then
                sudo apt-get update
                sudo apt-get install -y certbot
            elif command -v yum &> /dev/null; then
                sudo yum install -y certbot
            fi
        elif [[ "$OS" == "macos" ]]; then
            if command -v brew &> /dev/null; then
                brew install certbot
            fi
        fi
        
        # Get certificate
        sudo certbot certonly --standalone -d $DOMAIN --email $EMAIL --agree-tos --non-interactive
        
        # Copy certificates to nginx directory
        sudo mkdir -p nginx/ssl
        sudo cp /etc/letsencrypt/live/$DOMAIN/fullchain.pem nginx/ssl/cert.pem
        sudo cp /etc/letsencrypt/live/$DOMAIN/privkey.pem nginx/ssl/key.pem
        sudo chown $USER:$USER nginx/ssl/*.pem
        
        success "SSL certificates configured for $DOMAIN"
        
        # Setup auto-renewal
        (crontab -l 2>/dev/null; echo "0 12 * * * /usr/bin/certbot renew --quiet && docker-compose restart nginx") | crontab -
        success "Auto-renewal configured"
    fi
}

# Generate secure secrets
generate_secrets() {
    if [ ! -f ".env" ]; then
        log "Generating secure secrets..."
        
        cp .env.example .env
        
        # Generate secure secrets
        SECRET_KEY=$(openssl rand -hex 32)
        JWT_SECRET_KEY=$(openssl rand -hex 32)
        POSTGRES_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-25)
        REDIS_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-25)
        
        # Update .env file
        sed -i.bak "s/your-super-secret-key-here/$SECRET_KEY/g" .env
        sed -i.bak "s/your-jwt-secret-key-here/$JWT_SECRET_KEY/g" .env
        sed -i.bak "s/your-strong-postgres-password/$POSTGRES_PASSWORD/g" .env
        sed -i.bak "s/your-strong-redis-password/$REDIS_PASSWORD/g" .env
        
        # Update database URL
        sed -i.bak "s/your-strong-postgres-password/$POSTGRES_PASSWORD/g" .env
        
        # Remove backup file
        rm .env.bak
        
        success "Secure secrets generated"
        warning "Please complete the .env configuration with your OAuth, Stripe, and email settings"
    else
        warning ".env file already exists, skipping secret generation"
    fi
}

# Setup monitoring (optional)
setup_monitoring() {
    read -p "Do you want to setup basic monitoring with Prometheus and Grafana? (y/N): " -r
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log "Setting up monitoring stack..."
        
        # Create monitoring docker-compose file
        cat > docker-compose.monitoring.yml << EOF
version: '3.8'
services:
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    networks:
      - aivideomaker-network

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3001:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin123
    volumes:
      - grafana_data:/var/lib/grafana
    networks:
      - aivideomaker-network

volumes:
  prometheus_data:
  grafana_data:

networks:
  aivideomaker-network:
    external: true
EOF

        # Create monitoring directory and basic config
        mkdir -p monitoring
        cat > monitoring/prometheus.yml << EOF
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'aivideomaker'
    static_configs:
      - targets: ['app:8000']
EOF

        success "Monitoring stack configured. Access Grafana at http://localhost:3001 (admin/admin123)"
    fi
}

# System optimization
optimize_system() {
    if [[ "$OS" == "linux" ]]; then
        log "Optimizing system for production..."
        
        # Update system
        if command -v apt-get &> /dev/null; then
            sudo apt-get update && sudo apt-get upgrade -y
        elif command -v yum &> /dev/null; then
            sudo yum update -y
        fi
        
        # Install useful packages
        if command -v apt-get &> /dev/null; then
            sudo apt-get install -y htop curl wget git unzip fail2ban
        elif command -v yum &> /dev/null; then
            sudo yum install -y htop curl wget git unzip fail2ban
        fi
        
        # Configure fail2ban for basic security
        sudo systemctl enable fail2ban
        sudo systemctl start fail2ban
        
        success "System optimized"
    fi
}

# Main setup process
main() {
    log "Starting AIVideoMaker production setup..."
    
    # Check for required files
    if [ ! -f "docker-compose.yml" ]; then
        error "docker-compose.yml not found. Make sure you're in the project directory."
    fi
    
    # Install Docker
    install_docker
    
    # Generate secrets
    generate_secrets
    
    # System optimization
    optimize_system
    
    # Setup firewall
    setup_firewall
    
    # Setup SSL
    setup_letsencrypt
    
    # Optional monitoring
    setup_monitoring
    
    # Final instructions
    echo ""
    echo "=============================================="
    echo "🎉 Production setup completed!"
    echo "=============================================="
    echo ""
    echo "Next steps:"
    echo "1. Complete your .env configuration:"
    echo "   - OAuth credentials (Google, Microsoft, Apple)"
    echo "   - Stripe payment keys"
    echo "   - Email settings"
    echo "   - Domain URLs"
    echo ""
    echo "2. Deploy the application:"
    echo "   ./scripts/deploy.sh deploy"
    echo ""
    echo "3. Access your application:"
    echo "   https://your-domain.com"
    echo ""
    echo "4. Setup monitoring (if enabled):"
    echo "   docker-compose -f docker-compose.monitoring.yml up -d"
    echo ""
    echo "=============================================="
    
    success "Setup completed successfully!"
}

# Run main function
main "$@"