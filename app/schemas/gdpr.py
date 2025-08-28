"""
Pydantic schemas for GDPR operations
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

from app.database.gdpr_models import ConsentType, DataProcessingPurpose


# Consent Management Schemas
class ConsentRequest(BaseModel):
    consent_type: ConsentType
    consent_given: bool
    
    class Config:
        use_enum_values = True


class ConsentResponse(BaseModel):
    id: int
    consent_type: str
    consent_given: bool
    consent_date: datetime
    consent_withdrawn_date: Optional[datetime] = None
    consent_version: str
    
    class Config:
        from_attributes = True


class ConsentSummary(BaseModel):
    essential: bool = True  # Always required
    analytics: bool = False
    marketing: bool = False
    third_party: bool = False
    cookies: bool = False
    last_updated: datetime
    
    class Config:
        from_attributes = True


# Data Export Schemas
class DataExportRequest(BaseModel):
    data_categories: List[str] = Field(..., description="Categories of data to export")
    export_format: str = Field(default="json", description="Export format (json, csv, xml)")
    
    class Config:
        schema_extra = {
            "example": {
                "data_categories": ["profile", "usage", "payments", "consents"],
                "export_format": "json"
            }
        }


class DataExportResponse(BaseModel):
    id: int
    request_date: datetime
    status: str
    export_format: str
    data_categories: List[str]
    completed_date: Optional[datetime] = None
    download_expires: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class DataExportStatus(BaseModel):
    status: str
    message: str
    progress: Optional[int] = None
    estimated_completion: Optional[datetime] = None


# Data Deletion Schemas
class DataDeletionRequest(BaseModel):
    data_categories: List[str] = Field(..., description="Categories of data to delete")
    reason: Optional[str] = Field(None, description="Reason for deletion request")
    confirmation: bool = Field(..., description="Confirmation that user understands consequences")
    
    class Config:
        schema_extra = {
            "example": {
                "data_categories": ["profile", "usage", "all"],
                "reason": "No longer using the service",
                "confirmation": True
            }
        }


class DataDeletionResponse(BaseModel):
    id: int
    request_date: datetime
    status: str
    data_categories: List[str]
    scheduled_deletion_date: Optional[datetime] = None
    grace_period_ends: Optional[datetime] = None
    reason: Optional[str] = None
    
    class Config:
        from_attributes = True


# Privacy Dashboard Schemas
class PrivacyDashboard(BaseModel):
    user_id: int
    consents: ConsentSummary
    data_categories: List[str]
    retention_info: Dict[str, Any]
    active_export_requests: List[DataExportResponse]
    active_deletion_requests: List[DataDeletionResponse]
    privacy_policy_version: str
    last_policy_acceptance: Optional[datetime] = None


class DataCategoryInfo(BaseModel):
    category: str
    description: str
    data_types: List[str]
    legal_basis: str
    retention_period: Optional[int] = None  # Days
    can_be_exported: bool = True
    can_be_deleted: bool = True
    third_parties: Optional[List[str]] = None


class RetentionInfo(BaseModel):
    category: str
    retention_period_days: int
    legal_basis: str
    next_review_date: Optional[datetime] = None
    can_request_deletion: bool = True
    exceptions: Optional[List[str]] = None


# Cookie Consent Schemas
class CookieConsentRequest(BaseModel):
    essential_cookies: bool = True  # Always required
    functional_cookies: bool = False
    analytics_cookies: bool = False
    marketing_cookies: bool = False


class CookieConsentResponse(BaseModel):
    id: int
    essential_cookies: bool
    functional_cookies: bool
    analytics_cookies: bool
    marketing_cookies: bool
    consent_date: datetime
    expires_date: datetime
    
    class Config:
        from_attributes = True


# Data Processing Record Schemas
class DataProcessingRequest(BaseModel):
    purpose: DataProcessingPurpose
    data_categories: List[str]
    legal_basis: str
    retention_period: Optional[int] = None
    third_parties: Optional[List[str]] = None
    automated_decision_making: bool = False
    
    class Config:
        use_enum_values = True


class DataProcessingResponse(BaseModel):
    id: int
    purpose: str
    data_categories: List[str]
    processing_date: datetime
    legal_basis: str
    retention_period: Optional[int] = None
    third_parties: List[str]
    automated_decision_making: bool
    
    class Config:
        from_attributes = True


# Privacy Policy Schemas
class PrivacyPolicyResponse(BaseModel):
    version: str
    effective_date: datetime
    major_changes: List[str]
    requires_new_consent: bool
    is_active: bool


class PrivacyPolicyAcceptance(BaseModel):
    version: str
    acceptance_date: datetime
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


# Data Subject Rights Schemas
class DataSubjectRightsInfo(BaseModel):
    """Information about data subject rights under GDPR"""
    right_to_information: Dict[str, Any]
    right_of_access: Dict[str, Any]
    right_to_rectification: Dict[str, Any]
    right_to_erasure: Dict[str, Any]
    right_to_restrict_processing: Dict[str, Any]
    right_to_data_portability: Dict[str, Any]
    right_to_object: Dict[str, Any]
    right_not_to_be_subject_to_automated_decision_making: Dict[str, Any]


# Admin Schemas for GDPR Management
class GDPRAdminDashboard(BaseModel):
    total_users_with_consent: int
    pending_export_requests: int
    pending_deletion_requests: int
    overdue_deletion_requests: int
    privacy_policy_version: str
    users_requiring_new_consent: int
    data_breach_notifications: int
    retention_policy_compliance: Dict[str, Any]


class DataBreachNotificationRequest(BaseModel):
    incident_date: datetime
    discovery_date: datetime
    breach_type: str
    affected_data_categories: List[str]
    affected_users_count: int
    severity_level: str  # low, medium, high, critical
    description: str
    containment_measures: Optional[str] = None


class DataBreachNotificationResponse(BaseModel):
    id: int
    incident_date: datetime
    discovery_date: datetime
    notification_date: Optional[datetime] = None
    breach_type: str
    affected_data_categories: List[str]
    affected_users_count: int
    severity_level: str
    description: str
    containment_measures: Optional[str] = None
    authority_notified: bool
    users_notified: bool
    status: str
    
    class Config:
        from_attributes = True


# User Data Inventory Schemas
class DataInventoryItem(BaseModel):
    data_category: str
    data_location: str
    collection_date: datetime
    last_updated: datetime
    retention_status: str
    scheduled_deletion_date: Optional[datetime] = None
    legal_basis: str
    is_sensitive: bool
    
    class Config:
        from_attributes = True


class UserDataInventoryResponse(BaseModel):
    user_id: int
    total_data_categories: int
    data_items: List[DataInventoryItem]
    last_inventory_update: datetime
    compliance_status: str  # compliant, needs_review, overdue


# Audit and Compliance Schemas
class GDPRComplianceReport(BaseModel):
    report_date: datetime
    total_users: int
    users_with_valid_consent: int
    consent_compliance_rate: float
    pending_data_requests: int
    overdue_requests: int
    retention_compliance_rate: float
    privacy_policy_acceptance_rate: float
    recommendations: List[str]


class GDPRAuditLog(BaseModel):
    id: int
    user_id: int
    action: str
    details: str
    timestamp: datetime
    ip_address: Optional[str] = None
    
    class Config:
        from_attributes = True


# Validation and Error Schemas
class GDPRError(BaseModel):
    error_code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    suggestions: Optional[List[str]] = None


class GDPRValidation(BaseModel):
    is_valid: bool
    errors: List[GDPRError]
    warnings: List[str]
    compliance_score: float  # 0.0 to 1.0