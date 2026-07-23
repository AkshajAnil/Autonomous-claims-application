from typing import Any, Dict, List

class DecisionEngine:
    """
    Decoupled Decision Engine mapping Trust & Safety Score and Rule Trigger outputs to:
    - 5 Decision Tiers: STRAIGHT_THROUGH, FAST_REVIEW, MANUAL_REVIEW, HIGH_RISK_INVESTIGATION, REJECT_FRAUD
    - Standardized Reason Codes & Jargon-Free, Plain English Decision Reasons
    - Actionable Next Actions Checklist
    - Top Positive and Top Negative rule summaries
    """
    def evaluate(self, risk_score: int, evidence_confidence: int, triggered_rules: List[Dict[str, Any]], claim: Any = None) -> Dict[str, Any]:
        # Determine Decision Tier based on Trust & Safety Score (100 = Highest Safety/Trust)
        if risk_score >= 85:
            decision = "STRAIGHT_THROUGH"
            decision_label = "Straight Through Processing (Auto Approve)"
        elif risk_score >= 70:
            decision = "FAST_REVIEW"
            decision_label = "Low Risk – Fast Review"
        elif risk_score >= 50:
            decision = "MANUAL_REVIEW"
            decision_label = "Manual Review"
        elif risk_score >= 30:
            decision = "HIGH_RISK_INVESTIGATION"
            decision_label = "High Risk Investigation"
        else:
            decision = "REJECT_FRAUD"
            decision_label = "Reject / Fraud Investigation"

        # Determine Reason Code
        reason_code = "NORMAL_EVALUATION"
        reason_desc = "Claim evaluated according to standard risk rules."

        negative_rule_keys = [r.get("rule_key") for r in triggered_rules if r.get("score", 0) < 0]
        positive_rule_keys = [r.get("rule_key") for r in triggered_rules if r.get("score", 0) > 0]

        if "gps_mismatch" in negative_rule_keys:
            reason_code = "LOCATION_MISMATCH"
            reason_desc = "Location conflict detected between declared location and incident evidence."
        elif "weather_contradicts" in negative_rule_keys:
            reason_code = "WEATHER_CONTRADICTION"
            reason_desc = "Historical weather archive contradicts reported weather conditions."
        elif "ocr_low" in negative_rule_keys:
            reason_code = "OCR_FAILURE"
            reason_desc = "OCR text extraction consistency below threshold."
        elif "missing_docs" in negative_rule_keys:
            reason_code = "MISSING_DOCUMENTS"
            reason_desc = "One or more required proof documents missing."
        elif "exceeds_policy_limit" in negative_rule_keys or "extremely_high_amount" in negative_rule_keys:
            reason_code = "HIGH_VALUE"
            reason_desc = "Requested claim amount exceeds standard policy limit."
        elif "story_low" in negative_rule_keys:
            reason_code = "STORY_INCONSISTENT"
            reason_desc = "Story description contains internal text contradictions."
        elif evidence_confidence < 60:
            reason_code = "LOW_EVIDENCE"
            reason_desc = "Evidence confidence below reliable decision threshold."

        # Translation mapping from technical rule keys to plain English phrases
        rule_translations = {
            "identity_verified": "verified customer identity documentation",
            "face_match": "matching biometric verification details",
            "liveness_passed": "liveness validation check",
            "policy_active": "active policy status in good standing",
            "coverage_valid": "eligible policy coverage terms",
            "gps_match": "matching location coordinates",
            "address_match": "consistent address verification",
            "weather_supports": "corroborating historical weather archive reports",
            "incident_verified_news": "supporting regional news reports of the event",
            "disaster_confirmed": "confirmed emergency alerts matching the incident window",
            "ocr_high": "highly legible documentation scans",
            "image_authentic": "authentic visual proof files with intact metadata",
            "timely_submission": "reporting of the claim in a timely manner",
            "gps_mismatch": "a location discrepancy between the reported incident place and photo coordinates",
            "weather_contradicts": "weather station records contradicting claimed weather conditions",
            "ocr_low": "low invoice or document text scan quality",
            "missing_docs": "missing required supporting documents",
            "exceeds_policy_limit": "requested payout amount exceeding standard policy limits",
            "extremely_high_amount": "an unusually high claim value request for this category",
            "story_low": "logical inconsistencies within written story description",
            "long_submission_delay": "a late claim submission timeline",
            "sameday_high_value": "an immediate high-value claim filed on the same day the policy took effect"
        }

        # Top Positives & Top Negatives sorted by magnitude
        pos_sorted = sorted([r for r in triggered_rules if r.get("score", 0) > 0], key=lambda x: x.get("score", 0), reverse=True)
        neg_sorted = sorted([r for r in triggered_rules if r.get("score", 0) < 0], key=lambda x: x.get("score", 0))

        top_positive = [f"+{r.get('score')} {r.get('rule')}" for r in pos_sorted[:3]]
        top_negative = [f"{r.get('score')} {r.get('rule')}" for r in neg_sorted[:3]]

        # Translate rule keys to natural language
        pos_phrases = [rule_translations.get(r.get("rule_key"), r.get("rule").lower()) for r in pos_sorted[:2]]
        neg_phrases = [rule_translations.get(r.get("rule_key"), r.get("rule").lower()) for r in neg_sorted[:2]]

        pos_str = " and ".join(pos_phrases) if pos_phrases else "active policy standing"
        neg_str = " and ".join(neg_phrases)

        # Build Claim-Specific Context
        claimant = getattr(claim, "claimant_name", None) or "Policyholder"
        desc_text = getattr(claim, "description", None)
        desc_stmt = f'"{desc_text}"' if desc_text else "declared incident"
        loc_text = getattr(claim, "incident_location", None)
        loc_stmt = f" at {loc_text}" if loc_text else ""
        amt_val = getattr(claim, "amount_requested", None)
        amt_stmt = f" for ₹{int(amt_val):,}" if amt_val else ""

        # Synthesize plain English Jargon-Free & Claim-Specific Decision Reason
        if decision == "STRAIGHT_THROUGH":
            multi_sentence_reason = (
                f"AI investigation for {claimant}'s claim ({desc_stmt}{loc_stmt}{amt_stmt}) passed with a verified Trust Score of {risk_score}/100. "
                f"Key verification indicators including {pos_str} strongly corroborate the reported event details. "
                f"All submitted evidence files passed visual, temporal, and location integrity checks."
            )
        elif decision == "FAST_REVIEW":
            multi_sentence_reason = (
                f"AI investigation for {claimant}'s claim ({desc_stmt}{loc_stmt}{amt_stmt}) scored a Trust Score of {risk_score}/100 and requires quick validation. "
                f"While primary checks such as {pos_str} are fully verified, minor exceptions like {neg_str or 'optional evidence gaps'} "
                f"warrant a brief manual check by an adjuster before payout."
            )
        elif decision == "MANUAL_REVIEW":
            multi_sentence_reason = (
                f"AI investigation for {claimant}'s claim ({desc_stmt}{loc_stmt}{amt_stmt}) yielded a Trust Score of {risk_score}/100. "
                f"Specific risk signals including {neg_str or 'unconfirmed details'} require detailed human review before settlement."
            )
        elif decision == "HIGH_RISK_INVESTIGATION":
            multi_sentence_reason = (
                f"AI investigation for {claimant}'s claim ({desc_stmt}{loc_stmt}{amt_stmt}) flagged high risk with a Trust Score of {risk_score}/100. "
                f"Significant inconsistencies were detected in {neg_str or reason_desc.lower()}, requiring a formal review by SIU."
            )
        else:
            multi_sentence_reason = (
                f"AI investigation for {claimant}'s claim ({desc_stmt}{loc_stmt}{amt_stmt}) failed risk threshold with a Trust Score of {risk_score}/100. "
                f"Critical risk factors including {neg_str or reason_desc.lower()} contradict the declared incident."
            )

        # Generate Actionable Next Actions
        next_actions = []
        if "missing_docs" in negative_rule_keys:
            next_actions.append("Upload Missing Proof Documents")
        if "gps_mismatch" in negative_rule_keys:
            next_actions.append("Verify Physical Incident Geolocation")
        if "ocr_low" in negative_rule_keys:
            next_actions.append("Re-scan Invoice with Clear OCR Quality")
        if decision in ("HIGH_RISK_INVESTIGATION", "REJECT_FRAUD"):
            next_actions.append("Route to Special Investigations Unit (SIU)")
        if not next_actions:
            next_actions = ["Proceed to Final Settlement", "Send Decision Update to Policyholder"]

        return {
            "decision": decision,
            "decision_label": decision_label,
            "reason_code": reason_code,
            "reason": reason_desc,
            "decision_reason": multi_sentence_reason,
            "top_positive": top_positive,
            "top_negative": top_negative,
            "next_actions": next_actions,
            "trust_score": risk_score,
            "fraud_risk_score": 100 - risk_score
        }
