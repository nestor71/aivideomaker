"""
Admin dashboard and management tests
"""
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database.models import User, UserRole, Subscription, UsageRecord, AuditLog


class TestAdminAuthentication:
    """Test admin authentication and authorization"""
    
    def test_admin_access_granted(self, client: TestClient, admin_auth_headers):
        """Test that admin users can access admin routes"""
        response = client.get("/api/admin/dashboard", headers=admin_auth_headers)
        assert response.status_code == 200
    
    def test_regular_user_admin_access_denied(self, client: TestClient, auth_headers):
        """Test that regular users cannot access admin routes"""
        response = client.get("/api/admin/dashboard", headers=auth_headers)
        assert response.status_code == 403
        assert "admin" in response.json()["detail"].lower()
    
    def test_unauthenticated_admin_access_denied(self, client: TestClient):
        """Test that unauthenticated requests to admin routes are denied"""
        response = client.get("/api/admin/dashboard")
        assert response.status_code == 401


class TestUserManagement:
    """Test admin user management functionality"""
    
    def test_get_all_users(self, client: TestClient, admin_auth_headers):
        """Test getting list of all users"""
        response = client.get("/api/admin/users", headers=admin_auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "users" in data
        assert "total" in data
        assert "page" in data
        assert isinstance(data["users"], list)
    
    def test_get_user_details(self, client: TestClient, admin_auth_headers, auth_headers, db_session: Session):
        """Test getting detailed user information"""
        # Get the regular user ID
        user = db_session.query(User).filter(User.role == UserRole.USER).first()
        
        response = client.get(f"/api/admin/users/{user.id}", headers=admin_auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["id"] == user.id
        assert data["email"] == user.email
        assert "subscription" in data
        assert "usage_stats" in data
    
    def test_update_user_status(self, client: TestClient, admin_auth_headers, db_session: Session):
        """Test updating user active status"""
        user = db_session.query(User).filter(User.role == UserRole.USER).first()
        
        update_data = {
            "is_active": False
        }
        
        response = client.put(f"/api/admin/users/{user.id}", json=update_data, headers=admin_auth_headers)
        
        assert response.status_code == 200
        
        # Verify update in database
        db_session.refresh(user)
        assert user.is_active is False
    
    def test_delete_user(self, client: TestClient, admin_auth_headers, db_session: Session):
        """Test deleting a user account"""
        # Create a test user to delete
        from app.services.auth_service import AuthService
        
        auth_service = AuthService(db_session)
        user = auth_service.create_user(
            email="delete_me@example.com",
            password="TestPass123",
            full_name="Delete Me"
        )
        
        response = client.delete(f"/api/admin/users/{user.id}", headers=admin_auth_headers)
        
        assert response.status_code == 200
        
        # Verify user is deleted or deactivated
        deleted_user = db_session.query(User).filter(User.id == user.id).first()
        assert deleted_user is None or deleted_user.is_active is False
    
    def test_search_users(self, client: TestClient, admin_auth_headers):
        """Test searching for users"""
        search_params = {
            "q": "test",
            "tier": "free"
        }
        
        response = client.get("/api/admin/users/search", params=search_params, headers=admin_auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "users" in data
        assert "total" in data


class TestAnalyticsDashboard:
    """Test admin analytics dashboard"""
    
    def test_get_dashboard_stats(self, client: TestClient, admin_auth_headers):
        """Test getting main dashboard statistics"""
        response = client.get("/api/admin/dashboard", headers=admin_auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        # Check for key metrics
        assert "users" in data
        assert "subscriptions" in data
        assert "revenue" in data
        assert "usage" in data
        
        # User metrics
        assert "total_users" in data["users"]
        assert "new_users_this_month" in data["users"]
        assert "active_users" in data["users"]
        
        # Subscription metrics
        assert "total_premium_users" in data["subscriptions"]
        assert "conversion_rate" in data["subscriptions"]
        assert "churn_rate" in data["subscriptions"]
        
        # Revenue metrics
        assert "monthly_revenue" in data["revenue"]
        assert "total_revenue" in data["revenue"]
    
    def test_get_usage_analytics(self, client: TestClient, admin_auth_headers):
        """Test getting usage analytics"""
        response = client.get("/api/admin/analytics/usage", headers=admin_auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "total_videos_processed" in data
        assert "total_minutes_processed" in data
        assert "processing_by_day" in data
        assert "popular_features" in data
    
    def test_get_revenue_analytics(self, client: TestClient, admin_auth_headers):
        """Test getting revenue analytics"""
        response = client.get("/api/admin/analytics/revenue", headers=admin_auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "monthly_recurring_revenue" in data
        assert "revenue_by_month" in data
        assert "average_revenue_per_user" in data
    
    def test_get_user_growth_analytics(self, client: TestClient, admin_auth_headers):
        """Test getting user growth analytics"""
        response = client.get("/api/admin/analytics/users", headers=admin_auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "registrations_by_day" in data
        assert "retention_rates" in data
        assert "user_lifecycle" in data


class TestSystemHealth:
    """Test system health monitoring"""
    
    def test_get_system_health(self, client: TestClient, admin_auth_headers):
        """Test getting system health status"""
        response = client.get("/api/admin/system/health", headers=admin_auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "database" in data
        assert "redis" in data
        assert "storage" in data
        assert "processing_queue" in data
        
        # Check health statuses
        for service in ["database", "redis", "storage", "processing_queue"]:
            assert "status" in data[service]
            assert data[service]["status"] in ["healthy", "warning", "critical"]
    
    def test_get_system_metrics(self, client: TestClient, admin_auth_headers):
        """Test getting system performance metrics"""
        response = client.get("/api/admin/system/metrics", headers=admin_auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "cpu_usage" in data
        assert "memory_usage" in data
        assert "disk_usage" in data
        assert "active_tasks" in data
    
    def test_get_error_logs(self, client: TestClient, admin_auth_headers):
        """Test getting system error logs"""
        response = client.get("/api/admin/system/logs", headers=admin_auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "logs" in data
        assert "total" in data
        assert isinstance(data["logs"], list)


class TestSubscriptionManagement:
    """Test admin subscription management"""
    
    def test_get_subscription_overview(self, client: TestClient, admin_auth_headers):
        """Test getting subscription overview"""
        response = client.get("/api/admin/subscriptions", headers=admin_auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "subscriptions" in data
        assert "summary" in data
        assert "total" in data
    
    def test_modify_user_subscription(self, client: TestClient, admin_auth_headers, db_session: Session):
        """Test admin modifying user subscription"""
        user = db_session.query(User).filter(User.role == UserRole.USER).first()
        
        subscription_data = {
            "tier": "premium",
            "status": "active",
            "admin_note": "Manual upgrade for testing"
        }
        
        response = client.put(
            f"/api/admin/users/{user.id}/subscription", 
            json=subscription_data, 
            headers=admin_auth_headers
        )
        
        assert response.status_code == 200
        
        # Verify subscription was updated
        updated_user = db_session.query(User).filter(User.id == user.id).first()
        # Note: The exact verification depends on your subscription model implementation
    
    def test_refund_subscription(self, client: TestClient, admin_auth_headers, mock_stripe):
        """Test admin processing refund"""
        refund_data = {
            "subscription_id": "sub_test123",
            "amount": 999,  # $9.99
            "reason": "requested_by_customer"
        }
        
        mock_stripe.Refund.create.return_value = {
            'id': 'ref_test123',
            'status': 'succeeded'
        }
        
        response = client.post("/api/admin/refunds", json=refund_data, headers=admin_auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "refund_id" in data


class TestAuditLogs:
    """Test audit logging functionality"""
    
    def test_get_audit_logs(self, client: TestClient, admin_auth_headers):
        """Test getting audit logs"""
        response = client.get("/api/admin/audit-logs", headers=admin_auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "logs" in data
        assert "total" in data
        assert isinstance(data["logs"], list)
    
    def test_audit_log_filtering(self, client: TestClient, admin_auth_headers):
        """Test filtering audit logs"""
        filters = {
            "action": "user_login",
            "start_date": "2025-01-01",
            "end_date": "2025-12-31"
        }
        
        response = client.get("/api/admin/audit-logs", params=filters, headers=admin_auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        # Should return filtered results
        assert "logs" in data
    
    def test_audit_log_creation(self, client: TestClient, admin_auth_headers, db_session: Session):
        """Test that admin actions create audit logs"""
        initial_log_count = db_session.query(AuditLog).count()
        
        # Perform an admin action that should create an audit log
        user = db_session.query(User).filter(User.role == UserRole.USER).first()
        response = client.put(f"/api/admin/users/{user.id}", json={"is_active": False}, headers=admin_auth_headers)
        
        assert response.status_code == 200
        
        # Check that audit log was created
        final_log_count = db_session.query(AuditLog).count()
        assert final_log_count > initial_log_count


class TestBulkOperations:
    """Test bulk operations for admin management"""
    
    def test_bulk_user_actions(self, client: TestClient, admin_auth_headers, db_session: Session):
        """Test bulk user operations"""
        # Create multiple test users
        user_ids = []
        from app.services.auth_service import AuthService
        
        auth_service = AuthService(db_session)
        for i in range(3):
            user = auth_service.create_user(
                email=f"bulk_test_{i}@example.com",
                password="TestPass123",
                full_name=f"Bulk Test User {i}"
            )
            user_ids.append(user.id)
        
        # Test bulk deactivation
        bulk_data = {
            "user_ids": user_ids,
            "action": "deactivate"
        }
        
        response = client.post("/api/admin/users/bulk-action", json=bulk_data, headers=admin_auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["affected_count"] == 3
    
    def test_bulk_email_notification(self, client: TestClient, admin_auth_headers, mock_email_service):
        """Test sending bulk email notifications"""
        email_data = {
            "recipient_filter": {"tier": "free"},
            "subject": "Important Update",
            "template": "system_announcement",
            "variables": {
                "announcement": "System maintenance scheduled"
            }
        }
        
        response = client.post("/api/admin/notifications/bulk-email", json=email_data, headers=admin_auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "sent_count" in data


class TestDataExport:
    """Test data export functionality for admin"""
    
    def test_export_user_data(self, client: TestClient, admin_auth_headers):
        """Test exporting user data"""
        export_params = {
            "format": "csv",
            "include_usage": "true",
            "date_range": "30"
        }
        
        response = client.get("/api/admin/export/users", params=export_params, headers=admin_auth_headers)
        
        assert response.status_code == 200
        # Response should be a file download
        assert response.headers["content-type"] == "text/csv"
    
    def test_export_revenue_data(self, client: TestClient, admin_auth_headers):
        """Test exporting revenue data"""
        export_params = {
            "format": "json",
            "period": "monthly"
        }
        
        response = client.get("/api/admin/export/revenue", params=export_params, headers=admin_auth_headers)
        
        assert response.status_code == 200
        # Should return JSON data
        assert response.headers["content-type"] == "application/json"
    
    def test_export_usage_analytics(self, client: TestClient, admin_auth_headers):
        """Test exporting usage analytics"""
        response = client.get("/api/admin/export/usage", headers=admin_auth_headers)
        
        assert response.status_code == 200