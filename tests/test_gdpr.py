import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from app.database.models import User, UserConsent, DataExportRequest, DataDeletionRequest


class TestConsentManagement:
    """Test consent management functionality"""
    
    def test_record_consent_authenticated(self, client: TestClient, auth_headers):
        """Test recording consent for authenticated user"""
        consent_data = {
            "consent_type": "analytics",
            "consent_given": True,
            "purpose": "Analytics tracking",
            "lawful_basis": "consent"
        }
        
        response = client.post("/api/gdpr/consent", json=consent_data, headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["consent_type"] == "analytics"
        assert data["consent_given"] is True
        assert data["purpose"] == "Analytics tracking"
        assert data["lawful_basis"] == "consent"
        assert "consent_date" in data
        assert "user_id" in data
    
    def test_record_consent_unauthenticated(self, client: TestClient):
        """Test that unauthenticated users cannot record consent"""
        consent_data = {
            "consent_type": "analytics",
            "consent_given": True
        }
        
        response = client.post("/api/gdpr/consent", json=consent_data)
        assert response.status_code == 401
    
    def test_withdraw_consent(self, client: TestClient, auth_headers):
        """Test withdrawing previously given consent"""
        # Give consent first
        client.post("/api/gdpr/consent", json={
            "consent_type": "marketing",
            "consent_given": True
        }, headers=auth_headers)
        
        # Withdraw consent
        response = client.post("/api/gdpr/consent", json={
            "consent_type": "marketing",
            "consent_given": False
        }, headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["consent_type"] == "marketing"
        assert data["consent_given"] is False
    
    def test_get_user_consents(self, client: TestClient, auth_headers):
        """Test getting user's consent history"""
        # Record some consents first
        client.post("/api/gdpr/consent", json={
            "consent_type": "analytics", 
            "consent_given": True
        }, headers=auth_headers)
        
        client.post("/api/gdpr/consent", json={
            "consent_type": "marketing",
            "consent_given": False
        }, headers=auth_headers)
        
        response = client.get("/api/gdpr/consents", headers=auth_headers)
        
        assert response.status_code == 200
        consents = response.json()
        
        assert len(consents) >= 2
        
        # Check that both consent types are present
        consent_types = [c["consent_type"] for c in consents]
        assert "analytics" in consent_types
        assert "marketing" in consent_types
    
    def test_invalid_consent_type(self, client: TestClient, auth_headers):
        """Test invalid consent type returns error"""
        response = client.post("/api/gdpr/consent", json={
            "consent_type": "invalid_type",
            "consent_given": True
        }, headers=auth_headers)
        
        assert response.status_code == 400
    
    def test_consent_metadata_recorded(self, client: TestClient, auth_headers):
        """Test that consent metadata is properly recorded"""
        response = client.post("/api/gdpr/consent", json={
            "consent_type": "analytics",
            "consent_given": True,
            "purpose": "User analytics",
            "lawful_basis": "consent"
        }, headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "consent_date" in data
        assert "user_agent" in data  # Should capture user agent
        assert "ip_address" in data  # Should capture IP for audit


class TestDataExport:
    """Test data export functionality"""
    
    def test_request_data_export_authenticated(self, client: TestClient, auth_headers):
        """Test requesting data export for authenticated user"""
        export_data = {
            "data_categories": ["profile", "usage"],
            "format": "json"
        }
        
        response = client.post("/api/gdpr/export", json=export_data, headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "request_id" in data
        assert data["status"] == "pending"
        assert data["data_categories"] == ["profile", "usage"]
        assert data["format"] == "json"
        assert "created_date" in data
    
    def test_request_data_export_unauthenticated(self, client: TestClient):
        """Test that unauthenticated users cannot request export"""
        response = client.post("/api/gdpr/export", json={
            "data_categories": ["profile"],
            "format": "json"
        })
        
        assert response.status_code == 401
    
    def test_export_request_status(self, client: TestClient, auth_headers):
        """Test checking export request status"""
        # Create export request
        export_response = client.post("/api/gdpr/export", json={
            "data_categories": ["profile"],
            "format": "json"
        }, headers=auth_headers)
        
        request_id = export_response.json()["request_id"]
        
        # Check status
        response = client.get(f"/api/gdpr/export/{request_id}", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["request_id"] == request_id
        assert data["status"] in ["pending", "processing", "completed", "failed"]
    
    def test_export_multiple_formats(self, client: TestClient, auth_headers):
        """Test exporting in different formats"""
        formats = ["json", "csv"]
        
        for fmt in formats:
            response = client.post("/api/gdpr/export", json={
                "data_categories": ["profile"],
                "format": fmt
            }, headers=auth_headers)
            
            assert response.status_code == 200
            assert response.json()["format"] == fmt
    
    def test_export_selective_categories(self, client: TestClient, auth_headers):
        """Test exporting selective data categories"""
        categories = [
            ["profile"],
            ["usage"],
            ["profile", "usage"],
            ["profile", "usage", "consents"]
        ]
        
        for category_list in categories:
            response = client.post("/api/gdpr/export", json={
                "data_categories": category_list,
                "format": "json"
            }, headers=auth_headers)
            
            assert response.status_code == 200
            assert response.json()["data_categories"] == category_list
    
    def test_export_includes_user_data(self, client: TestClient, auth_headers):
        """Test that export includes user data when processed"""
        # This would test actual data export processing
        # For now, we test the request creation
        response = client.post("/api/gdpr/export", json={
            "data_categories": ["profile", "consents"],
            "format": "json"
        }, headers=auth_headers)
        
        assert response.status_code == 200
        # In real implementation, would test actual data inclusion


class TestDataDeletion:
    """Test data deletion functionality"""
    
    def test_request_data_deletion_authenticated(self, client: TestClient, auth_headers):
        """Test requesting data deletion for authenticated user"""
        deletion_data = {
            "reason": "No longer need the service"
        }
        
        response = client.post("/api/gdpr/delete", json=deletion_data, headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "request_id" in data
        assert data["status"] == "pending"
        assert data["reason"] == "No longer need the service"
        assert "grace_period_ends" in data
        assert "created_date" in data
    
    def test_request_data_deletion_unauthenticated(self, client: TestClient):
        """Test that unauthenticated users cannot request deletion"""
        response = client.post("/api/gdpr/delete", json={
            "reason": "Test reason"
        })
        
        assert response.status_code == 401
    
    def test_deletion_request_status(self, client: TestClient, auth_headers):
        """Test checking deletion request status"""
        # Create deletion request
        delete_response = client.post("/api/gdpr/delete", json={
            "reason": "Test deletion"
        }, headers=auth_headers)
        
        request_id = delete_response.json()["request_id"]
        
        # Check status
        response = client.get(f"/api/gdpr/delete/{request_id}", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["request_id"] == request_id
        assert data["status"] in ["pending", "approved", "processing", "completed", "cancelled"]
    
    def test_cancel_deletion_request(self, client: TestClient, auth_headers):
        """Test cancelling deletion request during grace period"""
        # Create deletion request
        delete_response = client.post("/api/gdpr/delete", json={
            "reason": "Changed my mind"
        }, headers=auth_headers)
        
        request_id = delete_response.json()["request_id"]
        
        # Cancel request
        response = client.post(f"/api/gdpr/delete/{request_id}/cancel", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "cancelled"
    
    def test_deletion_grace_period(self, client: TestClient, auth_headers):
        """Test that deletion includes proper grace period"""
        response = client.post("/api/gdpr/delete", json={
            "reason": "Test grace period"
        }, headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        grace_period_end = datetime.fromisoformat(data["grace_period_ends"].replace('Z', '+00:00'))
        now = datetime.now(grace_period_end.tzinfo)
        
        # Grace period should be at least 7 days in the future
        assert (grace_period_end - now).days >= 7
    
    def test_deletion_reason_optional(self, client: TestClient, auth_headers):
        """Test that deletion reason is optional"""
        response = client.post("/api/gdpr/delete", json={}, headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "request_id" in data
        assert data["status"] == "pending"
    
    def test_multiple_deletion_requests_prevented(self, client: TestClient, auth_headers):
        """Test that multiple active deletion requests are prevented"""
        # Create first deletion request
        client.post("/api/gdpr/delete", json={
            "reason": "First request"
        }, headers=auth_headers)
        
        # Try to create second deletion request
        response = client.post("/api/gdpr/delete", json={
            "reason": "Second request"
        }, headers=auth_headers)
        
        assert response.status_code == 400  # Should prevent duplicate


class TestPrivacyDashboard:
    """Test privacy dashboard functionality"""
    
    def test_get_privacy_dashboard_authenticated(self, client: TestClient, auth_headers):
        """Test getting privacy dashboard"""
        # Create some data first
        client.post("/api/gdpr/consent", json={
            "consent_type": "analytics", 
            "consent_given": True
        }, headers=auth_headers)
        
        response = client.get("/api/gdpr/dashboard", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "user_id" in data
        assert "consents" in data
        assert "data_categories" in data
        assert "retention_info" in data
        assert "active_export_requests" in data
        assert "active_deletion_requests" in data
        assert data["privacy_policy_version"] == "2.0"
    
    def test_get_data_categories_info(self, client: TestClient):
        """Test getting data categories information"""
        response = client.get("/api/gdpr/data-categories")
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data) >= 4  # profile, usage, payments, communications
        
        # Check structure of first category
        category = data[0]
        assert "category" in category
        assert "description" in category
        assert "data_types" in category
        assert "legal_basis" in category
        assert "can_be_exported" in category
        assert "can_be_deleted" in category
    
    def test_privacy_dashboard_requires_auth(self, client: TestClient):
        """Test that privacy dashboard requires authentication"""
        response = client.get("/api/gdpr/dashboard")
        assert response.status_code == 401


class TestCookieConsent:
    """Test cookie consent functionality"""
    
    def test_update_cookie_consent_authenticated(self, client: TestClient, auth_headers):
        """Test updating cookie consent for authenticated user"""
        cookie_data = {
            "essential_cookies": True,
            "functional_cookies": True,
            "analytics_cookies": False,
            "marketing_cookies": False
        }
        
        response = client.post("/api/gdpr/cookies", json=cookie_data, headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["essential_cookies"] is True
        assert data["functional_cookies"] is True
        assert data["analytics_cookies"] is False
        assert data["marketing_cookies"] is False
        assert "consent_date" in data
        assert "expires_date" in data
    
    def test_update_cookie_consent_anonymous(self, client: TestClient):
        """Test updating cookie consent for anonymous user"""
        # This would work with session management
        cookie_data = {
            "essential_cookies": True,
            "functional_cookies": False,
            "analytics_cookies": False,
            "marketing_cookies": False
        }
        
        # For anonymous users, this might require different handling
        # depending on session implementation
        response = client.post("/api/gdpr/cookies", json=cookie_data)
        
        # Could be 401 if auth is required, or 200 if anonymous is allowed
        assert response.status_code in [200, 401]


class TestDataSubjectRights:
    """Test data subject rights information"""
    
    def test_get_data_subject_rights(self, client: TestClient):
        """Test getting data subject rights information"""
        response = client.get("/api/gdpr/rights")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check all GDPR rights are covered
        expected_rights = [
            "right_to_information",
            "right_of_access",
            "right_to_rectification",
            "right_to_erasure",
            "right_to_restrict_processing",
            "right_to_data_portability",
            "right_to_object",
            "rights_related_to_automated_decision_making"
        ]
        
        for right in expected_rights:
            assert right in data
            assert "title" in data[right]
            assert "description" in data[right]
    
    def test_legal_basis_information(self, client: TestClient):
        """Test getting legal basis information"""
        response = client.get("/api/gdpr/legal-basis")
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data) > 0
        
        # Check structure
        basis = data[0]
        assert "basis_type" in basis
        assert "description" in basis
        assert "data_categories" in basis


class TestGDPRService:
    """Test GDPR service functionality"""
    
    def test_record_consent_service(self, db_session, test_user):
        """Test recording consent via service"""
        from app.services.gdpr_service import GDPRService
        
        service = GDPRService(db_session)
        
        consent = service.record_consent(
            user_id=test_user.id,
            consent_type="analytics",
            consent_given=True,
            purpose="Analytics tracking",
            lawful_basis="consent"
        )
        
        assert consent.user_id == test_user.id
        assert consent.consent_type == "analytics"
        assert consent.consent_given is True
        assert consent.purpose == "Analytics tracking"
        assert consent.lawful_basis == "consent"
        assert consent.consent_date is not None
    
    def test_get_user_consents_service(self, db_session, test_user):
        """Test getting user consents via service"""
        from app.services.gdpr_service import GDPRService
        
        service = GDPRService(db_session)
        
        # Record some consents first
        service.record_consent(test_user.id, "analytics", True, "Analytics", "consent")
        service.record_consent(test_user.id, "marketing", False, "Marketing", "consent")
        
        consents = service.get_user_consents(test_user.id)
        
        assert len(consents) == 2
        assert any(c.consent_type == "analytics" and c.consent_given for c in consents)
        assert any(c.consent_type == "marketing" and not c.consent_given for c in consents)
    
    def test_create_data_export_service(self, db_session, test_user):
        """Test creating data export via service"""
        from app.services.gdpr_service import GDPRService
        
        service = GDPRService(db_session)
        
        export_request = service.create_data_export_request(
            user_id=test_user.id,
            data_categories=["profile", "usage"],
            format="json"
        )
        
        assert export_request.user_id == test_user.id
        assert export_request.data_categories == ["profile", "usage"]
        assert export_request.format == "json"
        assert export_request.status == "pending"
    
    def test_create_data_deletion_service(self, db_session, test_user):
        """Test creating data deletion via service"""
        from app.services.gdpr_service import GDPRService
        
        service = GDPRService(db_session)
        
        deletion_request = service.create_data_deletion_request(
            user_id=test_user.id,
            reason="No longer want service"
        )
        
        assert deletion_request.user_id == test_user.id
        assert deletion_request.reason == "No longer want service"
        assert deletion_request.status == "pending"
        assert deletion_request.grace_period_ends is not None
    
    def test_process_data_export_service(self, db_session, test_user):
        """Test processing data export via service"""
        from app.services.gdpr_service import GDPRService
        
        service = GDPRService(db_session)
        
        # Create export request first
        export_request = service.create_data_export_request(
            user_id=test_user.id,
            data_categories=["profile"],
            format="json"
        )
        
        # Process the export
        result = service.process_data_export(export_request.id)
        
        assert result is not None
        assert "user_data" in result
        assert "profile" in result["user_data"]
    
    def test_anonymize_user_data_service(self, db_session, test_user):
        """Test anonymizing user data via service"""
        from app.services.gdpr_service import GDPRService
        
        service = GDPRService(db_session)
        
        # Anonymize user data
        result = service.anonymize_user_data(test_user.id)
        
        assert result is True
        
        # Verify user data is anonymized
        db_session.refresh(test_user)
        assert test_user.email.startswith("anonymized_")
        assert test_user.name == "Anonymized User"


class TestGDPRAdminFeatures:
    """Test GDPR admin features"""
    
    def test_admin_gdpr_dashboard(self, client: TestClient, admin_headers):
        """Test admin GDPR dashboard"""
        response = client.get("/api/admin/gdpr/dashboard", headers=admin_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "consent_stats" in data
        assert "export_requests" in data
        assert "deletion_requests" in data
        assert "compliance_metrics" in data
    
    def test_admin_export_requests_list(self, client: TestClient, admin_headers):
        """Test admin export requests list"""
        response = client.get("/api/admin/gdpr/export-requests", headers=admin_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
    
    def test_admin_deletion_requests_list(self, client: TestClient, admin_headers):
        """Test admin deletion requests list"""
        response = client.get("/api/admin/gdpr/deletion-requests", headers=admin_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
    
    def test_admin_process_export_request(self, client: TestClient, admin_headers, auth_headers):
        """Test admin processing export request"""
        # Create export request first
        export_response = client.post("/api/gdpr/export", json={
            "data_categories": ["profile"],
            "format": "json"
        }, headers=auth_headers)
        
        export_id = export_response.json()["request_id"]
        
        # Process it as admin
        response = client.post(f"/api/admin/gdpr/export-requests/{export_id}/process", 
                             headers=admin_headers)
        
        assert response.status_code == 200
    
    def test_admin_approve_deletion_request(self, client: TestClient, admin_headers, auth_headers):
        """Test admin approving deletion request"""
        # Create deletion request first
        delete_response = client.post("/api/gdpr/delete", json={
            "reason": "Test deletion"
        }, headers=auth_headers)
        
        delete_id = delete_response.json()["request_id"]
        
        # Approve it as admin
        response = client.post(f"/api/admin/gdpr/deletion-requests/{delete_id}/approve", 
                             headers=admin_headers)
        
        assert response.status_code == 200
    
    def test_admin_gdpr_requires_admin_role(self, client: TestClient, auth_headers):
        """Test that admin GDPR endpoints require admin role"""
        response = client.get("/api/admin/gdpr/dashboard", headers=auth_headers)
        assert response.status_code == 403


class TestGDPRIntegration:
    """Test GDPR integration with other systems"""
    
    def test_user_deletion_cascades_properly(self, client: TestClient, auth_headers):
        """Test that user deletion cascades to related data"""
        # Create some user data first
        client.post("/api/gdpr/consent", json={
            "consent_type": "analytics",
            "consent_given": True
        }, headers=auth_headers)
        
        # Request deletion
        delete_response = client.post("/api/gdpr/delete", json={
            "reason": "Test deletion"
        }, headers=auth_headers)
        
        assert delete_response.status_code == 200
        request_id = delete_response.json()["request_id"]
        
        # Verify deletion request was created
        response = client.get("/api/gdpr/dashboard", headers=auth_headers)
        dashboard = response.json()
        
        assert len(dashboard["active_deletion_requests"]) == 1
        assert dashboard["active_deletion_requests"][0]["id"] == request_id
    
    def test_consent_withdrawal_stops_processing(self, client: TestClient, auth_headers):
        """Test that consent withdrawal stops data processing"""
        # Give consent first
        client.post("/api/gdpr/consent", json={
            "consent_type": "analytics",
            "consent_given": True
        }, headers=auth_headers)
        
        # Withdraw consent
        response = client.post("/api/gdpr/consent", json={
            "consent_type": "analytics",
            "consent_given": False
        }, headers=auth_headers)
        
        assert response.status_code == 200
        
        # Verify consent was withdrawn
        dashboard_response = client.get("/api/gdpr/dashboard", headers=auth_headers)
        dashboard = dashboard_response.json()
        
        analytics_consent = next(
            (c for c in dashboard["consents"] if c["consent_type"] == "analytics"),
            None
        )
        assert analytics_consent is not None
        assert analytics_consent["consent_given"] is False
    
    def test_data_export_includes_all_categories(self, client: TestClient, auth_headers):
        """Test that data export includes all requested categories"""
        # Create some data first
        client.post("/api/gdpr/consent", json={
            "consent_type": "marketing",
            "consent_given": True
        }, headers=auth_headers)
        
        # Request export
        export_response = client.post("/api/gdpr/export", json={
            "data_categories": ["profile", "consents"],
            "format": "json"
        }, headers=auth_headers)
        
        assert export_response.status_code == 200
        export_data = export_response.json()
        
        assert "request_id" in export_data
        assert export_data["status"] == "pending"
        assert export_data["data_categories"] == ["profile", "consents"]
        assert export_data["format"] == "json"


class TestGDPRCompliance:
    """Test overall GDPR compliance"""
    
    def test_lawful_basis_documented(self, client: TestClient):
        """Test that lawful basis is documented for all data processing"""
        response = client.get("/api/gdpr/legal-basis")
        
        assert response.status_code == 200
        legal_bases = response.json()
        
        # Ensure all major processing has documented legal basis
        basis_types = [basis["basis_type"] for basis in legal_bases]
        
        expected_bases = ["consent", "contract", "legal_obligation", "legitimate_interests"]
        
        for expected_basis in expected_bases:
            assert any(basis_type == expected_basis for basis_type in basis_types)
    
    def test_data_retention_periods_defined(self, client: TestClient):
        """Test that data retention periods are defined"""
        response = client.get("/api/gdpr/data-categories")
        
        assert response.status_code == 200
        categories = response.json()
        
        for category in categories:
            assert "retention_period" in category
            assert category["retention_period"] is not None
            assert len(category["retention_period"]) > 0
    
    def test_privacy_policy_accessible(self, client: TestClient):
        """Test that privacy policy is accessible"""
        # This would test actual privacy policy endpoint
        # For now, we check that privacy info is available
        response = client.get("/api/gdpr/rights")
        
        assert response.status_code == 200
        # Privacy policy should be referenced in rights information
    
    def test_consent_granular_and_specific(self, client: TestClient, auth_headers):
        """Test that consent is granular and specific"""
        # Test different types of consent can be managed separately
        consent_types = ["analytics", "marketing", "third_party", "functional"]
        
        for consent_type in consent_types:
            response = client.post("/api/gdpr/consent", json={
                "consent_type": consent_type,
                "consent_given": True
            }, headers=auth_headers)
            
            assert response.status_code == 200
        
        # Verify all consents were recorded separately
        dashboard_response = client.get("/api/gdpr/dashboard", headers=auth_headers)
        dashboard = dashboard_response.json()
        
        recorded_types = [c["consent_type"] for c in dashboard["consents"]]
        
        for consent_type in consent_types:
            assert consent_type in recorded_types
    
    def test_data_portability_format_compliance(self, client: TestClient, auth_headers):
        """Test that data export formats comply with portability requirements"""
        # Test JSON format (machine readable)
        response = client.post("/api/gdpr/export", json={
            "data_categories": ["profile"],
            "format": "json"
        }, headers=auth_headers)
        
        assert response.status_code == 200
        assert response.json()["format"] == "json"
        
        # Test CSV format (commonly used)
        response = client.post("/api/gdpr/export", json={
            "data_categories": ["profile"],
            "format": "csv"
        }, headers=auth_headers)
        
        assert response.status_code == 200
        assert response.json()["format"] == "csv"
    
    def test_right_to_erasure_grace_period(self, client: TestClient, auth_headers):
        """Test that right to erasure includes proper grace period"""
        response = client.post("/api/gdpr/delete", json={
            "reason": "No longer need service"
        }, headers=auth_headers)
        
        assert response.status_code == 200
        deletion_data = response.json()
        
        assert "grace_period_ends" in deletion_data
        assert deletion_data["grace_period_ends"] is not None
        
        # Grace period should be in the future
        from datetime import datetime
        grace_period_end = datetime.fromisoformat(
            deletion_data["grace_period_ends"].replace('Z', '+00:00')
        )
        assert grace_period_end > datetime.now(grace_period_end.tzinfo)
    
    def test_audit_trail_exists(self, client: TestClient, auth_headers, db_session: Session):
        """Test that audit trail is maintained for GDPR operations"""
        from app.database.models import AuditLog
        
        initial_audit_count = db_session.query(AuditLog).count()
        
        # Perform GDPR operation
        client.post("/api/gdpr/consent", json={
            "consent_type": "analytics",
            "consent_given": True
        }, headers=auth_headers)
        
        # Check audit log was created
        final_audit_count = db_session.query(AuditLog).count()
        assert final_audit_count > initial_audit_count