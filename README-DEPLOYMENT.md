# 🚀 AIVideoMaker Deployment Guide

Complete deployment guide for AIVideoMaker with Docker containerization.

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Nginx Proxy   │────│   FastAPI App   │────│   PostgreSQL    │
│   (Port 80/443) │    │   (Port 8000)   │    │   (Port 5432)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │              ┌─────────────────┐    ┌─────────────────┐
         └──────────────│      Redis      │    │ Celery Workers  │
                        │   (Port 6379)   │    │  (Background)   │
                        └─────────────────┘    └─────────────────┘
```

## 📋 Prerequisites

- Docker & Docker Compose
- Domain name (for production)
- SSL certificate (Let's Encrypt recommended)
- SMTP email service
- OAuth app credentials (Google, Microsoft, Apple)
- Stripe account for payments

## 🚀 Quick Start

### 1. Production Deployment

```bash
# Clone the repository
git clone <your-repo-url>
cd AIVideoMaker

# Run production setup (installs Docker, generates secrets, etc.)
chmod +x scripts/setup-production.sh
./scripts/setup-production.sh

# Configure your environment
cp .env.example .env
nano .env  # Edit with your configuration

# Deploy the application
chmod +x scripts/deploy.sh
./scripts/deploy.sh deploy
```

### 2. Development Setup

```bash
# Start development environment
docker-compose -f docker-compose.dev.yml up -d

# Access the application
open http://localhost:8001
```

## 📁 File Structure

```
AIVideoMaker/
├── docker-compose.yml          # Production configuration
├── docker-compose.dev.yml      # Development configuration
├── Dockerfile                  # Production Docker image
├── Dockerfile.dev              # Development Docker image
├── .env.example               # Environment template
├── nginx/
│   ├── nginx.conf             # Nginx configuration
│   └── ssl/                   # SSL certificates
├── scripts/
│   ├── deploy.sh              # Deployment script
│   ├── setup-production.sh    # Production setup
│   └── init-db.sql           # Database initialization
└── app/                       # Application code
```

## ⚙️ Environment Configuration

### Required Environment Variables

```bash
# Security (generate with: openssl rand -hex 32)
SECRET_KEY=your-secret-key
JWT_SECRET_KEY=your-jwt-secret-key

# Database
POSTGRES_PASSWORD=your-postgres-password
DATABASE_URL=postgresql://postgres:password@postgres:5432/aivideomaker

# Redis
REDIS_HOST=redis
REDIS_PASSWORD=your-redis-password

# OAuth Providers
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
MICROSOFT_CLIENT_ID=your-microsoft-client-id
MICROSOFT_CLIENT_SECRET=your-microsoft-client-secret

# Stripe Payments
STRIPE_SECRET_KEY=sk_live_your-stripe-secret-key
STRIPE_WEBHOOK_SECRET=whsec_your-webhook-secret

# Email
EMAIL_USERNAME=your-email@domain.com
EMAIL_PASSWORD=your-app-password
ADMIN_EMAIL_ADDRESSES=admin@yourdomain.com

# Application URLs
BASE_URL=https://yourdomain.com
```

## 🛠️ Deployment Commands

### Using the Deploy Script

```bash
# Deploy application
./scripts/deploy.sh deploy

# View logs
./scripts/deploy.sh logs
./scripts/deploy.sh logs app

# Stop services
./scripts/deploy.sh stop

# Restart services
./scripts/deploy.sh restart

# Update application
./scripts/deploy.sh update

# Backup database
./scripts/deploy.sh backup

# Show status
./scripts/deploy.sh status
```

### Manual Docker Commands

```bash
# Build and start all services
docker-compose up -d --build

# View logs
docker-compose logs -f app

# Stop all services
docker-compose down

# Restart specific service
docker-compose restart app

# Run database migrations
docker-compose exec app alembic upgrade head

# Access application shell
docker-compose exec app bash
```

## 🔐 SSL/HTTPS Setup

### Option 1: Let's Encrypt (Recommended)

```bash
# Install certbot
sudo apt-get install certbot

# Get certificate
sudo certbot certonly --standalone -d yourdomain.com

