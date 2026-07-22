from datetime import datetime
import json
from typing import Any
from pydantic import BaseModel, field_validator


class EvidenceOut(BaseModel):
    id: str
    filename: str
    url: str
    content_type: str

    model_config = {"from_attributes": True}


class AgentEventOut(BaseModel):
    id: str
    step: str
    message: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class UserOut(BaseModel):
    id: str
    username: str
    customer_id: str
    role: str
    full_name: str
    is_identity_verified: bool
    is_active: bool
    must_change_password: bool
    email: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ClaimOut(BaseModel):
    id: str
    claimant_name: str
    claim_type: str
    policy_number: str
    amount_requested: float
    description: str
    status: str
    
    # New Incident Fields
    incident_date: datetime | None = None
    incident_location: str | None = None
    
    # AI Outputs
    summary: str | None = None
    extracted_info: dict | None = None
    fraud_risk_score: float | None = None
    routing_decision: str | None = None
    decision_reason: str | None = None
    confidence_score: float | None = None
    missing_documents: list[str] | None = None
    fraud_indicators: list[str] | None = None
    recommended_action: str | None = None
    verification_report: dict | None = None

    # Persistent Adjudication Outputs
    risk_score: float | None = None
    fraud_probability: float | None = None
    decision: str | None = None
    investigation_summary: str | None = None
    shap_explanations: dict | list | None = None
    processing_timestamp: datetime | None = None
    
    # Verification Statuses & Metadata
    location_verification_status: str | None = None
    weather_verification_status: str | None = None
    disaster_verification_status: str | None = None
    event_verification_status: str | None = None
    verification_metadata: dict | list | None = None
    
    # Universal Risk Engine v4.0 Fields
    evidence_confidence: float | None = None
    reason_code: str | None = None
    triggered_rules: list | None = None
    top_positive: list | None = None
    top_negative: list | None = None
    next_actions: list | None = None
    universal_features: dict | None = None
    domain_features: dict | None = None
    raw_evidence: dict | None = None
    workflow_version: str | None = None
    
    # Debugging / Audit / Tracking
    fallback_reason: str | None = None
    decision_reason: str | None = None
    investigation_version: str | None = None
    processing_duration_ms: int | None = None
    
    # Adjuster Notes and Assignee
    adjuster_notes: str | None = None
    assigned_adjuster_id: str | None = None
    
    # Manual Review Override Metadata
    reviewed_by_id: str | None = None
    reviewed_at: datetime | None = None
    reviewer_notes: str | None = None
    reviewed_by_user: UserOut | None = None

    user_id: str | None
    created_at: datetime
    evidence: list[EvidenceOut]
    events: list[AgentEventOut]
    
    user: UserOut | None = None

    model_config = {"from_attributes": True}

    @field_validator("extracted_info", "verification_report", mode="before")
    @classmethod
    def parse_extracted_info(cls, v: Any):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return {}
        return v

    @field_validator("missing_documents", "fraud_indicators", mode="before")
    @classmethod
    def parse_lists(cls, v: Any):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return []
        return v


class AgentDecision(BaseModel):
    fraud_risk_score: float
    routing_decision: str
    decision_reason: str
    summary: str | None = None
    extracted_info: dict | None = None
    confidence_score: float | None = None
    missing_documents: list[str] | None = None
    fraud_indicators: list[str] | None = None
    recommended_action: str | None = None
    verification_report: dict | None = None


class UserCreate(BaseModel):
    username: str
    password: str


class PredictRequest(BaseModel):
    customer_tenure: float | None = None
    policy_age: float | None = None
    previous_claims: int | None = None
    policy_type: str | None = None
    insurance_type: str | None = None
    claim_amount: float | None = None
    claim_submission_delay: int | None = None
    incident_location: str | None = None
    incident_date: str | None = None
    weather_verified: bool | None = None
    location_verified: bool | None = None
    disaster_verified: bool | None = None
    image_anomaly_score: float | None = None
    ocr_consistency_score: float | None = None
    missing_document_count: int | None = None


class ShapExplanation(BaseModel):
    feature: str
    impact: float


class PredictResponse(BaseModel):
    fraud_probability: float
    risk_score: int
    recommendation: str
    shap_explanations: list[ShapExplanation]


class AuditLogOut(BaseModel):
    id: str
    user_id: str | None
    action: str
    details: str
    created_at: datetime
    user: UserOut | None = None

    model_config = {"from_attributes": True}


class AdjudicationRequest(BaseModel):
    action: str
    notes: str | None = None


class EmployeeCreate(BaseModel):
    full_name: str
    email: str
    role: str
    temporary_password: str


class PasswordChangeRequest(BaseModel):
    new_password: str


class SelfResetPasswordRequest(BaseModel):
    username: str
    customer_id: str
    new_password: str
