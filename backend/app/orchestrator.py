import asyncio
import datetime
from typing import Any, Dict
from sqlalchemy.orm import Session

from app.models import Claim
from app.workflow_planner import WorkflowPlanner
from app.agent import run_claim_agent
from app.evidence_collector import EvidenceCollector
from app.verification_status import VerificationStatusManager
from app.feature_extractor import UniversalFeatureExtractor
from app.domain_features import DomainFeatureExtractor
from app.fraud_predictor import RuleBasedFraudPredictor
from app.evidence_confidence import EvidenceConfidenceCalculator
from app.decision_engine import DecisionEngine
from app.repository import apply_decision, update_claim_status

class ClaimOrchestrator:
    """
    Central claim processing coordinator for Universal AI Claims Platform v4.1.
    Manages complete claim lifecycle states:
    RECEIVED -> DOMAIN_IDENTIFIED -> WORKFLOW_PLANNED -> COLLECTING_EVIDENCE ->
    FEATURE_EXTRACTION -> RISK_EVALUATION -> DECISION_GENERATED -> COMPLETED (or FAILED)
    """
    def process_claim(self, db: Session, claim_id: str) -> Claim:
        claim = db.query(Claim).filter(Claim.id == claim_id).first()
        if not claim:
            raise ValueError(f"Claim {claim_id} not found")

        # Step 1: RECEIVED -> PROCESSING
        update_claim_status(db, claim_id, "PROCESSING")
        
        try:
            # Step 2: DOMAIN_IDENTIFIED & WORKFLOW_PLANNED
            planner = WorkflowPlanner()
            wf_plan = planner.plan(claim.claim_type or "", claim.description or "")
            
            # Step 3: COLLECTING_EVIDENCE (LangChain Agent + MCP Tools Execution)
            agent_result = asyncio.run(run_claim_agent(lambda: db, claim_id)) if asyncio.iscoroutinefunction(run_claim_agent) else run_claim_agent(lambda: db, claim_id)
            
            # Extract collected evidence outputs
            visual_findings = agent_result.get("visual_findings") or {}
            external_verif = agent_result.get("external_verification") or {}
            policy_matches = agent_result.get("policy_matches") or []
            final_decision_payload = agent_result.get("final_decision_payload") or {}

            collector = EvidenceCollector()
            collector.add_gemini_analysis(visual_findings if isinstance(visual_findings, dict) else {})
            collector.add_weather_verification(external_verif.get("weather_verification") or {})
            collector.add_location_verification(external_verif.get("location_verification") or {})
            collector.add_disaster_verification(external_verif.get("disaster_verification") or {})
            collector.add_news_verification(external_verif.get("event_verification") or {})
            collector.add_policy_rag(policy_matches)

            v_manager = VerificationStatusManager()
            if external_verif.get("weather_verification", {}).get("available"):
                v_manager.set_status("weather", "SUCCESS" if external_verif["weather_verification"].get("weather_verified") else "FAILED")
            if external_verif.get("location_verification"):
                v_manager.set_status("location", "SUCCESS" if external_verif["location_verification"].get("valid") else "FAILED")
            if external_verif.get("disaster_verification", {}).get("available"):
                v_manager.set_status("gdacs", "SUCCESS" if external_verif["disaster_verification"].get("disaster_verified") else "NO_MATCH")
            if external_verif.get("event_verification", {}).get("available"):
                v_manager.set_status("news", "SUCCESS" if external_verif["event_verification"].get("event_verified") else "NO_MATCH")
            v_manager.set_status("gemini_vision", "SUCCESS" if visual_findings else "FAILED")
            v_manager.set_status("ocr", "SUCCESS" if visual_findings else "FAILED")

            evidence_dict = collector.to_dict()
            status_dict = v_manager.to_dict()

            # Step 4: FEATURE_EXTRACTION (Universal & Domain Features)
            extractor = UniversalFeatureExtractor()
            univ_features = extractor.extract(claim, evidence_dict, status_dict)

            dom_extractor = DomainFeatureExtractor()
            dom_features = dom_extractor.extract(claim, wf_plan["domain"], wf_plan["category"], evidence_dict)

            # Step 5: RISK_EVALUATION (Universal Risk Engine)
            predictor = RuleBasedFraudPredictor()
            risk_res = predictor.predict(univ_features)

            conf_calc = EvidenceConfidenceCalculator()
            evid_conf = conf_calc.calculate(univ_features, status_dict)

            # Step 6: DECISION_GENERATED
            dec_engine = DecisionEngine()
            dec_res = dec_engine.evaluate(risk_res["risk_score"], evid_conf, risk_res["triggered_rules"], claim=claim)

            final_decision_payload["summary"] = dec_res.get("decision_reason", final_decision_payload.get("summary"))
            final_decision_payload["decision_reason"] = dec_res.get("decision_reason", final_decision_payload.get("decision_reason"))

            # Step 7: COMPLETED (Persist to Database & Feature Store)
            apply_decision(
                db,
                claim_id,
                final_decision_payload,
                float(risk_res["risk_score"]) / 100.0,
                dec_res.get("top_positive", []) + dec_res.get("top_negative", []),
                fallback_reason=None,
                verifications=agent_result.get("verifications_payload"),
                image_anomaly_score=0.1,
                ocr_consistency_score=0.95,
                evidence=evidence_dict,
                verification_status=status_dict,
                universal_features=univ_features,
                domain_features=dom_features,
                risk_result=risk_res,
                evidence_confidence=evid_conf,
                decision_result=dec_res
            )

        except Exception as e:
            update_claim_status(db, claim_id, "FAILED")
            raise e

        return claim
