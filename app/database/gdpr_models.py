"""
GDPR Compliance Models for data privacy and user consent management
"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSON
from datetime import datetime
import enum

from app.database.base import Base


class ConsentType(str, enum.Enum):
    """Types of consent that can be given by users"""
    ESSENTIAL = "essential"  # Required for service functionality
    ANALYTICS = "analytics"  # For usage analytics and improvements
    MARKETING = "marketing"  # For marketing communications
    THIRD_PARTY = "third_party"  # For third-party integrations
    COOKIES = "cookies"  # For non-essential cookies


class DataProcessingPurpose(str, enum.Enum):
    """Purposes for which personal data is processed"""
    SERVICE_PROVISION = "service_provision"
    ACCOUNT_MANAGEMENT = "account_management"
    PAYMENT_PROCESSING = "payment_processing"
    COMMUNICATION = "communication"
    ANALYTICS = "analytics"
    MARKETING = "marketing"
    LEGAL_COMPLIANCE = "legal_compliance"
    SECURITY = "security"


class DataRetentionStatus(str, enum.Enum):
    """Status of data retention"""
    ACTIVE = "active"
    SCHEDULED_DELETION = "scheduled_deletion"
    DELETED = "deleted"
    ANONYMIZED = "anonymized"


class UserConsent(Base):
    """Track user consent for different types of data processing"""
    __tablename__ = "user_consents"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    consent_type = Column(SQLEnum(ConsentType), nullable=False)
    consent_given = Column(Boolean, nullable=False, default=False)
    consent_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    consent_withdrawn_date = Column(DateTime, nullable=True)
    ip_address = Column(String(45), nullable=True)  # For legal proof
    user_agent = Column(Text, nullable=True)
    consent_version = Column(String(10), nullable=False, default="1.0")
    
    # Relationships
    user = relationship("User", back_populates="consents")
    
    def __repr__(self):
        return f"<UserConsent(user_id={self.user_id}, type={self.consent_type}, given={self.consent_given})>"


class DataProcessingRecord(Base):
    """Track all data processing activities for GDPR compliance"""
    __tablename__ = "data_processing_records"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    purpose = Column(SQLEnum(DataProcessingPurpose), nullable=False)
    data_categories = Column(JSON, nullable=False)  # List of data types processed
    processing_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    legal_basis = Column(String(100), nullable=False)  # GDPR legal basis
    retention_period = Column(Integer, nullable=True)  # Days
    third_parties = Column(JSON, nullable=True)  # List of third parties data shared with
    automated_decision_making = Column(Boolean, default=False)
    
    # Relationships
    user = relationship("User", back_populates="processing_records")
    
    def __repr__(self):
        return f"<DataProcessingRecord(user_id={self.user_id}, purpose={self.purpose})>"


class DataExportRequest(Base):
    """Track data export requests (Right to Data Portability)"""
    __tablename__ = "data_export_requests"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    request_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_date = Column(DateTime, nullable=True)
    export_format = Column(String(20), nullable=False, default="json")  # json, csv, xml
    data_categories = Column(JSON, nullable=False)  # What data to export
    status = Column(String(20), nullable=False, default="pending")  # pending, processing, completed, failed
    file_path = Column(String(500), nullable=True)  # Path to generated export file
    download_expires = Column(DateTime, nullable=True)  # When download link expires
    ip_address = Column(String(45), nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="export_requests")
    
    def __repr__(self):
        return f"<DataExportRequest(user_id={self.user_id}, status={self.status})>"


class DataDeletionRequest(Base):
    """Track data deletion requests (Right to Erasure)"""
    __tablename__ = "data_deletion_requests"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    request_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    scheduled_deletion_date = Column(DateTime, nullable=True)
    completed_date = Column(DateTime, nullable=True)
    reason = Column(String(200), nullable=True)
    data_categories = Column(JSON, nullable=False)  # What data to delete
    status = Column(String(20), nullable=False, default="pending")  # pending, scheduled, processing, completed, cancelled
    retention_exceptions = Column(JSON, nullable=True)  # Data that cannot be deleted (legal reasons)
    confirmation_required = Column(Boolean, default=True)
    confirmation_date = Column(DateTime, nullable=True)
    ip_address = Column(String(45), nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="deletion_requests")
    
    def __repr__(self):
        return f"<DataDeletionRequest(user_id={self.user_id}, status={self.status})>"


class PrivacyPolicyVersion(Base):
    """Track privacy policy versions for consent management"""
    __tablename__ = "privacy_policy_versions"
    
    id = Column(Integer, primary_key=True, index=True)
    version = Column(String(10), nullable=False, unique=True)
    effective_date = Column(DateTime, nullable=False)
    content_hash = Column(String(64), nullable=False)  # SHA256 hash of policy content
    major_changes = Column(JSON, nullable=True)  # List of major changes
    requires_new_consent = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<PrivacyPolicyVersion(version={self.version}, active={self.is_active})>"


class DataBreachNotification(Base):
    """Track data breaches and notifications (GDPR Article 33-34)"""
    __tablename__ = "data_breach_notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    incident_date = Column(DateTime, nullable=False)
    discovery_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    notification_date = Column(DateTime, nullable=True)
    breach_type = Column(String(100), nullable=False)  # unauthorized_access, data_loss, etc.
    affected_data_categories = Column(JSON, nullable=False)
    affected_users_count = Column(Integer, nullable=False, default=0)
    severity_level = Column(String(20), nullable=False)  # low, medium, high, critical
    description = Column(Text, nullable=False)
    containment_measures = Column(Text, nullable=True)
    notification_required = Column(Boolean, default=True)
    authority_notified = Column(Boolean, default=False)
    users_notified = Column(Boolean, default=False)
    status = Column(String(20), nullable=False, default="investigating")
    
    def __repr__(self):
        return f"<DataBreachNotification(id={self.id}, severity={self.severity_level})>"


class CookieConsent(Base):
    """Track cookie consent for website visitors"""
    __tablename__ = "cookie_consents"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Null for anonymous users
    session_id = Column(String(100), nullable=True)  # For anonymous tracking
    essential_cookies = Column(Boolean, default=True)  # Always true
    functional_cookies = Column(Boolean, default=False)
    analytics_cookies = Column(Boolean, default=False)
    marketing_cookies = Column(Boolean, default=False)
    consent_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_date = Column(DateTime, nullable=False)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="cookie_consents")
    
    def __repr__(self):
        return f"<CookieConsent(user_id={self.user_id}, session_id={self.session_id})>"


class DataRetentionPolicy(Base):
    """Define data retention policies for different data types"""
    __tablename__ = "data_retention_policies"
    
    id = Column(Integer, primary_key=True, index=True)
    data_category = Column(String(100), nullable=False, unique=True)
    retention_period_days = Column(Integer, nullable=False)
    legal_basis = Column(String(200), nullable=False)
    automated_deletion = Column(Boolean, default=True)
    requires_user_confirmation = Column(Boolean, default=False)
    exceptions = Column(JSON, nullable=True)  # Conditions that extend retention
    is_active = Column(Boolean, default=True)
    created_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<DataRetentionPolicy(category={self.data_category}, days={self.retention_period_days})>"


class UserDataInventory(Base):
    """Inventory of personal data held for each user"""
    __tablename__ = "user_data_inventory"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    data_category = Column(String(100), nullable=False)
    data_location = Column(String(200), nullable=False)  # table.column or file path
    collection_date = Column(DateTime, nullable=False)
    last_updated = Column(DateTime, nullable=False, default=datetime.utcnow)
    retention_status = Column(SQLEnum(DataRetentionStatus), default=DataRetentionStatus.ACTIVE)
    scheduled_deletion_date = Column(DateTime, nullable=True)
    legal_basis = Column(String(100), nullable=False)
    is_sensitive = Column(Boolean, default=False)
    
    # Relationships
    user = relationship("User", back_populates="data_inventory")
    
    def __repr__(self):
        return f"<UserDataInventory(user_id={self.user_id}, category={self.data_category})>"