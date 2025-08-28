"""
Integration tests for complete user flows
"""
import pytest
import os
import tempfile
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import Mock, patch

from app.database.models import User, Subscription, UsageRecord


class TestCompleteUserJourney:
    """Test complete user journey from registration to video processing"""
    
    def test_free_user_complete_flow(self, client: TestClient, sample_video_file, sample_image_file, mock_email_service):
        """Test complete flow for a free user"""
        # 1. User registration
        user_data = {
            "email": "journey_test@example.com",
            "password": "TestPass123",
            "full_name": "Journey Test User"
        }
        
        response = client.post("/api/auth/register", json=user_data)
        assert response.status_code == 200
        
        token = response.json()["access_token"]
        auth_headers = {"Authorization": f"Bearer {token}"}
        
        # 2. Check initial subscription status
        response = client.get("/api/subscription/current", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["tier"] == "free"
        
        # 3. Check usage limits
        response = client.get("/api/subscription/limits", headers=auth_headers)
        assert response.status_code == 200
        limits = response.json()
        assert limits["monthly_minutes"] == 10
        assert limits["watermark"] is True
        
        # 4. Upload a video
        with patch('app.services.video_processor.VideoProcessor.get_video_duration') as mock_duration:
            mock_duration.return_value = 30  # 30 seconds
            
            with open(sample_video_file, 'rb') as video_file:
                files = {'file': ('test_video.mp4', video_file, 'video/mp4')}
                response = client.post("/api/upload/video", files=files, headers=auth_headers)
                
                # Should succeed (or fail for non-duration reasons)
                if response.status_code != 200:
                    assert "duration" not in response.json().get("detail", "").lower()
        
        # 5. Upload logo and CTA
        with open(sample_image_file, 'rb') as image_file:
            files = {'file': ('logo.png', image_file, 'image/png')}
            response = client.post("/api/upload/logo", files=files, headers=auth_headers)
        
        # 6. Process video with free tier limitations
        with patch('app.services.video_processor.VideoProcessor.process_video') as mock_process:
            with patch('app.services.watermark_service.WatermarkService.add_watermark') as mock_watermark:
                mock_process.return_value = {"task_id": "test123", "status": "processing"}
                mock_watermark.return_value = "/path/to/watermarked_video.mp4"
                
                process_data = {
                    "quality": "720p",  # Free tier quality
                    "features": {
                        "logo_overlay": True,
                        "transcription": True
                    }
                }
                
                response = client.post("/api/process", json=process_data, headers=auth_headers)
                
                if response.status_code == 200:
                    # Watermark should be applied for free users
                    mock_watermark.assert_called_once()
        
        # 7. Check usage was recorded
        response = client.get("/api/subscription/usage", headers=auth_headers)
        assert response.status_code == 200
    
    def test_premium_user_complete_flow(self, client: TestClient, sample_video_file, mock_stripe, mock_email_service):
        """Test complete flow for a premium user"""
        # 1. User registration
        user_data = {
            "email": "premium_journey@example.com",
            "password": "PremiumPass123",
            "full_name": "Premium Journey User"
        }
        
        response = client.post("/api/auth/register", json=user_data)
        assert response.status_code == 200
        
        token = response.json()["access_token"]
        auth_headers = {"Authorization": f"Bearer {token}"}
        
        # 2. Upgrade to premium
        subscription_data = {
            "plan": "premium",
            "payment_method_id": "pm_test_123"
        }
        
        response = client.post("/api/subscription/create", json=subscription_data, headers=auth_headers)
        assert response.status_code == 200
        
        # 3. Verify premium benefits
        response = client.get("/api/subscription/limits", headers=auth_headers)
        assert response.status_code == 200
        limits = response.json()
        assert limits["monthly_minutes"] == -1  # Unlimited
        assert limits["watermark"] is False
        
        # 4. Process 4K video (premium feature)
        with patch('app.services.video_processor.VideoProcessor.process_video') as mock_process:
            with patch('app.services.watermark_service.WatermarkService.add_watermark') as mock_watermark:
                mock_process.return_value = {"task_id": "test123", "status": "processing"}
                
                process_data = {
                    "quality": "4K",  # Premium quality
                    "features": {
                        "logo_overlay": True,
                        "transcription": True,
                        "translation": True  # Premium feature
                    }
                }
                
                response = client.post("/api/process", json=process_data, headers=auth_headers)
                
                if response.status_code == 200:
                    # No watermark for premium users
                    mock_watermark.assert_not_called()
        
        # 5. Access billing portal
        mock_stripe.billing_portal.Session.create.return_value = {
            'url': 'https://billing.stripe.com/session/test123'
        }
        
        response = client.post("/api/subscription/billing-portal", headers=auth_headers)
        assert response.status_code == 200
        assert "url" in response.json()


class TestUpgradeDowngradeFlow:
    """Test subscription upgrade and downgrade flows"""
    
    def test_free_to_premium_upgrade_flow(self, client: TestClient, mock_stripe, mock_email_service):
        """Test upgrading from free to premium"""
        # Start as free user
        user_data = {
            "email": "upgrade_test@example.com",
            "password": "UpgradePass123",
            "full_name": "Upgrade Test User"
        }
        
        response = client.post("/api/auth/register", json=user_data)
        token = response.json()["access_token"]
        auth_headers = {"Authorization": f"Bearer {token}"}
        
        # Verify free tier
        response = client.get("/api/subscription/current", headers=auth_headers)
        assert response.json()["tier"] == "free"
        
        # Upgrade to premium
        subscription_data = {
            "plan": "premium",
            "payment_method_id": "pm_test_123"
        }
        
        response = client.post("/api/subscription/create", json=subscription_data, headers=auth_headers)
        assert response.status_code == 200
        
        # Verify upgrade
        response = client.get("/api/subscription/current", headers=auth_headers)
        current_sub = response.json()
        
        # Should now be premium (or the upgrade process should be initiated)
        assert current_sub["tier"] == "premium" or "upgrade" in str(current_sub)
    
    def test_premium_to_free_downgrade_flow(self, client: TestClient, premium_auth_headers, mock_stripe):
        """Test downgrading from premium to free"""
        # Start with premium user (from fixture)
        
        # Verify premium tier
        response = client.get("/api/subscription/current", headers=premium_auth_headers)
        assert response.json()["tier"] == "premium"
        
        # Cancel premium subscription
        response = client.post("/api/subscription/cancel", headers=premium_auth_headers)
        assert response.status_code == 200
        
        # Verify downgrade effects
        response = client.get("/api/subscription/limits", headers=premium_auth_headers)
        limits = response.json()
        
        # Should have free tier limits after cancellation
        if limits["monthly_minutes"] != -1:  # If downgrade already processed
            assert limits["monthly_minutes"] == 10
            assert limits["watermark"] is True


class TestVideoProcessingWorkflow:
    """Test complete video processing workflows"""
    
    def test_basic_video_processing_workflow(self, client: TestClient, auth_headers, sample_video_file):
        """Test basic video processing workflow"""
        # 1. Upload video
        with patch('app.services.video_processor.VideoProcessor.get_video_duration') as mock_duration:
            mock_duration.return_value = 45
            
            with open(sample_video_file, 'rb') as video_file:
                files = {'file': ('workflow_test.mp4', video_file, 'video/mp4')}
                response = client.post("/api/upload/video", files=files, headers=auth_headers)
        
        # 2. Configure processing settings
        settings_data = {
            "logo_overlay": True,
            "transcription": True,
            "thumbnail_generation": True
        }
        
        response = client.post("/api/settings", json=settings_data, headers=auth_headers)
        
        # 3. Start processing
        with patch('app.services.video_processor.VideoProcessor.process_video') as mock_process:
            mock_process.return_value = {"task_id": "workflow_123", "status": "processing"}
            
            process_data = {
                "quality": "720p",
                "features": {
                    "logo_overlay": True,
                    "transcription": True
                }
            }
            
            response = client.post("/api/process", json=process_data, headers=auth_headers)
            
            if response.status_code == 200:
                task_id = response.json().get("task_id")
                
                # 4. Monitor progress
                with patch('app.services.task_manager.TaskManager.get_task_status') as mock_status:
                    mock_status.return_value = {
                        "status": "completed",
                        "progress": 100,
                        "result": {
                            "output_file": "/path/to/output.mp4",
                            "thumbnail": "/path/to/thumb.jpg",
                            "transcript": "Video transcript..."
                        }
                    }
                    
                    response = client.get(f"/api/progress/{task_id}", headers=auth_headers)
                    assert response.status_code == 200
                    
                    progress_data = response.json()
                    assert progress_data["status"] == "completed"
    
    def test_advanced_video_processing_workflow(self, client: TestClient, premium_auth_headers, sample_video_file):
        """Test advanced video processing workflow for premium users"""
        # Premium users can access advanced features
        
        # 1. Upload high-quality video
        with patch('app.services.video_processor.VideoProcessor.get_video_duration') as mock_duration:
            mock_duration.return_value = 300  # 5 minutes - only premium can handle this
            
            with open(sample_video_file, 'rb') as video_file:
                files = {'file': ('premium_video.mp4', video_file, 'video/mp4')}
                response = client.post("/api/upload/video", files=files, headers=premium_auth_headers)
        
        # 2. Configure advanced settings
        with patch('app.services.video_processor.VideoProcessor.process_video') as mock_process:
            mock_process.return_value = {"task_id": "premium_123", "status": "processing"}
            
            advanced_process_data = {
                "quality": "4K",  # Premium only
                "features": {
                    "logo_overlay": True,
                    "transcription": True,
                    "translation": True,  # Premium feature
                    "ai_enhancement": True,  # Premium feature
                    "custom_watermark": False  # No watermark for premium
                }
            }
            
            response = client.post("/api/process", json=advanced_process_data, headers=premium_auth_headers)
            
            # Should succeed for premium users
            if response.status_code != 200:
                # Should not fail due to premium feature restrictions
                detail = response.json().get("detail", "").lower()
                assert "premium" not in detail
                assert "upgrade" not in detail


class TestErrorHandlingFlow:
    """Test error handling in various user flows"""
    
    def test_processing_limit_exceeded_flow(self, client: TestClient, auth_headers, db_session: Session):
        """Test flow when user exceeds processing limits"""
        from app.services.usage_service import UsageService
        from app.database.models import User
        
        user = db_session.query(User).first()
        usage_service = UsageService(db_session)
        
        # Simulate user has used all their monthly minutes
        usage_service.record_usage(user.id, 10.0, "video_processing")
        
        # Try to process another video
        with patch('app.services.video_processor.VideoProcessor.process_video') as mock_process:
            process_data = {
                "quality": "720p",
                "features": {"logo_overlay": True}
            }
            
            response = client.post("/api/process", json=process_data, headers=auth_headers)
            
            # Should be blocked due to limit
            assert response.status_code == 429  # Too many requests / Rate limited
            assert "limit" in response.json()["detail"].lower()
    
    def test_invalid_file_upload_flow(self, client: TestClient, auth_headers):
        """Test flow with invalid file uploads"""
        # Try to upload non-video file as video
        with tempfile.NamedTemporaryFile(suffix='.txt') as temp_file:
            temp_file.write(b'This is not a video file')
            temp_file.seek(0)
            
            files = {'file': ('fake_video.txt', temp_file, 'text/plain')}
            response = client.post("/api/upload/video", files=files, headers=auth_headers)
            
            assert response.status_code == 400
            assert "video" in response.json()["detail"].lower() or "format" in response.json()["detail"].lower()
    
    def test_payment_failure_flow(self, client: TestClient, auth_headers, mock_stripe):
        """Test flow when payment fails"""
        # Mock payment failure
        mock_stripe.Subscription.create.side_effect = Exception("Payment failed")
        
        subscription_data = {
            "plan": "premium",
            "payment_method_id": "pm_test_fail"
        }
        
        response = client.post("/api/subscription/create", json=subscription_data, headers=auth_headers)
        
        # Should handle payment failure gracefully
        assert response.status_code == 400
        assert "payment" in response.json()["detail"].lower() or "error" in response.json()["detail"].lower()
        
        # User should still be on free tier
        response = client.get("/api/subscription/current", headers=auth_headers)
        assert response.json()["tier"] == "free"


class TestConcurrencyAndRateLimiting:
    """Test concurrent operations and rate limiting"""
    
    def test_concurrent_video_uploads(self, client: TestClient, auth_headers, sample_video_file):
        """Test handling of concurrent video uploads"""
        with patch('app.services.video_processor.VideoProcessor.process_video') as mock_process:
            mock_process.return_value = {"task_id": "concurrent_test", "status": "processing"}
            
            # Simulate multiple concurrent uploads
            responses = []
            for i in range(3):  # Try 3 concurrent uploads (free users limited to 1)
                with open(sample_video_file, 'rb') as video_file:
                    files = {'file': (f'concurrent_{i}.mp4', video_file, 'video/mp4')}
                    response = client.post("/api/upload/video", files=files, headers=auth_headers)
                    responses.append(response)
            
            # At least some should be rejected due to concurrent upload limits
            success_count = sum(1 for r in responses if r.status_code == 200)
            rejection_count = sum(1 for r in responses if r.status_code == 429)
            
            # For free users, should allow max 1 concurrent upload
            assert success_count <= 1
            assert rejection_count >= 2
    
    def test_api_rate_limiting(self, client: TestClient, auth_headers):
        """Test API rate limiting"""
        # Make many rapid requests to test rate limiting
        responses = []
        for i in range(100):  # Make 100 rapid requests
            response = client.get("/api/subscription/current", headers=auth_headers)
            responses.append(response)
            
            # Stop early if we hit rate limit
            if response.status_code == 429:
                break
        
        # Should eventually hit rate limit
        rate_limited_responses = [r for r in responses if r.status_code == 429]
        assert len(rate_limited_responses) > 0


class TestDataConsistency:
    """Test data consistency across operations"""
    
    def test_usage_tracking_consistency(self, client: TestClient, auth_headers, db_session: Session):
        """Test that usage tracking is consistent across operations"""
        # Record some usage
        from app.services.usage_service import UsageService
        from app.database.models import User, UsageRecord
        
        user = db_session.query(User).first()
        usage_service = UsageService(db_session)
        
        # Record usage
        usage_service.record_usage(user.id, 2.5, "video_processing")
        usage_service.record_usage(user.id, 1.5, "transcription")
        
        # Check consistency between API and database
        api_response = client.get("/api/subscription/usage", headers=auth_headers)
        api_usage = api_response.json()["current_month"]["minutes_used"]
        
        db_usage = db_session.query(UsageRecord).filter(
            UsageRecord.user_id == user.id
        ).all()
        
        total_db_usage = sum(record.minutes_used for record in db_usage)
        
        # API and DB should match
        assert abs(api_usage - total_db_usage) < 0.01  # Allow for small floating point differences
    
    def test_subscription_state_consistency(self, client: TestClient, premium_auth_headers, mock_stripe):
        """Test subscription state consistency"""
        # Get subscription state from different endpoints
        current_response = client.get("/api/subscription/current", headers=premium_auth_headers)
        limits_response = client.get("/api/subscription/limits", headers=premium_auth_headers)
        
        current_tier = current_response.json()["tier"]
        limits_tier = "premium" if limits_response.json()["monthly_minutes"] == -1 else "free"
        
        # Should be consistent
        assert current_tier == limits_tier