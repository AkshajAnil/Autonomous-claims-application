from sqlalchemy.orm import Session, selectinload
from datetime import datetime
import json

from app.models import AgentEvent, Claim, ClaimStatus, AuditLog, User
from app.schemas import AgentDecision


def claim_with_children(db: Session, claim_id: str) -> Claim | None:
    return (
        db.query(Claim)
        .options(
            selectinload(Claim.evidence), 
            selectinload(Claim.events), 
            selectinload(Claim.user),
            selectinload(Claim.assigned_adjuster),
            selectinload(Claim.reviewed_by_user)
        )
        .filter(Claim.id == claim_id)
        .first()
    )

def add_event(db: Session, claim_id: str, step: str, message: str, status: str = "done") -> AgentEvent:
    event = AgentEvent(claim_id=claim_id, step=step, message=message, status=status)
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def log_audit(db: Session, user_id: str | None, action: str, details: dict) -> AuditLog:
    log_entry = AuditLog(
        user_id=user_id,
        action=action,
        details=json.dumps(details)
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)
    return log_entry


def mark_processing(db: Session, claim_id: str) -> None:
    claim = db.get(Claim, claim_id)
    if claim:
        claim.status = ClaimStatus.processing.value
        db.commit()


def apply_decision(
    db: Session,
    claim_id: str,
    decision_payload: dict,
    fallback_reason: str | None = None,
    verifications: dict | None = None,
    evidence: dict | None = None,
) -> None:
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        return

    # Map AI decision fields (Serializing dict/list objects to JSON strings for Text columns)
    claim.fraud_risk_score = decision_payload.get("fraud_risk_score")
    claim.routing_decision = decision_payload.get("routing_decision")
    claim.decision_reason = decision_payload.get("decision_reason")
    claim.summary = decision_payload.get("summary")
    
    extracted = decision_payload.get("extracted_info")
    claim.extracted_info = json.dumps(extracted) if isinstance(extracted, (dict, list)) else extracted

    claim.confidence_score = decision_payload.get("confidence_score")

    missing_docs = decision_payload.get("missing_documents")
    claim.missing_documents = json.dumps(missing_docs) if isinstance(missing_docs, (dict, list)) else missing_docs

    fraud_ind = decision_payload.get("fraud_indicators")
    claim.fraud_indicators = json.dumps(fraud_ind) if isinstance(fraud_ind, (dict, list)) else fraud_ind

    claim.recommended_action = decision_payload.get("recommended_action")

    verif_rep = decision_payload.get("verification_report")
    claim.verification_report = json.dumps(verif_rep) if isinstance(verif_rep, (dict, list)) else verif_rep

    # Persistent agentic adjudication outputs
    claim.risk_score = decision_payload.get("fraud_risk_score")
    claim.fraud_probability = None
    claim.processing_timestamp = datetime.utcnow()
    
    if claim.created_at:
        claim.processing_duration_ms = int((claim.processing_timestamp - claim.created_at).total_seconds() * 1000)
        
    # Save verification statuses & metadata JSON
    v_data = verifications or {}
    claim.location_verification_status = v_data.get("location", {}).get("status", "NOT_REQUIRED")
    claim.weather_verification_status = v_data.get("weather", {}).get("status", "NOT_REQUIRED")
    claim.disaster_verification_status = v_data.get("disaster", {}).get("status", "NOT_REQUIRED")
    claim.event_verification_status = v_data.get("event", {}).get("status", "NOT_REQUIRED")
    
    # Store complete agentic workflow metadata payload
    metadata_payload = {
        "verifications": v_data,
        "evidence": evidence or {},
        "routing_decision": decision_payload.get("routing_decision"),
        "decision_reason": decision_payload.get("decision_reason", ""),
        "next_actions": decision_payload.get("next_actions", []),
        "workflow_version": "agentic-v1.0",
    }
    claim.verification_metadata = metadata_payload

    routing = (decision_payload.get("routing_decision") or "").lower()
    if routing in {"auto_approve", "straight_through", "approve"}:
        claim.status = ClaimStatus.approved.value
        claim.decision = "Auto Approved (Agentic Workflow)"
    elif routing in {"reject", "reject_fraud"}:
        claim.status = ClaimStatus.rejected.value
        claim.decision = "Rejected (Agentic Workflow)"
    else:
        claim.status = ClaimStatus.under_review.value
        claim.decision = "Under Review (Agentic Workflow)"

        # Workload-Balanced Auto Assignment (cap of 20 active claims per adjuster)
        from app.models import User
        adjusters = db.query(User).filter(User.role.contains("adjuster"), User.is_active == True).all()
        best_adjuster = None
        min_load = 21
        
        for adj in adjusters:
            active_claims_count = db.query(Claim).filter(
                Claim.assigned_adjuster_id == adj.id,
                Claim.status == ClaimStatus.under_review.value
            ).count()
            
            if active_claims_count < 20 and active_claims_count < min_load:
                min_load = active_claims_count
                best_adjuster = adj
                
        if best_adjuster:
            claim.assigned_adjuster_id = best_adjuster.id
            claim.decision = f"Assigned to {best_adjuster.full_name} (Agentic Review)"

    db.commit()
    db.refresh(claim)

    # Log audit event for decision
    log_audit(db, claim.user_id, "Claim Decision", {
        "claim_id": claim_id,
        "routing_decision": decision_payload.get("routing_decision"),
        "decision": claim.decision,
        "status": claim.status
    })