# Copy certificates
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem nginx/ssl/cert.pem
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem nginx/ssl/key.pem

# Set permissions
sudo chown $USER:$USER nginx/ssl/*.pem

# Setup auto-renewal
echo "0 12 * * * /usr/bin/certbot renew --quiet && docker-compose restart nginx" | crontab -
```

### Option 2: Self-Signed (Development)

```bash
# Generate self-signed certificate
mkdir -p nginx/ssl
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout nginx/ssl/key.pem \
    -out nginx/ssl/cert.pem \
    -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"
```

## 📊 Monitoring & Maintenance

### Health Checks

```bash
# Check service health
curl -f http://localhost/health

# Check database connection
docker-compose exec postgres pg_isready -U postgres -d aivideomaker

# Check Redis connection
docker-compose exec redis redis-cli ping
```

### Performance Monitoring

```bash
# View resource usage
docker stats

# View application logs
docker-compose logs -f app

# Monitor database performance
docker-compose exec postgres psql -U postgres -d aivideomaker -c "SELECT * FROM pg_stat_activity;"
```

### Backup & Restore

```bash
# Backup database
docker-compose exec postgres pg_dump -U postgres aivideomaker > backup.sql

# Restore database
docker-compose exec -T postgres psql -U postgres aivideomaker < backup.sql

# Backup uploaded files
tar -czf uploads-backup.tar.gz -C /var/lib/docker/volumes/aivideomaker_app_uploads/_data .
```

## 🔧 Troubleshooting

### Common Issues

**Service won't start:**
```bash
# Check logs
docker-compose logs service_name

# Check service status
docker-compose ps

# Rebuild image
docker-compose build --no-cache service_name
```

**Database connection issues:**
```bash
# Check database logs
docker-compose logs postgres

# Connect to database directly
docker-compose exec postgres psql -U postgres -d aivideomaker

# Reset database
docker-compose down -v
docker-compose up -d postgres
```

**SSL certificate issues:**
```bash
# Check certificate validity
openssl x509 -in nginx/ssl/cert.pem -text -noout

# Test SSL configuration
curl -k https://localhost
```

### Log Locations

- Application logs: `docker-compose logs app`
- Nginx logs: `docker-compose logs nginx`
- Database logs: `docker-compose logs postgres`
- Redis logs: `docker-compose logs redis`

## 🔄 Updates & Maintenance

### Update Application

```bash
# Method 1: Using deploy script
./scripts/deploy.sh update

# Method 2: Manual update
git pull origin main
docker-compose down
docker-compose build --no-cache
docker-compose up -d
docker-compose exec app alembic upgrade head
```

### Database Migrations

```bash
# Create new migration
docker-compose exec app alembic revision --autogenerate -m "Description"

# Apply migrations
docker-compose exec app alembic upgrade head

# View migration history
docker-compose exec app alembic history
```

## 🌐 Domain & DNS Setup

1. Point your domain's A record to your server's IP
2. Configure your domain in `.env`:
   ```bash
   BASE_URL=https://yourdomain.com
   FRONTEND_URL=https://yourdomain.com
   ```
3. Update CORS origins:
   ```bash
   CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
   ```

## 📈 Scaling

### Horizontal Scaling

```bash
# Scale application containers
docker-compose up -d --scale app=3

# Use load balancer (Nginx upstream)
# Edit nginx/nginx.conf to add multiple app servers
```

### Resource Limits

```yaml
# Add to docker-compose.yml
services:
  app:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
        reservations:
          memory: 1G
```

## 🔒 Security Checklist

- [ ] Strong passwords in `.env`
- [ ] SSL certificate configured
- [ ] Firewall rules configured
- [ ] Regular security updates
- [ ] Backup strategy implemented
- [ ] Rate limiting configured
- [ ] Admin access restricted
- [ ] Environment variables secured
- [ ] Database access restricted
- [ ] Logs monitoring enabled

## 📞 Support

For deployment issues:

1. Check the troubleshooting section
2. Review service logs
3. Verify environment configuration
4. Check domain and SSL setup
5. Contact support with error logs

---

🎉 **Congratulations!** Your AIVideoMaker application is now ready for production use.