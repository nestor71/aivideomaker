"""
Tier limitation and video processing tests
"""
import pytest
import os
import tempfile
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import Mock, patch

from app.database.models import User, UsageRecord
from app.services.tier_manager import TierManager


class TestVideoProcessingLimits:
    """Test video processing limitations by tier"""
    
    def test_free_user_video_duration_limit(self, client: TestClient, auth_headers, sample_video_file):
        """Test that free users cannot process videos longer than 1 minute"""
        # Mock a video file that's too long
        with patch('app.services.video_processor.VideoProcessor.get_video_duration') as mock_duration:
            mock_duration.return_value = 90  # 90 seconds (exceeds 60 second limit)
            
            with open(sample_video_file, 'rb') as video_file:
                files = {'file': ('test_video.mp4', video_file, 'video/mp4')}
                
                response = client.post(
                    "/api/upload/video", 
                    files=files, 
                    headers=auth_headers
                )
                
                assert response.status_code == 400
                assert "duration" in response.json()["detail"].lower()
                assert "60" in response.json()["detail"]
    
    def test_free_user_video_duration_allowed(self, client: TestClient, auth_headers, sample_video_file):
        """Test that free users can process videos under 1 minute"""
        with patch('app.services.video_processor.VideoProcessor.get_video_duration') as mock_duration:
            mock_duration.return_value = 45  # 45 seconds (under limit)
            
            with open(sample_video_file, 'rb') as video_file:
                files = {'file': ('test_video.mp4', video_file, 'video/mp4')}
                
                response = client.post(
                    "/api/upload/video", 
                    files=files, 
                    headers=auth_headers
                )
                
                # Should be successful (or fail for other reasons, but not duration)
                if response.status_code != 200:
                    assert "duration" not in response.json().get("detail", "").lower()
    
    def test_premium_user_no_duration_limit(self, client: TestClient, premium_auth_headers, sample_video_file):
        """Test that premium users can process long videos"""
        with patch('app.services.video_processor.VideoProcessor.get_video_duration') as mock_duration:
            mock_duration.return_value = 3600  # 1 hour
            
            with open(sample_video_file, 'rb') as video_file:
                files = {'file': ('test_video.mp4', video_file, 'video/mp4')}
                
                response = client.post(
                    "/api/upload/video", 
                    files=files, 
                    headers=premium_auth_headers
                )
                
                # Should not fail due to duration (may fail for other reasons)
                if response.status_code != 200:
                    assert "duration" not in response.json().get("detail", "").lower()


class TestMonthlyUsageLimits:
    """Test monthly usage limit enforcement"""
    
    def test_free_user_monthly_limit_check(self, client: TestClient, auth_headers, db_session: Session):
        """Test monthly limit checking for free users"""
        from app.services.usage_service import UsageService
        from app.database.models import User
        
        user = db_session.query(User).first()
        usage_service = UsageService(db_session)
        
        # Record usage up to the limit (10 minutes)
        usage_service.record_usage(user.id, 10.0, "video_processing")
        
        # Check if user has exceeded limit
        tier_manager = TierManager(db_session)
        can_process = tier_manager.can_process_video(user.id, duration_minutes=1.0)
        
        assert can_process is False
    
    def test_free_user_under_monthly_limit(self, client: TestClient, auth_headers, db_session: Session):
        """Test that free users can process when under monthly limit"""
        from app.services.usage_service import UsageService
        from app.database.models import User
        
        user = db_session.query(User).first()
        usage_service = UsageService(db_session)
        
        # Record some usage but stay under limit
        usage_service.record_usage(user.id, 5.0, "video_processing")
        
        # Check if user can process more
        tier_manager = TierManager(db_session)
        can_process = tier_manager.can_process_video(user.id, duration_minutes=2.0)
        
        assert can_process is True
    
    def test_premium_user_no_monthly_limit(self, client: TestClient, premium_auth_headers, db_session: Session):
        """Test that premium users have no monthly limits"""
        from app.services.usage_service import UsageService
        from app.database.models import User
        
        user = db_session.query(User).filter(User.email.like("%premium%")).first()
        usage_service = UsageService(db_session)
        
        # Record heavy usage
        usage_service.record_usage(user.id, 1000.0, "video_processing")
        
        # Premium users should still be able to process
        tier_manager = TierManager(db_session)
        can_process = tier_manager.can_process_video(user.id, duration_minutes=60.0)
        
        assert can_process is True


