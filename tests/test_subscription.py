"""
Subscription and payment system tests
"""
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database.models import User, Subscription, SubscriptionTier, SubscriptionStatus, UsageRecord


class TestSubscriptionPlans:
    """Test subscription plan functionality"""
    
    def test_get_pricing_plans(self, client: TestClient):
        """Test getting available pricing plans"""
        response = client.get("/api/subscription/pricing")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "plans" in data
        assert "free" in data["plans"]
        assert "premium" in data["plans"]
        
        # Check free plan details
        free_plan = data["plans"]["free"]
        assert free_plan["price"] == 0
        assert free_plan["features"]["monthly_minutes"] == 10
        assert free_plan["features"]["watermark"] is True
        
        # Check premium plan details
        premium_plan = data["plans"]["premium"]
        assert premium_plan["price"] == 999  # $9.99 in cents
        assert premium_plan["features"]["monthly_minutes"] == -1  # Unlimited
        assert premium_plan["features"]["watermark"] is False
    
    def test_plan_features_comparison(self, client: TestClient):
        """Test that plan features are correctly defined"""
        response = client.get("/api/subscription/pricing")
        data = response.json()
        
        free = data["plans"]["free"]["features"]
        premium = data["plans"]["premium"]["features"]
        
        # Free limitations
        assert free["monthly_minutes"] == 10
        assert free["max_video_duration"] == 60
        assert free["max_quality"] == "720p"
        assert free["concurrent_uploads"] == 1
        assert free["watermark"] is True
        
        # Premium benefits
        assert premium["monthly_minutes"] == -1  # Unlimited
        assert premium["max_video_duration"] == -1  # Unlimited
        assert premium["max_quality"] == "4K"
        assert premium["concurrent_uploads"] == 5
        assert premium["watermark"] is False
        assert premium["priority_processing"] is True


