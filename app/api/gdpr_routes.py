"""
GDPR API routes for data privacy and compliance
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta

from app.database.base import get_session
from app.database.models import User
from app.database.gdpr_models import ConsentType, DataProcessingPurpose
from app.services.gdpr_service import GDPRService
from app.services.auth_service import get_current_user, get_current_admin_user
from app.core.logger import logger
from app.schemas.gdpr import (
    ConsentRequest, ConsentResponse, ConsentSummary,
    DataExportRequest as DataExportRequestSchema, DataExportResponse, DataExportStatus,
    DataDeletionRequest as DataDeletionRequestSchema, DataDeletionResponse,
    PrivacyDashboard, DataCategoryInfo, RetentionInfo,
    CookieConsentRequest, CookieConsentResponse,
    DataProcessingRequest, DataProcessingResponse,
    PrivacyPolicyResponse, PrivacyPolicyAcceptance,
    DataSubjectRightsInfo, GDPRAdminDashboard,
    DataBreachNotificationRequest, DataBreachNotificationResponse,
    UserDataInventoryResponse, GDPRComplianceReport
)

router = APIRouter(prefix="/api/gdpr", tags=["GDPR Compliance"])


# Consent Management Endpoints
@router.post("/consent", response_model=ConsentResponse)
async def update_consent(
    consent_request: ConsentRequest,
    request: Request,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Update user consent for data processing"""
    try:
        gdpr_service = GDPRService(db)
        
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        
        consent = gdpr_service.record_consent(
            user_id=current_user.id,
            consent_type=consent_request.consent_type,
            consent_given=consent_request.consent_given,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        return ConsentResponse(
            id=consent.id,
            consent_type=consent.consent_type.value,
            consent_given=consent.consent_given,
            consent_date=consent.consent_date,
            consent_withdrawn_date=consent.consent_withdrawn_date,
            consent_version=consent.consent_version
        )
        
    except Exception as e:
        logger.error(f"Error updating consent: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update consent"
        )


@router.get("/consent", response_model=List[ConsentResponse])
async def get_user_consents(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get all user consents"""
    try:
        gdpr_service = GDPRService(db)
        consents = gdpr_service.get_user_consents(current_user.id)
        
        return [
            ConsentResponse(
                id=consent.id,
                consent_type=consent.consent_type.value,
                consent_given=consent.consent_given,
                consent_date=consent.consent_date,
                consent_withdrawn_date=consent.consent_withdrawn_date,
                consent_version=consent.consent_version
            )
            for consent in consents
        ]
        
    except Exception as e:
        logger.error(f"Error retrieving consents: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve consents"
        )


@router.get("/consent/summary", response_model=ConsentSummary)
async def get_consent_summary(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get summary of user consents"""
    try:
        gdpr_service = GDPRService(db)
        consents = gdpr_service.get_user_consents(current_user.id)
        
        consent_dict = {
            consent.consent_type.value: consent.consent_given 
            for consent in consents
        }
        
        # Find most recent consent date
        latest_date = max([c.consent_date for c in consents]) if consents else datetime.utcnow()
        
        return ConsentSummary(
            essential=True,  # Always required
            analytics=consent_dict.get("analytics", False),
            marketing=consent_dict.get("marketing", False),
            third_party=consent_dict.get("third_party", False),
            cookies=consent_dict.get("cookies", False),
            last_updated=latest_date
        )
        
    except Exception as e:
        logger.error(f"Error retrieving consent summary: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve consent summary"
        )


# Data Export (Right to Data Portability)
@router.post("/export", response_model=DataExportResponse)
async def request_data_export(
    export_request: DataExportRequestSchema,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Request data export (Right to Data Portability)"""
    try:
        gdpr_service = GDPRService(db)
        
        ip_address = request.client.host if request.client else None
        
        export_req = gdpr_service.create_data_export_request(
            user_id=current_user.id,
            data_categories=export_request.data_categories,
            export_format=export_request.export_format,
            ip_address=ip_address
        )
        
        # Process export in background
        background_tasks.add_task(
            gdpr_service.process_data_export_request, 
            export_req.id
        )
        
        return DataExportResponse(
            id=export_req.id,
            request_date=export_req.request_date,
            status=export_req.status,
            export_format=export_req.export_format,
            data_categories=export_req.data_categories,
            completed_date=export_req.completed_date,
            download_expires=export_req.download_expires
        )
        
    except Exception as e:
        logger.error(f"Error requesting data export: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to request data export"
        )


@router.get("/export", response_model=List[DataExportResponse])
async def get_export_requests(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get user's data export requests"""
    try:
        from app.database.gdpr_models import DataExportRequest
        
        requests = db.query(DataExportRequest).filter(
            DataExportRequest.user_id == current_user.id
        ).order_by(DataExportRequest.request_date.desc()).all()
        
        return [
            DataExportResponse(
                id=req.id,
                request_date=req.request_date,
                status=req.status,
                export_format=req.export_format,
                data_categories=req.data_categories,
                completed_date=req.completed_date,
                download_expires=req.download_expires
            )
            for req in requests
        ]
        
    except Exception as e:
        logger.error(f"Error retrieving export requests: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve export requests"
        )


@router.get("/export/{request_id}/status", response_model=DataExportStatus)
async def get_export_status(
    request_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get status of data export request"""
    try:
        from app.database.gdpr_models import DataExportRequest
        
        export_request = db.query(DataExportRequest).filter(
            DataExportRequest.id == request_id,
            DataExportRequest.user_id == current_user.id
        ).first()
        
        if not export_request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Export request not found"
            )
        
        # Calculate progress based on status
        progress_map = {
            "pending": 0,
            "processing": 50,
            "completed": 100,
            "failed": 0
        }
        
        return DataExportStatus(
            status=export_request.status,
            message=f"Export request is {export_request.status}",
            progress=progress_map.get(export_request.status, 0),
            estimated_completion=export_request.download_expires
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting export status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get export status"
        )


# Data Deletion (Right to Erasure)
@router.post("/delete", response_model=DataDeletionResponse)
async def request_data_deletion(
    deletion_request: DataDeletionRequestSchema,
    request: Request,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Request data deletion (Right to Erasure)"""
    try:
        if not deletion_request.confirmation:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Confirmation required for data deletion"
            )
        
        gdpr_service = GDPRService(db)
        
        ip_address = request.client.host if request.client else None
        
        deletion_req = gdpr_service.create_data_deletion_request(
            user_id=current_user.id,
            data_categories=deletion_request.data_categories,
            reason=deletion_request.reason,
            ip_address=ip_address
        )
        
        return DataDeletionResponse(
            id=deletion_req.id,
            request_date=deletion_req.request_date,
            status=deletion_req.status,
            data_categories=deletion_req.data_categories,
            scheduled_deletion_date=deletion_req.scheduled_deletion_date,
            reason=deletion_req.reason
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error requesting data deletion: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to request data deletion"
        )


@router.get("/delete", response_model=List[DataDeletionResponse])
async def get_deletion_requests(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get user's data deletion requests"""
    try:
        from app.database.gdpr_models import DataDeletionRequest
        
        requests = db.query(DataDeletionRequest).filter(
            DataDeletionRequest.user_id == current_user.id
        ).order_by(DataDeletionRequest.request_date.desc()).all()
        
        return [
            DataDeletionResponse(
                id=req.id,
                request_date=req.request_date,
                status=req.status,
                data_categories=req.data_categories,
                scheduled_deletion_date=req.scheduled_deletion_date,
                grace_period_ends=req.scheduled_deletion_date,
                reason=req.reason
            )
            for req in requests
        ]
        
    except Exception as e:
        logger.error(f"Error retrieving deletion requests: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve deletion requests"
        )


@router.delete("/delete/{request_id}/cancel")
async def cancel_deletion_request(
    request_id: int,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Cancel a pending deletion request"""
    try:
        from app.database.gdpr_models import DataDeletionRequest
        
        deletion_request = db.query(DataDeletionRequest).filter(
            DataDeletionRequest.id == request_id,
            DataDeletionRequest.user_id == current_user.id,
            DataDeletionRequest.status.in_(["pending", "scheduled"])
        ).first()
        
        if not deletion_request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Deletion request not found or cannot be cancelled"
            )
        
        deletion_request.status = "cancelled"
        db.commit()
        
        return {"message": "Deletion request cancelled successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling deletion request: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel deletion request"
        )


# Privacy Dashboard
@router.get("/dashboard", response_model=PrivacyDashboard)
async def get_privacy_dashboard(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get user's privacy dashboard"""
    try:
        gdpr_service = GDPRService(db)
        
        # Get consent summary
        consents = gdpr_service.get_user_consents(current_user.id)
        consent_dict = {c.consent_type.value: c.consent_given for c in consents}
        latest_consent_date = max([c.consent_date for c in consents]) if consents else datetime.utcnow()
        
        consent_summary = ConsentSummary(
            essential=True,
            analytics=consent_dict.get("analytics", False),
            marketing=consent_dict.get("marketing", False),
            third_party=consent_dict.get("third_party", False),
            cookies=consent_dict.get("cookies", False),
            last_updated=latest_consent_date
        )
        
        # Get active requests
        from app.database.gdpr_models import DataExportRequest, DataDeletionRequest
        
        active_exports = db.query(DataExportRequest).filter(
            DataExportRequest.user_id == current_user.id,
            DataExportRequest.status.in_(["pending", "processing"])
        ).all()
        
        active_deletions = db.query(DataDeletionRequest).filter(
            DataDeletionRequest.user_id == current_user.id,
            DataDeletionRequest.status.in_(["pending", "scheduled"])
        ).all()
        
        return PrivacyDashboard(
            user_id=current_user.id,
            consents=consent_summary,
            data_categories=["profile", "usage", "payments", "consents", "communications"],
            retention_info={
                "profile": "Account lifetime + 3 years",
                "usage": "2 years from last activity",
                "payments": "7 years for tax compliance"
            },
            active_export_requests=[
                DataExportResponse(
                    id=req.id,
                    request_date=req.request_date,
                    status=req.status,
                    export_format=req.export_format,
                    data_categories=req.data_categories,
                    completed_date=req.completed_date,
                    download_expires=req.download_expires
                ) for req in active_exports
            ],
            active_deletion_requests=[
                DataDeletionResponse(
                    id=req.id,
                    request_date=req.request_date,
                    status=req.status,
                    data_categories=req.data_categories,
                    scheduled_deletion_date=req.scheduled_deletion_date,
                    reason=req.reason
                ) for req in active_deletions
            ],
            privacy_policy_version="2.0",
            last_policy_acceptance=current_user.created_at
        )
        
    except Exception as e:
        logger.error(f"Error retrieving privacy dashboard: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve privacy dashboard"
        )


# Data Categories Information
@router.get("/data-categories", response_model=List[DataCategoryInfo])
async def get_data_categories():
    """Get information about data categories we process"""
    return [
        DataCategoryInfo(
            category="profile",
            description="Basic profile information",
            data_types=["email", "name", "avatar", "preferences"],
            legal_basis="Contract performance",
            retention_period=None,  # Until account deletion
            can_be_exported=True,
            can_be_deleted=True,
            third_parties=[]
        ),
        DataCategoryInfo(
            category="usage",
            description="Usage analytics and statistics",
            data_types=["video processing history", "feature usage", "timestamps"],
            legal_basis="Legitimate interest",
            retention_period=730,  # 2 years
            can_be_exported=True,
            can_be_deleted=False,  # Anonymized instead
            third_parties=["Analytics providers"]
        ),
        DataCategoryInfo(
            category="payments",
            description="Payment and billing information",
            data_types=["payment history", "billing address", "subscription details"],
            legal_basis="Legal obligation",
            retention_period=2555,  # 7 years
            can_be_exported=True,
            can_be_deleted=False,  # Legal requirement
            third_parties=["Stripe", "Tax authorities"]
        ),
        DataCategoryInfo(
            category="communications",
            description="Email communications and preferences",
            data_types=["email history", "notification preferences"],
            legal_basis="Consent",
            retention_period=1095,  # 3 years
            can_be_exported=True,
            can_be_deleted=True,
            third_parties=["Email service providers"]
        )
    ]


# Cookie Consent
@router.post("/cookies", response_model=CookieConsentResponse)
async def update_cookie_consent(
    cookie_request: CookieConsentRequest,
    request: Request,
    db: Session = Depends(get_session),
    current_user: Optional[User] = Depends(get_current_user)  # Optional for anonymous users
):
    """Update cookie consent preferences"""
    try:
        from app.database.gdpr_models import CookieConsent
        
        # For anonymous users, use session ID
        session_id = request.session.get("session_id") if not current_user else None
        user_id = current_user.id if current_user else None
        
        # Delete existing cookie consent
        if current_user:
            db.query(CookieConsent).filter(CookieConsent.user_id == user_id).delete()
        else:
            db.query(CookieConsent).filter(CookieConsent.session_id == session_id).delete()
        
        # Create new consent
        cookie_consent = CookieConsent(
            user_id=user_id,
            session_id=session_id,
            essential_cookies=cookie_request.essential_cookies,
            functional_cookies=cookie_request.functional_cookies,
            analytics_cookies=cookie_request.analytics_cookies,
            marketing_cookies=cookie_request.marketing_cookies,
            expires_date=datetime.utcnow() + timedelta(days=365),  # 1 year
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent")
        )
        
        db.add(cookie_consent)
        db.commit()
        
        return CookieConsentResponse(
            id=cookie_consent.id,
            essential_cookies=cookie_consent.essential_cookies,
            functional_cookies=cookie_consent.functional_cookies,
            analytics_cookies=cookie_consent.analytics_cookies,
            marketing_cookies=cookie_consent.marketing_cookies,
            consent_date=cookie_consent.consent_date,
            expires_date=cookie_consent.expires_date
        )
        
    except Exception as e:
        logger.error(f"Error updating cookie consent: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update cookie consent"
        )


# Data Subject Rights Information
@router.get("/rights", response_model=DataSubjectRightsInfo)
async def get_data_subject_rights():
    """Get information about data subject rights under GDPR"""
    return DataSubjectRightsInfo(
        right_to_information={
            "description": "Right to be informed about data processing",
            "how_to_exercise": "Review our privacy policy",
            "response_time": "Available immediately"
        },
        right_of_access={
            "description": "Right to access your personal data",
            "how_to_exercise": "Use the data export feature in your privacy dashboard",
            "response_time": "Within 1 month"
        },
        right_to_rectification={
            "description": "Right to correct inaccurate personal data",
            "how_to_exercise": "Update your profile in account settings",
            "response_time": "Immediate for profile data"
        },
        right_to_erasure={
            "description": "Right to have personal data deleted",
            "how_to_exercise": "Use the data deletion feature in your privacy dashboard",
            "response_time": "Within 30 days, with 30-day grace period"
        },
        right_to_restrict_processing={
            "description": "Right to limit how we process your data",
            "how_to_exercise": "Contact our support team",
            "response_time": "Within 1 month"
        },
        right_to_data_portability={
            "description": "Right to receive your data in a portable format",
            "how_to_exercise": "Use the data export feature",
            "response_time": "Within 1 month"
        },
        right_to_object={
            "description": "Right to object to processing based on legitimate interests",
            "how_to_exercise": "Withdraw consent in your privacy settings",
            "response_time": "Immediate for consent-based processing"
        },
        right_not_to_be_subject_to_automated_decision_making={
            "description": "Right not to be subject to automated decisions",
            "how_to_exercise": "We do not use automated decision-making",
            "response_time": "N/A"
        }
    )


# Admin Endpoints (require admin privileges)
@router.get("/admin/dashboard", response_model=GDPRAdminDashboard)
async def get_gdpr_admin_dashboard(
    db: Session = Depends(get_session),
    admin_user: User = Depends(get_current_admin_user)
):
    """Get GDPR admin dashboard"""
    try:
        from app.database.gdpr_models import (
            UserConsent, DataExportRequest, DataDeletionRequest, 
            PrivacyPolicyVersion, DataBreachNotification
        )
        
        # Calculate statistics
        total_users_with_consent = db.query(UserConsent.user_id).distinct().count()
        pending_exports = db.query(DataExportRequest).filter(
            DataExportRequest.status == "pending"
        ).count()
        pending_deletions = db.query(DataDeletionRequest).filter(
            DataDeletionRequest.status == "pending"
        ).count()
        overdue_deletions = db.query(DataDeletionRequest).filter(
            DataDeletionRequest.status == "scheduled",
            DataDeletionRequest.scheduled_deletion_date <= datetime.utcnow()
        ).count()
        
        current_policy = db.query(PrivacyPolicyVersion).filter(
            PrivacyPolicyVersion.is_active == True
        ).first()
        
        breach_notifications = db.query(DataBreachNotification).filter(
            DataBreachNotification.discovery_date >= datetime.utcnow() - timedelta(days=30)
        ).count()
        
        return GDPRAdminDashboard(
            total_users_with_consent=total_users_with_consent,
            pending_export_requests=pending_exports,
            pending_deletion_requests=pending_deletions,
            overdue_deletion_requests=overdue_deletions,
            privacy_policy_version=current_policy.version if current_policy else "N/A",
            users_requiring_new_consent=0,  # Would calculate based on policy changes
            data_breach_notifications=breach_notifications,
            retention_policy_compliance={
                "compliant": 85.5,
                "needs_review": 14.5,
                "overdue": 0.0
            }
        )
        
    except Exception as e:
        logger.error(f"Error retrieving GDPR admin dashboard: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve GDPR admin dashboard"
        )