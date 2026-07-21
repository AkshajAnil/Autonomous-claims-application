from datetime import datetime
from enum import Enum
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text, JSON, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class VerificationStatus(str, Enum):
    passed = "PASSED"
    failed = "FAILED"
    not_required = "NOT_REQUIRED"
    unknown = "UNKNOWN"


class ClaimStatus(str, Enum):
    submitted = "SUBMITTED"
    processing = "PROCESSING"
    ai_completed = "AI_COMPLETED"
    under_review = "UNDER_REVIEW"
    approved = "APPROVED"
    rejected = "REJECTED"
    closed = "CLOSED"


class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    claimant_name: Mapped[str] = mapped_column(String(160))
    claim_type: Mapped[str] = mapped_column(String(120))
    policy_number: Mapped[str] = mapped_column(String(80))
    amount_requested: Mapped[float] = mapped_column(Float)
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), default=ClaimStatus.submitted.value)
    
    # New Incident Fields
    incident_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    incident_location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # AI/ML Outputs
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_info: Mapped[str | None] = mapped_column(Text, nullable=True)  # Store as JSON string
    fraud_risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    routing_decision: Mapped[str | None] = mapped_column(String(80), nullable=True)
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    missing_documents: Mapped[str | None] = mapped_column(Text, nullable=True)  # Store as JSON string
    fraud_indicators: Mapped[str | None] = mapped_column(Text, nullable=True)  # Store as JSON string
    recommended_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    verification_report: Mapped[str | None] = mapped_column(Text, nullable=True)  # Store as JSON string
    
    # Persistent Adjudication Outputs
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    fraud_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    decision: Mapped[str | None] = mapped_column(String(80), nullable=True)
    investigation_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    shap_explanations: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    processing_timestamp: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    
    # Verification Statuses & Metadata JSON
    location_verification_status: Mapped[str] = mapped_column(String(40), default=VerificationStatus.not_required.value)
    weather_verification_status: Mapped[str] = mapped_column(String(40), default=VerificationStatus.not_required.value)
    disaster_verification_status: Mapped[str] = mapped_column(String(40), default=VerificationStatus.not_required.value)
    event_verification_status: Mapped[str] = mapped_column(String(40), default=VerificationStatus.not_required.value)
    
    verification_metadata: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    
    # Debugging/Audit/Pipeline Tracking
    fallback_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    investigation_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    processing_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Adjuster Notes and Assignee
    adjuster_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    assigned_adjuster_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    
    # Manual Review/Override Metadata
    reviewed_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reviewer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="claims", foreign_keys=[user_id])
    assigned_adjuster: Mapped["User"] = relationship(foreign_keys=[assigned_adjuster_id])
    reviewed_by_user: Mapped["User | None"] = relationship(foreign_keys=[reviewed_by_id])
    
    evidence: Mapped[list["Evidence"]] = relationship(back_populates="claim", cascade="all, delete-orphan")
    events: Mapped[list["AgentEvent"]] = relationship(back_populates="claim", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    username: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(260))
    customer_id: Mapped[str] = mapped_column(String(40), unique=True, index=True, nullable=False)
    role: Mapped[str] = mapped_column(String(40), default="customer")
    full_name: Mapped[str] = mapped_column(String(160), default="")
    id_card_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_identity_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Enterprise Account Management Fields
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    email: Mapped[str | None] = mapped_column(String(160), unique=True, index=True, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    claims: Mapped[list[Claim]] = relationship(
        back_populates="user", 
        cascade="all, delete-orphan", 
        foreign_keys=[Claim.user_id]
    )


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.id"))
    filename: Mapped[str] = mapped_column(String(260))
    object_name: Mapped[str] = mapped_column(String(320))
    url: Mapped[str] = mapped_column(Text)
    content_type: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    claim: Mapped[Claim] = relationship(back_populates="evidence")


class AgentEvent(Base):
    __tablename__ = "agent_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.id"))
    step: Mapped[str] = mapped_column(String(80))
    message: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), default="running")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    claim: Mapped[Claim] = relationship(back_populates="events")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(100))
    details: Mapped[str] = mapped_column(Text)  # JSON string
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User | None"] = relationship()