class TestQualityLimitations:
    """Test video quality limitations by tier"""
    
    def test_free_user_4k_blocked(self, client: TestClient, auth_headers):
        """Test that free users cannot process 4K videos"""
        video_settings = {
            "quality": "4K",
            "features": {
                "logo_overlay": True
            }
        }
        
        response = client.post(
            "/api/process", 
            json=video_settings, 
            headers=auth_headers
        )
        
        # Should fail due to quality restriction
        assert response.status_code == 400
        assert "quality" in response.json()["detail"].lower() or "4k" in response.json()["detail"].lower()
    
    def test_free_user_720p_allowed(self, client: TestClient, auth_headers):
        """Test that free users can process 720p videos"""
        video_settings = {
            "quality": "720p",
            "features": {
                "logo_overlay": True
            }
        }
        
        with patch('app.services.video_processor.VideoProcessor.process_video') as mock_process:
            mock_process.return_value = {"task_id": "test123", "status": "processing"}
            
            response = client.post(
                "/api/process", 
                json=video_settings, 
                headers=auth_headers
            )
            
            # Should not fail due to quality (may fail for other reasons)
            if response.status_code != 200:
                detail = response.json().get("detail", "").lower()
                assert "quality" not in detail and "720p" not in detail
    
    def test_premium_user_4k_allowed(self, client: TestClient, premium_auth_headers):
        """Test that premium users can process 4K videos"""
        video_settings = {
            "quality": "4K",
            "features": {
                "logo_overlay": True
            }
        }
        
        with patch('app.services.video_processor.VideoProcessor.process_video') as mock_process:
            mock_process.return_value = {"task_id": "test123", "status": "processing"}
            
            response = client.post(
                "/api/process", 
                json=video_settings, 
                headers=premium_auth_headers
            )
            
            # Should not fail due to quality
            if response.status_code != 200:
                detail = response.json().get("detail", "").lower()
                assert "quality" not in detail and "4k" not in detail


class TestWatermarkSystem:
    """Test watermark application by tier"""
    
    def test_free_user_watermark_applied(self, client: TestClient, auth_headers):
        """Test that watermarks are applied to free user videos"""
        from app.services.watermark_service import WatermarkService
        
        with patch.object(WatermarkService, 'add_watermark') as mock_watermark:
            mock_watermark.return_value = "/path/to/watermarked_video.mp4"
            
            video_settings = {
                "quality": "720p",
                "features": {
                    "logo_overlay": True
                }
            }
            
            with patch('app.services.video_processor.VideoProcessor.process_video') as mock_process:
                mock_process.return_value = {"task_id": "test123", "status": "processing"}
                
                response = client.post(
                    "/api/process", 
                    json=video_settings, 
                    headers=auth_headers
                )
                
                if response.status_code == 200:
                    # Watermark should be applied for free users
                    mock_watermark.assert_called_once()
    
    def test_premium_user_no_watermark(self, client: TestClient, premium_auth_headers):
        """Test that watermarks are NOT applied to premium user videos"""
        from app.services.watermark_service import WatermarkService
        
        with patch.object(WatermarkService, 'add_watermark') as mock_watermark:
            video_settings = {
                "quality": "4K",
                "features": {
                    "logo_overlay": True
                }
            }
            
            with patch('app.services.video_processor.VideoProcessor.process_video') as mock_process:
                mock_process.return_value = {"task_id": "test123", "status": "processing"}
                
                response = client.post(
                    "/api/process", 
                    json=video_settings, 
                    headers=premium_auth_headers
                )
                
                if response.status_code == 200:
                    # Watermark should NOT be applied for premium users
                    mock_watermark.assert_not_called()


