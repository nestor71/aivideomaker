"""
GDPR Service for handling data privacy operations
"""
import json
import hashlib
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.database.models import User, UsageRecord, PaymentHistory, Subscription, AuditLog
from app.database.gdpr_models import (
    UserConsent, DataProcessingRecord, DataExportRequest, DataDeletionRequest,
    PrivacyPolicyVersion, CookieConsent, DataRetentionPolicy, UserDataInventory,
    ConsentType, DataProcessingPurpose, DataRetentionStatus
)
from app.core.logger import logger
from app.services.email_service import EmailService


class GDPRService:
    """Service for GDPR compliance operations"""
    
    def __init__(self, db: Session):
        self.db = db
        self.email_service = EmailService()
    
    # Consent Management
    def record_consent(
        self,
        user_id: int,
        consent_type: ConsentType,
        consent_given: bool,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> UserConsent:
        """Record user consent for data processing"""
        try:
            # Check if consent already exists
            existing_consent = self.db.query(UserConsent).filter(
                and_(
                    UserConsent.user_id == user_id,
                    UserConsent.consent_type == consent_type
                )
            ).first()
            
            if existing_consent:
                # Update existing consent
                existing_consent.consent_given = consent_given
                existing_consent.consent_date = datetime.utcnow()
                if not consent_given:
                    existing_consent.consent_withdrawn_date = datetime.utcnow()
                existing_consent.ip_address = ip_address
                existing_consent.user_agent = user_agent
                consent = existing_consent
            else:
                # Create new consent record
                consent = UserConsent(
                    user_id=user_id,
                    consent_type=consent_type,
                    consent_given=consent_given,
                    ip_address=ip_address,
                    user_agent=user_agent
                )
                self.db.add(consent)
            
            self.db.commit()
            
            # Record the consent action in audit log
            self._create_audit_log(
                user_id,
                "consent_updated",
                f"Consent {consent_type.value} {'granted' if consent_given else 'withdrawn'}"
            )
            
            logger.info(f"Consent recorded: user_id={user_id}, type={consent_type.value}, given={consent_given}")
            return consent
            
        except Exception as e:
            logger.error(f"Error recording consent: {str(e)}")
            self.db.rollback()
            raise
    
    def get_user_consents(self, user_id: int) -> List[UserConsent]:
        """Get all consents for a user"""
        return self.db.query(UserConsent).filter(UserConsent.user_id == user_id).all()
    
    def check_consent(self, user_id: int, consent_type: ConsentType) -> bool:
        """Check if user has given specific consent"""
        consent = self.db.query(UserConsent).filter(
            and_(
                UserConsent.user_id == user_id,
                UserConsent.consent_type == consent_type,
                UserConsent.consent_given == True
            )
        ).first()
        return consent is not None
    
    # Data Processing Records
    def record_data_processing(
        self,
        user_id: int,
        purpose: DataProcessingPurpose,
        data_categories: List[str],
        legal_basis: str,
        retention_period: Optional[int] = None,
        third_parties: Optional[List[str]] = None,
        automated_decision_making: bool = False
    ) -> DataProcessingRecord:
        """Record data processing activity"""
        try:
            record = DataProcessingRecord(
                user_id=user_id,
                purpose=purpose,
                data_categories=data_categories,
                legal_basis=legal_basis,
                retention_period=retention_period,
                third_parties=third_parties or [],
                automated_decision_making=automated_decision_making
            )
            
            self.db.add(record)
            self.db.commit()
            
            logger.info(f"Data processing recorded: user_id={user_id}, purpose={purpose.value}")
            return record
            
        except Exception as e:
            logger.error(f"Error recording data processing: {str(e)}")
            self.db.rollback()
            raise
    
    # Data Export (Right to Data Portability)
    def create_data_export_request(
        self,
        user_id: int,
        data_categories: List[str],
        export_format: str = "json",
        ip_address: Optional[str] = None
    ) -> DataExportRequest:
        """Create a data export request"""
        try:
            request = DataExportRequest(
                user_id=user_id,
                data_categories=data_categories,
                export_format=export_format,
                ip_address=ip_address
            )
            
            self.db.add(request)
            self.db.commit()
            
            # Send confirmation email
            user = self.db.query(User).filter(User.id == user_id).first()
            if user:
                self.email_service.send_data_export_confirmation(user.email, user.full_name)
            
            self._create_audit_log(user_id, "data_export_requested", f"Format: {export_format}")
            
            logger.info(f"Data export request created: user_id={user_id}, format={export_format}")
            return request
            
        except Exception as e:
            logger.error(f"Error creating data export request: {str(e)}")
            self.db.rollback()
            raise
    
    def process_data_export_request(self, request_id: int) -> Dict[str, Any]:
        """Process a data export request and generate the export file"""
        try:
            request = self.db.query(DataExportRequest).filter(
                DataExportRequest.id == request_id
            ).first()
            
            if not request:
                raise ValueError(f"Export request {request_id} not found")
            
            if request.status != "pending":
                raise ValueError(f"Request {request_id} is not pending")
            
            # Update status to processing
            request.status = "processing"
            self.db.commit()
            
            # Gather user data
            user_data = self._gather_user_data(request.user_id, request.data_categories)
            
            # Generate export file
            file_path = self._generate_export_file(request, user_data)
            
            # Update request with completion details
            request.status = "completed"
            request.completed_date = datetime.utcnow()
            request.file_path = file_path
            request.download_expires = datetime.utcnow() + timedelta(days=7)  # 7 days to download
            
            self.db.commit()
            
            # Send completion email
            user = self.db.query(User).filter(User.id == request.user_id).first()
            if user:
                self.email_service.send_data_export_ready(
                    user.email, 
                    user.full_name, 
                    request.download_expires
                )
            
            self._create_audit_log(request.user_id, "data_export_completed", f"File: {file_path}")
            
            logger.info(f"Data export completed: request_id={request_id}, file={file_path}")
            return {"status": "completed", "file_path": file_path, "expires": request.download_expires}
            
        except Exception as e:
            # Update request status to failed
            if 'request' in locals():
                request.status = "failed"
                self.db.commit()
            
            logger.error(f"Error processing data export: {str(e)}")
            raise
    
    # Data Deletion (Right to Erasure)
    def create_data_deletion_request(
        self,
        user_id: int,
        data_categories: List[str],
        reason: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> DataDeletionRequest:
        """Create a data deletion request"""
        try:
            request = DataDeletionRequest(
                user_id=user_id,
                data_categories=data_categories,
                reason=reason,
                ip_address=ip_address
            )
            
            self.db.add(request)
            self.db.commit()
            
            # Send confirmation email
            user = self.db.query(User).filter(User.id == user_id).first()
            if user:
                self.email_service.send_data_deletion_confirmation(user.email, user.full_name)
            
            self._create_audit_log(user_id, "data_deletion_requested", reason or "User request")
            
            logger.info(f"Data deletion request created: user_id={user_id}")
            return request
            
        except Exception as e:
            logger.error(f"Error creating data deletion request: {str(e)}")
            self.db.rollback()
            raise
    
    def process_data_deletion_request(self, request_id: int, admin_approved: bool = True) -> Dict[str, Any]:
        """Process a data deletion request"""
        try:
            request = self.db.query(DataDeletionRequest).filter(
                DataDeletionRequest.id == request_id
            ).first()
            
            if not request:
                raise ValueError(f"Deletion request {request_id} not found")
            
            if not admin_approved:
                request.status = "cancelled"
                self.db.commit()
                return {"status": "cancelled", "reason": "Not approved"}
            
            # Schedule deletion (30-day grace period)
            grace_period = datetime.utcnow() + timedelta(days=30)
            request.status = "scheduled"
            request.scheduled_deletion_date = grace_period
            self.db.commit()
            
            # Send final confirmation with grace period
            user = self.db.query(User).filter(User.id == request.user_id).first()
            if user:
                self.email_service.send_data_deletion_scheduled(
                    user.email, 
                    user.full_name, 
                    grace_period
                )
            
            self._create_audit_log(request.user_id, "data_deletion_scheduled", f"Scheduled for: {grace_period}")
            
            logger.info(f"Data deletion scheduled: request_id={request_id}, date={grace_period}")
            return {"status": "scheduled", "deletion_date": grace_period}
            
        except Exception as e:
            logger.error(f"Error processing data deletion request: {str(e)}")
            raise
    
    def execute_scheduled_deletions(self) -> int:
        """Execute all scheduled deletions that are due"""
        try:
            # Find all scheduled deletions that are due
            due_deletions = self.db.query(DataDeletionRequest).filter(
                and_(
                    DataDeletionRequest.status == "scheduled",
                    DataDeletionRequest.scheduled_deletion_date <= datetime.utcnow()
                )
            ).all()
            
            deleted_count = 0
            
            for request in due_deletions:
                try:
                    self._execute_data_deletion(request)
                    request.status = "completed"
                    request.completed_date = datetime.utcnow()
                    deleted_count += 1
                    
                    self._create_audit_log(
                        request.user_id, 
                        "data_deletion_executed", 
                        f"Request ID: {request.id}"
                    )
                    
                except Exception as e:
                    logger.error(f"Error executing deletion for request {request.id}: {str(e)}")
                    # Don't mark as failed, will retry next time
            
            self.db.commit()
            logger.info(f"Executed {deleted_count} scheduled deletions")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error executing scheduled deletions: {str(e)}")
            self.db.rollback()
            raise
    
    # Data Inventory Management
    def create_user_data_inventory(self, user_id: int) -> List[UserDataInventory]:
        """Create data inventory for a user"""
        try:
            # Define data categories and their locations
            data_categories = [
                ("personal_info", "users.email,users.full_name,users.avatar_url"),
                ("authentication", "users.hashed_password,users.verification_token"),
                ("oauth_data", "users.google_id,users.microsoft_id,users.apple_id"),
                ("subscription_data", "subscriptions.*"),
                ("usage_data", "usage_records.*"),
                ("payment_data", "payment_history.*"),
                ("audit_logs", "audit_logs.*"),
                ("consent_data", "user_consents.*"),
                ("processing_records", "data_processing_records.*")
            ]
            
            inventory_items = []
            user = self.db.query(User).filter(User.id == user_id).first()
            
            if not user:
                raise ValueError(f"User {user_id} not found")
            
            for category, location in data_categories:
                inventory_item = UserDataInventory(
                    user_id=user_id,
                    data_category=category,
                    data_location=location,
                    collection_date=user.created_at or datetime.utcnow(),
                    legal_basis="contract",  # Most data is for contract performance
                    is_sensitive="payment" in category or "auth" in category
                )
                
                inventory_items.append(inventory_item)
                self.db.add(inventory_item)
            
            self.db.commit()
            return inventory_items
            
        except Exception as e:
            logger.error(f"Error creating data inventory: {str(e)}")
            self.db.rollback()
            raise
    
    # Privacy Policy Management
    def create_privacy_policy_version(
        self,
        version: str,
        effective_date: datetime,
        policy_content: str,
        major_changes: Optional[List[str]] = None,
        requires_new_consent: bool = False
    ) -> PrivacyPolicyVersion:
        """Create a new privacy policy version"""
        try:
            # Generate content hash
            content_hash = hashlib.sha256(policy_content.encode()).hexdigest()
            
            # Deactivate previous versions
            self.db.query(PrivacyPolicyVersion).update({"is_active": False})
            
            policy_version = PrivacyPolicyVersion(
                version=version,
                effective_date=effective_date,
                content_hash=content_hash,
                major_changes=major_changes or [],
                requires_new_consent=requires_new_consent,
                is_active=True
            )
            
            self.db.add(policy_version)
            self.db.commit()
            
            # If new consent is required, notify all users
            if requires_new_consent:
                self._notify_users_of_policy_change(policy_version)
            
            logger.info(f"Privacy policy version {version} created")
            return policy_version
            
        except Exception as e:
            logger.error(f"Error creating privacy policy version: {str(e)}")
            self.db.rollback()
            raise
    
    # Utility Methods
    def _gather_user_data(self, user_id: int, data_categories: List[str]) -> Dict[str, Any]:
        """Gather user data for export"""
        user_data = {}
        
        # Get user profile data
        if "profile" in data_categories or "all" in data_categories:
            user = self.db.query(User).filter(User.id == user_id).first()
            if user:
                user_data["profile"] = {
                    "email": user.email,
                    "full_name": user.full_name,
                    "avatar_url": user.avatar_url,
                    "created_at": user.created_at.isoformat() if user.created_at else None,
                    "last_login": user.last_login.isoformat() if user.last_login else None,
                    "is_verified": user.is_verified
                }
        
        # Get subscription data
        if "subscription" in data_categories or "all" in data_categories:
            subscription = self.db.query(Subscription).filter(Subscription.user_id == user_id).first()
            if subscription:
                user_data["subscription"] = {
                    "tier": subscription.tier.value,
                    "status": subscription.status.value,
                    "current_period_start": subscription.current_period_start.isoformat() if subscription.current_period_start else None,
                    "current_period_end": subscription.current_period_end.isoformat() if subscription.current_period_end else None
                }
        
        # Get usage data
        if "usage" in data_categories or "all" in data_categories:
            usage_records = self.db.query(UsageRecord).filter(UsageRecord.user_id == user_id).all()
            user_data["usage"] = [
                {
                    "date": record.record_date.isoformat(),
                    "minutes_used": record.minutes_used,
                    "operation_type": record.operation_type,
                    "metadata": record.metadata
                }
                for record in usage_records
            ]
        
        # Get payment data
        if "payments" in data_categories or "all" in data_categories:
            payments = self.db.query(PaymentHistory).filter(PaymentHistory.user_id == user_id).all()
            user_data["payments"] = [
                {
                    "date": payment.payment_date.isoformat(),
                    "amount": float(payment.amount),
                    "currency": payment.currency,
                    "status": payment.status.value,
                    "description": payment.description
                }
                for payment in payments
            ]
        
        # Get consent data
        if "consents" in data_categories or "all" in data_categories:
            consents = self.db.query(UserConsent).filter(UserConsent.user_id == user_id).all()
            user_data["consents"] = [
                {
                    "consent_type": consent.consent_type.value,
                    "consent_given": consent.consent_given,
                    "consent_date": consent.consent_date.isoformat(),
                    "consent_version": consent.consent_version
                }
                for consent in consents
            ]
        
        return user_data
    
    def _generate_export_file(self, request: DataExportRequest, user_data: Dict[str, Any]) -> str:
        """Generate export file in requested format"""
        # Create export directory if it doesn't exist
        export_dir = Path("exports")
        export_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"user_{request.user_id}_export_{timestamp}.{request.export_format}"
        file_path = export_dir / filename
        
        if request.export_format == "json":
            with open(file_path, "w") as f:
                json.dump(user_data, f, indent=2, default=str)
        elif request.export_format == "csv":
            # For CSV, we'll flatten the data structure
            import pandas as pd
            flattened_data = self._flatten_data_for_csv(user_data)
            df = pd.DataFrame(flattened_data)
            df.to_csv(file_path, index=False)
        else:
            raise ValueError(f"Unsupported export format: {request.export_format}")
        
        return str(file_path)
    
    def _flatten_data_for_csv(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Flatten nested data structure for CSV export"""
        flattened = []
        
        for category, category_data in data.items():
            if isinstance(category_data, dict):
                row = {"category": category}
                row.update(category_data)
                flattened.append(row)
            elif isinstance(category_data, list):
                for item in category_data:
                    row = {"category": category}
                    if isinstance(item, dict):
                        row.update(item)
                    else:
                        row["value"] = str(item)
                    flattened.append(row)
        
        return flattened
    
    def _execute_data_deletion(self, request: DataDeletionRequest):
        """Execute actual data deletion"""
        user_id = request.user_id
        
        # Delete or anonymize data based on request
        for category in request.data_categories:
            if category == "usage_data":
                # Anonymize usage data (keep for analytics but remove personal identifiers)
                self.db.query(UsageRecord).filter(UsageRecord.user_id == user_id).update({
                    "user_id": None  # Anonymize
                })
            elif category == "payment_data":
                # Keep payment data for legal/tax requirements but anonymize
                self.db.query(PaymentHistory).filter(PaymentHistory.user_id == user_id).update({
                    "user_id": None  # Anonymize
                })
            elif category == "profile_data":
                # Delete profile data
                user = self.db.query(User).filter(User.id == user_id).first()
                if user:
                    user.email = f"deleted_{user_id}@example.com"
                    user.full_name = "Deleted User"
                    user.avatar_url = None
                    user.is_active = False
            # Add more deletion logic for other categories
    
    def _create_audit_log(self, user_id: int, action: str, details: str):
        """Create audit log entry"""
        audit_log = AuditLog(
            user_id=user_id,
            action=action,
            details=details,
            ip_address="system"  # System-generated action
        )
        self.db.add(audit_log)
    
    def _notify_users_of_policy_change(self, policy_version: PrivacyPolicyVersion):
        """Notify all users of privacy policy changes"""
        # This would typically be done in a background task
        # For now, we'll just log the requirement
        logger.info(f"Privacy policy {policy_version.version} requires user notification")
        # TODO: Implement mass email notification system