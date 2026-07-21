import os
import json
import datetime
from typing import Any, Dict
from app.config import FEATURE_SCHEMA_VERSION, RISK_RULES_VERSION, WORKFLOW_VERSION

class FeatureStore:
    """
    Appends full feature vector, domain features, evidence, verification status, and decision snapshots
    to app/artifacts/feature_store.json to build the historical training dataset for Phase 3 ML.
    """
    def __init__(self, store_path: str = "app/artifacts/feature_store.json"):
        self.store_path = store_path
        os.makedirs(os.path.dirname(self.store_path), exist_ok=True)

    def log_claim(
        self,
        claim_id: Any,
        evidence: Dict[str, Any],
        verification_status: Dict[str, Any],
        universal_features: Dict[str, Any],
        domain_features: Dict[str, Any],
        triggered_rules: list,
        positive_rules: list,
        negative_rules: list,
        risk_score: int,
        evidence_confidence: int,
        decision: str,
        reason_code: str,
        decision_reason: str = "",
        next_actions: list = None
    ) -> Dict[str, Any]:
        cid_str = str(claim_id) if str(claim_id).startswith("CLM-") else f"CLM-{claim_id}"
        record = {
            "claim_id": cid_str,
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "workflow_version": WORKFLOW_VERSION,
            "feature_schema_version": FEATURE_SCHEMA_VERSION,
            "risk_rules_version": RISK_RULES_VERSION,
            "evidence": evidence,
            "verification_status": verification_status,
            "universal_features": universal_features,
            "domain_features": domain_features or {},
            "triggered_rules": triggered_rules,
            "positive_rules": positive_rules,
            "negative_rules": negative_rules,
            "risk_score": risk_score,
            "evidence_confidence": evidence_confidence,
            "decision": decision,
            "reason_code": reason_code,
            "decision_reason": decision_reason,
            "next_actions": next_actions or [],
            "reviewer_notes": None,
            "claim_outcome": None,
            "fraud_confirmed": None
        }

        # Append to local JSON Feature Store dataset
        try:
            records = []
            if os.path.exists(self.store_path):
                with open(self.store_path, "r", encoding="utf-8") as f:
                    records = json.load(f)
                    if not isinstance(records, list):
                        records = []
            
            # Avoid duplicate claim_id entries if re-processed
            records = [r for r in records if r.get("claim_id") != record["claim_id"]]
            records.append(record)

            with open(self.store_path, "w", encoding="utf-8") as f:
                json.dump(records, f, indent=2)
        except Exception as e:
            print(f"FeatureStore log error: {e}")

        return record