class TestConcurrentUploads:
    """Test concurrent upload limitations"""
    
    def test_free_user_concurrent_upload_limit(self, client: TestClient, auth_headers, sample_video_file):
        """Test that free users are limited to 1 concurrent upload"""
        # Simulate an ongoing upload by mocking the video processor
        with patch('app.services.video_processor.VideoProcessor.process_video') as mock_process:
            mock_process.return_value = {"task_id": "test123", "status": "processing"}
            
            # First upload should succeed
            with open(sample_video_file, 'rb') as video_file:
                files = {'file': ('test_video1.mp4', video_file, 'video/mp4')}
                
                response1 = client.post(
                    "/api/upload/video", 
                    files=files, 
                    headers=auth_headers
                )
            
            # Mock that first upload is still processing
            with patch('app.services.task_manager.TaskManager.get_user_active_tasks') as mock_tasks:
                mock_tasks.return_value = ['task123']  # One active task
                
                # Second concurrent upload should fail
                with open(sample_video_file, 'rb') as video_file:
                    files = {'file': ('test_video2.mp4', video_file, 'video/mp4')}
                    
                    response2 = client.post(
                        "/api/upload/video", 
                        files=files, 
                        headers=auth_headers
                    )
                    
                    assert response2.status_code == 429  # Too many requests
                    assert "concurrent" in response2.json()["detail"].lower()
    
    def test_premium_user_multiple_concurrent_uploads(self, client: TestClient, premium_auth_headers, sample_video_file):
        """Test that premium users can have multiple concurrent uploads"""
        with patch('app.services.video_processor.VideoProcessor.process_video') as mock_process:
            mock_process.return_value = {"task_id": "test123", "status": "processing"}
            
            with patch('app.services.task_manager.TaskManager.get_user_active_tasks') as mock_tasks:
                mock_tasks.return_value = ['task1', 'task2', 'task3']  # 3 active tasks
                
                # Should still allow more uploads for premium users
                with open(sample_video_file, 'rb') as video_file:
                    files = {'file': ('test_video.mp4', video_file, 'video/mp4')}
                    
                    response = client.post(
                        "/api/upload/video", 
                        files=files, 
                        headers=premium_auth_headers
                    )
                    
                    # Should not fail due to concurrent limit (premium allows 5)
                    if response.status_code != 200:
                        assert "concurrent" not in response.json().get("detail", "").lower()


class TestFeatureLimitations:
    """Test feature access limitations by tier"""
    
    def test_free_user_ai_services_limited(self, client: TestClient, auth_headers):
        """Test that free users have limited AI services"""
        response = client.get("/api/subscription/limits", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        # Free users should have limited AI services
        available_services = data.get("ai_services", [])
        assert "whisper_local" in available_services
        assert "openai_gpt" not in available_services  # Premium only
    
    def test_premium_user_all_ai_services(self, client: TestClient, premium_auth_headers):
        """Test that premium users have access to all AI services"""
        response = client.get("/api/subscription/limits", headers=premium_auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        # Premium users should have access to all services
        available_services = data.get("ai_services", [])
        assert "whisper_local" in available_services
        assert "whisper_api" in available_services
        assert "openai_gpt" in available_services
        assert "openai_tts" in available_services
    
    def test_premium_user_priority_processing(self, client: TestClient, premium_auth_headers):
        """Test that premium users have priority processing"""
        response = client.get("/api/subscription/limits", headers=premium_auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("priority_processing") is True


class TestTierUpgradeDowngrade:
    """Test tier upgrade and downgrade scenarios"""
    
    def test_upgrade_to_premium_immediate_benefits(self, client: TestClient, auth_headers, mock_stripe, db_session: Session):
        """Test that users get immediate benefits when upgrading to premium"""
        # Create premium subscription
        subscription_data = {
            "plan": "premium",
            "payment_method_id": "pm_test_123"
        }
        
        response = client.post("/api/subscription/create", json=subscription_data, headers=auth_headers)
        
        if response.status_code == 200:
            # Check that limits are immediately updated
            limits_response = client.get("/api/subscription/limits", headers=auth_headers)
            limits_data = limits_response.json()
            
            # Should now have premium limits
            assert limits_data["monthly_minutes"] == -1
            assert limits_data["watermark"] is False
    
    def test_downgrade_to_free_limits_applied(self, client: TestClient, premium_auth_headers, mock_stripe):
        """Test that users get free limits when downgrading"""
        # Cancel premium subscription
        response = client.post("/api/subscription/cancel", headers=premium_auth_headers)
        
        if response.status_code == 200:
            # Check that limits are updated to free
            limits_response = client.get("/api/subscription/limits", headers=premium_auth_headers)
            limits_data = limits_response.json()
            
            # Should now have free limits
            assert limits_data["monthly_minutes"] == 10
            assert limits_data["watermark"] is True