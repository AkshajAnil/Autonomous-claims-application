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
    ml_probability: float,
    shap_explanations: list,
    fallback_reason: str | None = None,
    verifications: dict | None = None,
    image_anomaly_score: float = 0.0,
    ocr_consistency_score: float = 1.0,
    evidence: dict | None = None,
    verification_status: dict | None = None,
    universal_features: dict | None = None,
    domain_features: dict | None = None,
    risk_result: dict | None = None,
    evidence_confidence: int = 100,
    decision_result: dict | None = None
) -> None:
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        return

    # Map AI decision fields (Serializing dict/list objects to JSON strings for Text columns)
    claim.fraud_risk_score = decision_payload.get("fraud_risk_score")
    claim.routing_decision = decision_payload.get("routing_decision")
    claim.decision_reason = decision_result.get("decision_reason", decision_payload.get("decision_reason")) if decision_result else decision_payload.get("decision_reason")
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

    # Persistent Adjudication Outputs
    risk_score = risk_result["risk_score"] if risk_result else decision_payload.get("fraud_risk_score", 50)
    claim.risk_score = risk_score
    claim.fraud_probability = ml_probability
    claim.processing_timestamp = datetime.utcnow()
    
    if claim.created_at:
        claim.processing_duration_ms = int((claim.processing_timestamp - claim.created_at).total_seconds() * 1000)
        
    # Save verification statuses & metadata JSON
    v_data = verifications or {}
    claim.location_verification_status = v_data.get("location", {}).get("status", "NOT_REQUIRED")
    claim.weather_verification_status = v_data.get("weather", {}).get("status", "NOT_REQUIRED")
    claim.disaster_verification_status = v_data.get("disaster", {}).get("status", "NOT_REQUIRED")
    claim.event_verification_status = v_data.get("event", {}).get("status", "NOT_REQUIRED")
    
    # Store complete v4.0 Universal Risk Engine metadata payload
    metadata_payload = {
        "verifications": v_data,
        "evidence": evidence or {},
        "verification_status": verification_status or {},
        "universal_features": universal_features or {},
        "domain_features": domain_features or {},
        "risk_result": risk_result or {},
        "triggered_rules": risk_result.get("triggered_rules", []) if risk_result else [],
        "positive_rules": risk_result.get("positive_rules", []) if risk_result else [],
        "negative_rules": risk_result.get("negative_rules", []) if risk_result else [],
        "risk_score": risk_score,
        "evidence_confidence": evidence_confidence,
        "decision_result": decision_result or {},
        "decision": decision_result.get("decision", "MANUAL_REVIEW") if decision_result else "MANUAL_REVIEW",
        "reason_code": decision_result.get("reason_code", "NORMAL_EVALUATION") if decision_result else "NORMAL_EVALUATION",
        "decision_reason": decision_result.get("decision_reason", "") if decision_result else "",
        "next_actions": decision_result.get("next_actions", []) if decision_result else [],
        "top_positive": decision_result.get("top_positive", []) if decision_result else [],
        "top_negative": decision_result.get("top_negative", []) if decision_result else [],
        "workflow_version": "v1.0",
        "feature_schema_version": "v1.0",
        "risk_rules_version": "v1.0"
    }
    claim.verification_metadata = metadata_payload

    # Decision Engine Routing
    dec_tier = decision_result.get("decision") if decision_result else "MANUAL_REVIEW"
    if dec_tier == "STRAIGHT_THROUGH":
        claim.status = ClaimStatus.approved.value
        claim.decision = "Auto Approved (Straight-Through Processing)"
    elif dec_tier == "REJECT_FRAUD":
        claim.status = ClaimStatus.rejected.value
        claim.decision = "Rejected (High Fraud Risk Flagged)"
    else:
        claim.status = ClaimStatus.under_review.value
        claim.decision = decision_result.get("decision_label", "Under Review") if decision_result else "Under Review"

        # Workload-Balanced Auto Assignment (cap of 20 active claims per adjuster)
        from app.models import User
        adjusters = db.query(User).filter(User.role == "adjuster").all()
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
            claim.decision = f"Assigned to {best_adjuster.full_name} ({decision_result.get('decision_label', 'Review') if decision_result else 'Review'})"

    # Log to FeatureStore dataset
    from app.feature_store import FeatureStore
    FeatureStore().log_claim(
        claim_id=claim_id,
        evidence=evidence or {},
        verification_status=verification_status or {},
        universal_features=universal_features or {},
        domain_features=domain_features or {},
        triggered_rules=risk_result.get("triggered_rules", []) if risk_result else [],
        positive_rules=risk_result.get("positive_rules", []) if risk_result else [],
        negative_rules=risk_result.get("negative_rules", []) if risk_result else [],
        risk_score=risk_score,
        evidence_confidence=evidence_confidence,
        decision=decision_result.get("decision", "MANUAL_REVIEW") if decision_result else "MANUAL_REVIEW",
        reason_code=decision_result.get("reason_code", "NORMAL_EVALUATION") if decision_result else "NORMAL_EVALUATION",
        decision_reason=decision_result.get("decision_reason", "") if decision_result else "",
        next_actions=decision_result.get("next_actions", []) if decision_result else []
    )

    db.commit()
    db.refresh(claim)

    # Log audit event for decision
    log_audit(db, claim.user_id, "Claim Decision", {
        "claim_id": claim_id,
        "risk_score": risk_score,
        "decision": claim.decision,
        "status": claim.status
    })