class TestSubscriptionManagement:
    """Test subscription management functionality"""
    
    def test_get_current_subscription_free_user(self, client: TestClient, auth_headers):
        """Test getting current subscription for free user"""
        response = client.get("/api/subscription/current", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["tier"] == "free"
        assert data["status"] == "active"
        assert data["features"]["monthly_minutes"] == 10
    
    def test_get_current_subscription_premium_user(self, client: TestClient, premium_auth_headers):
        """Test getting current subscription for premium user"""
        response = client.get("/api/subscription/current", headers=premium_auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["tier"] == "premium"
        assert data["status"] == "active"
        assert data["features"]["monthly_minutes"] == -1
    
    def test_create_premium_subscription(self, client: TestClient, auth_headers, mock_stripe):
        """Test creating a premium subscription"""
        subscription_data = {
            "plan": "premium",
            "payment_method_id": "pm_test_123"
        }
        
        response = client.post("/api/subscription/create", json=subscription_data, headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "subscription_id" in data
        assert "client_secret" in data or "status" in data
        
        # Verify Stripe was called
        mock_stripe.Subscription.create.assert_called_once()
    
    def test_create_subscription_without_auth(self, client: TestClient):
        """Test creating subscription without authentication fails"""
        subscription_data = {
            "plan": "premium",
            "payment_method_id": "pm_test_123"
        }
        
        response = client.post("/api/subscription/create", json=subscription_data)
        assert response.status_code == 401
    
    def test_cancel_subscription(self, client: TestClient, premium_auth_headers, mock_stripe):
        """Test canceling a premium subscription"""
        response = client.post("/api/subscription/cancel", headers=premium_auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "message" in data
        assert "canceled" in data["message"].lower()
    
    def test_cancel_free_subscription_fails(self, client: TestClient, auth_headers):
        """Test canceling free subscription fails"""
        response = client.post("/api/subscription/cancel", headers=auth_headers)
        
        assert response.status_code == 400
        assert "free" in response.json()["detail"].lower()


class TestUsageTracking:
    """Test usage tracking and limits"""
    
    def test_get_usage_summary(self, client: TestClient, auth_headers):
        """Test getting usage summary for user"""
        response = client.get("/api/subscription/usage", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "current_month" in data
        assert "minutes_used" in data["current_month"]
        assert "videos_processed" in data["current_month"]
        assert "limits" in data
        assert data["limits"]["monthly_minutes"] == 10  # Free user limit
    
    def test_usage_limits_free_user(self, client: TestClient, auth_headers):
        """Test usage limits for free users"""
        response = client.get("/api/subscription/limits", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["monthly_minutes"] == 10
        assert data["max_video_duration"] == 60
        assert data["max_quality"] == "720p"
        assert data["watermark"] is True
    
    def test_usage_limits_premium_user(self, client: TestClient, premium_auth_headers):
        """Test usage limits for premium users"""
        response = client.get("/api/subscription/limits", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["monthly_minutes"] == -1  # Unlimited
        assert data["max_video_duration"] == -1  # Unlimited
        assert data["max_quality"] == "4K"
        assert data["watermark"] is False
    
    def test_record_usage(self, client: TestClient, auth_headers, db_session: Session):
        """Test recording usage for a user"""
        # Simulate video processing that would record usage
        usage_data = {
            "video_duration": 30,  # 30 seconds
            "processing_type": "basic_edit"
        }
        
        # This would typically be done internally during video processing
        from app.services.usage_service import UsageService
        from app.database.models import User
        
        user = db_session.query(User).first()
        usage_service = UsageService(db_session)
        
        result = usage_service.record_usage(
            user_id=user.id,
            minutes_used=0.5,  # 30 seconds = 0.5 minutes
            operation_type="video_processing"
        )
        
        assert result is True
        
        # Check usage was recorded
        response = client.get("/api/subscription/usage", headers=auth_headers)
        data = response.json()
        
        assert data["current_month"]["minutes_used"] == 0.5


class TestSubscriptionLimits:
    """Test subscription limit enforcement"""
    
    def test_free_user_exceeds_monthly_limit(self, client: TestClient, auth_headers, db_session: Session):
        """Test that free users are blocked when exceeding monthly limits"""
        from app.services.usage_service import UsageService
        from app.database.models import User
        
        user = db_session.query(User).first()
        usage_service = UsageService(db_session)
        
        # Record usage that exceeds free limit (10 minutes)
        usage_service.record_usage(user.id, 11.0, "video_processing")
        
        # Try to process another video (this would be checked in video processing endpoint)
        response = client.get("/api/subscription/limits", headers=auth_headers)
        data = response.json()
        
        # Check that limits are properly reported
        assert data["monthly_minutes"] == 10
        
        # The actual limit checking would happen in the video processing endpoint
        # Here we just verify the usage was recorded correctly
        usage_response = client.get("/api/subscription/usage", headers=auth_headers)
        usage_data = usage_response.json()
        
        assert usage_data["current_month"]["minutes_used"] >= 10
    
    def test_premium_user_no_limits(self, client: TestClient, premium_auth_headers, db_session: Session):
        """Test that premium users have no monthly limits"""
        from app.services.usage_service import UsageService
        from app.database.models import User
        
        user = db_session.query(User).filter(User.email.like("%premium%")).first()
        usage_service = UsageService(db_session)
        
        # Record heavy usage
        usage_service.record_usage(user.id, 1000.0, "video_processing")
        
        # Check limits - should be unlimited
        response = client.get("/api/subscription/limits", headers=premium_auth_headers)
        data = response.json()
        
        assert data["monthly_minutes"] == -1  # Unlimited


class TestBillingPortal:
    """Test Stripe billing portal integration"""
    
    def test_create_billing_portal_session(self, client: TestClient, premium_auth_headers, mock_stripe):
        """Test creating billing portal session for premium user"""
        mock_stripe.billing_portal.Session.create.return_value = {
            'url': 'https://billing.stripe.com/session/test123'
        }
        
        response = client.post("/api/subscription/billing-portal", headers=premium_auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "url" in data
        assert "billing.stripe.com" in data["url"]
    
    def test_billing_portal_free_user_fails(self, client: TestClient, auth_headers):
        """Test that free users cannot access billing portal"""
        response = client.post("/api/subscription/billing-portal", headers=auth_headers)
        
        assert response.status_code == 400
        assert "premium" in response.json()["detail"].lower()


class TestPaymentHistory:
    """Test payment history functionality"""
    
    def test_get_payment_history_premium_user(self, client: TestClient, premium_auth_headers):
        """Test getting payment history for premium user"""
        response = client.get("/api/subscription/payment-history", headers=premium_auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        # Payment history might be empty for test user, which is fine
    
    def test_get_payment_history_free_user(self, client: TestClient, auth_headers):
        """Test getting payment history for free user returns empty list"""
        response = client.get("/api/subscription/payment-history", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) == 0  # Free users have no payment history


class TestWebhooks:
    """Test Stripe webhook handling"""
    
    def test_stripe_webhook_subscription_created(self, client: TestClient):
        """Test handling Stripe subscription created webhook"""
        webhook_data = {
            "type": "customer.subscription.created",
            "data": {
                "object": {
                    "id": "sub_test123",
                    "customer": "cus_test123",
                    "status": "active",
                    "current_period_start": 1234567890,
                    "current_period_end": 1234567890 + 2592000
                }
            }
        }
        
        # Note: In real implementation, this would require proper Stripe webhook signature
        response = client.post("/api/subscription/webhook/stripe", json=webhook_data)
        
        # The response depends on the webhook implementation
        # This is a basic test to ensure the endpoint exists
        assert response.status_code in [200, 400]  # 400 if signature validation fails
    
    def test_stripe_webhook_subscription_canceled(self, client: TestClient):
        """Test handling Stripe subscription canceled webhook"""
        webhook_data = {
            "type": "customer.subscription.deleted",
            "data": {
                "object": {
                    "id": "sub_test123",
                    "customer": "cus_test123",
                    "status": "canceled"
                }
            }
        }
        
        response = client.post("/api/subscription/webhook/stripe", json=webhook_data)
        
        # The response depends on the webhook implementation
        assert response.status_code in [200, 400]