"""
Test configuration and fixtures for AIVideoMaker
"""
import os
import tempfile
import pytest
import asyncio
from datetime import datetime, timedelta
from typing import Generator, AsyncGenerator
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.base import Base, get_session
from app.core.config import settings
from main import app


# Test database URL - use in-memory SQLite for tests
TEST_DATABASE_URL = "sqlite:///./test.db"

# Create test engine
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    """Override database dependency for tests"""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database for each test"""
    Base.metadata.create_all(bind=test_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def client(db_session) -> Generator[TestClient, None, None]:
    """Create a test client with database override"""
    app.dependency_overrides[get_session] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()


@pytest.fixture
def test_user_data():
    """Sample user data for tests"""
    return {
        "email": "testuser@example.com",
        "password": "TestPass123",
        "full_name": "Test User"
    }


@pytest.fixture
def test_premium_user_data():
    """Sample premium user data for tests"""
    return {
        "email": "premiumuser@example.com",
        "password": "PremiumPass123",
        "full_name": "Premium User"
    }


@pytest.fixture
def test_admin_user_data():
    """Sample admin user data for tests"""
    return {
        "email": "admin@example.com",
        "password": "AdminPass123",
        "full_name": "Admin User"
    }


@pytest.fixture
def auth_headers(client: TestClient, test_user_data):
    """Get authorization headers for a test user"""
    # Register user
    response = client.post("/api/auth/register", json=test_user_data)
    assert response.status_code == 200
    
    # Login to get token
    login_data = {
        "email": test_user_data["email"],
        "password": test_user_data["password"]
    }
    response = client.post("/api/auth/login", json=login_data)
    assert response.status_code == 200
    
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def premium_auth_headers(client: TestClient, test_premium_user_data, db_session):
    """Get authorization headers for a premium test user"""
    from app.database.models import User, Subscription, SubscriptionTier, SubscriptionStatus
    from app.services.auth_service import AuthService
    
    # Register premium user
    response = client.post("/api/auth/register", json=test_premium_user_data)
    assert response.status_code == 200
    
    # Update user to premium in database
    user = db_session.query(User).filter(User.email == test_premium_user_data["email"]).first()
    
    # Create premium subscription
    subscription = Subscription(
        user_id=user.id,
        tier=SubscriptionTier.PREMIUM,
        status=SubscriptionStatus.ACTIVE,
        stripe_subscription_id="test_sub_premium",
        current_period_start=datetime.utcnow(),
        current_period_end=datetime.utcnow() + timedelta(days=30)
    )
    db_session.add(subscription)
    db_session.commit()
    
    # Login to get token
    login_data = {
        "email": test_premium_user_data["email"],
        "password": test_premium_user_data["password"]
    }
    response = client.post("/api/auth/login", json=login_data)
    assert response.status_code == 200
    
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_auth_headers(client: TestClient, test_admin_user_data, db_session):
    """Get authorization headers for an admin test user"""
    from app.database.models import User, UserRole
    
    # Register admin user
    response = client.post("/api/auth/register", json=test_admin_user_data)
    assert response.status_code == 200
    
    # Update user to admin in database
    user = db_session.query(User).filter(User.email == test_admin_user_data["email"]).first()
    user.role = UserRole.ADMIN
    db_session.commit()
    
    # Login to get token
    login_data = {
        "email": test_admin_user_data["email"],
        "password": test_admin_user_data["password"]
    }
    response = client.post("/api/auth/login", json=login_data)
    assert response.status_code == 200
    
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sample_video_file():
    """Create a sample video file for testing"""
    # For testing purposes, we'll create a small test file
    # In real tests, you might want to use actual video files
    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as f:
        f.write(b'fake video content for testing')
        return f.name


@pytest.fixture
def sample_image_file():
    """Create a sample image file for testing"""
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
        f.write(b'fake image content for testing')
        return f.name


@pytest.fixture(autouse=True)
def cleanup_temp_files():
    """Clean up temporary files after each test"""
    temp_files = []
    yield temp_files
    
    # Cleanup
    for file_path in temp_files:
        try:
            os.unlink(file_path)
        except (OSError, FileNotFoundError):
            pass


# Mock external services for testing
@pytest.fixture
def mock_stripe():
    """Mock Stripe service for testing"""
    from unittest.mock import Mock, patch
    
    with patch('app.services.stripe_service.stripe') as mock_stripe:
        # Mock Stripe subscription creation
        mock_stripe.Subscription.create.return_value = {
            'id': 'sub_test123',
            'status': 'active',
            'current_period_start': 1234567890,
            'current_period_end': 1234567890 + 2592000  # +30 days
        }
        
        # Mock Stripe customer creation
        mock_stripe.Customer.create.return_value = {
            'id': 'cus_test123'
        }
        
        # Mock Stripe payment intent creation
        mock_stripe.PaymentIntent.create.return_value = {
            'id': 'pi_test123',
            'client_secret': 'pi_test123_secret_test'
        }
        
        yield mock_stripe


@pytest.fixture
def mock_email_service():
    """Mock email service for testing"""
    from unittest.mock import Mock, patch
    
    with patch('app.services.email_service.EmailService.send_email') as mock_send:
        mock_send.return_value = True
        yield mock_send


@pytest.fixture
def mock_redis():
    """Mock Redis for testing"""
    from unittest.mock import Mock, patch
    import fakeredis
    
    fake_redis = fakeredis.FakeRedis()
    
    with patch('app.services.rate_limiter.redis_client', fake_redis):
        yield fake_redis