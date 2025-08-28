# AIVideoMaker Makefile

.PHONY: help test test-auth test-subscription test-admin test-integration test-coverage lint format clean docker-test

help:
	@echo "Available commands:"
	@echo "  test              - Run all tests"
	@echo "  test-auth         - Run authentication tests"
	@echo "  test-subscription - Run subscription tests"
	@echo "  test-admin        - Run admin tests"
	@echo "  test-integration  - Run integration tests"
	@echo "  test-coverage     - Run tests with coverage report"
	@echo "  lint              - Run code linting"
	@echo "  format            - Format code with black"
	@echo "  docker-test       - Run tests in Docker environment"
	@echo "  clean             - Clean up temporary files"

# Test commands
test:
	pytest -v

test-auth:
	pytest -v tests/test_auth.py -m auth

test-subscription:
	pytest -v tests/test_subscription.py tests/test_tier_limits.py -m subscription

test-admin:
	pytest -v tests/test_admin.py -m admin

test-integration:
	pytest -v tests/test_integration.py -m integration

test-coverage:
	pytest --cov=app --cov-report=html --cov-report=term -v

# Code quality
lint:
	flake8 app/ tests/
	mypy app/

format:
	black app/ tests/
	isort app/ tests/

# Docker test environment
docker-test:
	docker-compose -f docker-compose.dev.yml exec app-dev pytest -v

docker-test-coverage:
	docker-compose -f docker-compose.dev.yml exec app-dev pytest --cov=app --cov-report=html --cov-report=term -v

# Development helpers
dev-setup:
	pip install -r requirements.txt
	pip install pytest pytest-asyncio fakeredis httpx pytest-cov black flake8 mypy isort

dev-db-reset:
	docker-compose -f docker-compose.dev.yml exec postgres-dev psql -U postgres -c "DROP DATABASE IF EXISTS aivideomaker_dev; CREATE DATABASE aivideomaker_dev;"

dev-logs:
	docker-compose -f docker-compose.dev.yml logs -f app-dev

# Cleanup
clean:
	find . -type d -name "__pycache__" -delete
	find . -type f -name "*.pyc" -delete
	find . -type f -name ".coverage" -delete
	find . -type d -name "htmlcov" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type f -name "test.db" -delete

# Production deployment
deploy-prod:
	./scripts/deploy.sh deploy

deploy-dev:
	docker-compose -f docker-compose.dev.yml up -d --build

stop-dev:
	docker-compose -f docker-compose.dev.yml down

restart-dev:
	docker-compose -f docker-compose.dev.yml restart

# Database operations
db-migrate:
	docker-compose -f docker-compose.dev.yml exec app-dev alembic upgrade head

db-revision:
	docker-compose -f docker-compose.dev.yml exec app-dev alembic revision --autogenerate -m "$(MESSAGE)"

db-downgrade:
	docker-compose -f docker-compose.dev.yml exec app-dev alembic downgrade -1