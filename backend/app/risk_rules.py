from dataclasses import dataclass
from typing import Any, Dict, List
from app.config import RISK_RULES_CONFIG

@dataclass
class RuleResult:
    category: str
    rule_key: str
    rule: str
    score: int
    description: str
    passed: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "rule_key": self.rule_key,
            "rule": self.rule,
            "score": self.score,
            "description": self.description,
            "passed": self.passed
        }


class IdentityRules:
    @staticmethod
    def evaluate(features: Dict[str, Any]) -> List[RuleResult]:
        results = []
        if features.get("identity_verified", {}).get("value"):
            cfg = RISK_RULES_CONFIG["identity_verified"]
            results.append(RuleResult("Identity", "identity_verified", "Identity Verified", cfg["score"], cfg["description"], True))
        if features.get("face_match", {}).get("value"):
            cfg = RISK_RULES_CONFIG["face_match"]
            results.append(RuleResult("Identity", "face_match", "Face Match Successful", cfg["score"], cfg["description"], True))
        if features.get("liveness_passed", {}).get("value"):
            cfg = RISK_RULES_CONFIG["liveness_passed"]
            results.append(RuleResult("Identity", "liveness_passed", "Liveness Passed", cfg["score"], cfg["description"], True))
        return results


class PolicyRules:
    @staticmethod
    def evaluate(features: Dict[str, Any]) -> List[RuleResult]:
        results = []
        if features.get("policy_active", {}).get("value"):
            cfg = RISK_RULES_CONFIG["policy_active"]
            results.append(RuleResult("Policy", "policy_active", "Policy Active", cfg["score"], cfg["description"], True))
        if features.get("coverage_valid", {}).get("value"):
            cfg = RISK_RULES_CONFIG["coverage_valid"]
            results.append(RuleResult("Policy", "coverage_valid", "Coverage Valid", cfg["score"], cfg["description"], True))
        if features.get("purchased_under_30_days", {}).get("value"):
            cfg = RISK_RULES_CONFIG["policy_newly_purchased"]
            results.append(RuleResult("Policy", "policy_newly_purchased", "Purchased <30 Days Ago", cfg["score"], cfg["description"], True))
        return results


class LocationRules:
    @staticmethod
    def evaluate(features: Dict[str, Any]) -> List[RuleResult]:
        results = []
        if features.get("gps_match", {}).get("value"):
            cfg = RISK_RULES_CONFIG["gps_match"]
            results.append(RuleResult("Location", "gps_match", "GPS Match", cfg["score"], cfg["description"], True))
        if features.get("address_match", {}).get("value"):
            cfg = RISK_RULES_CONFIG["address_match"]
            results.append(RuleResult("Location", "address_match", "Address Match", cfg["score"], cfg["description"], True))
        if features.get("gps_mismatch", {}).get("value"):
            cfg = RISK_RULES_CONFIG["gps_mismatch"]
            results.append(RuleResult("Location", "gps_mismatch", "GPS Mismatch", cfg["score"], cfg["description"], True))
        return results


class WeatherRules:
    @staticmethod
    def evaluate(features: Dict[str, Any]) -> List[RuleResult]:
        results = []
        if features.get("weather_verified", {}).get("value"):
            cfg = RISK_RULES_CONFIG["weather_supports"]
            results.append(RuleResult("Weather", "weather_supports", "Weather Supports Claim", cfg["score"], cfg["description"], True))
        elif features.get("weather_contradiction", {}).get("value"):
            cfg = RISK_RULES_CONFIG["weather_contradicts"]
            results.append(RuleResult("Weather", "weather_contradicts", "Weather Contradicts Claim", cfg["score"], cfg["description"], True))
        return results


class NewsRules:
    @staticmethod
    def evaluate(features: Dict[str, Any]) -> List[RuleResult]:
        results = []
        if features.get("incident_verified", {}).get("value"):
            cfg = RISK_RULES_CONFIG["incident_verified_news"]
            results.append(RuleResult("News", "incident_verified_news", "Incident Verified by News", cfg["score"], cfg["description"], True))
        if features.get("disaster_confirmed", {}).get("value"):
            cfg = RISK_RULES_CONFIG["disaster_confirmed"]
            results.append(RuleResult("News", "disaster_confirmed", "Disaster Confirmed", cfg["score"], cfg["description"], True))
        return results


class OCRRules:
    @staticmethod
    def evaluate(features: Dict[str, Any]) -> List[RuleResult]:
        results = []
        ocr = float(features.get("ocr_score", {}).get("value", 0.0))
        if ocr >= 0.95:
            cfg = RISK_RULES_CONFIG["ocr_high"]
            results.append(RuleResult("OCR", "ocr_high", "OCR Consistency High (>=95%)", cfg["score"], cfg["description"], True))
        elif ocr >= 0.80:
            cfg = RISK_RULES_CONFIG["ocr_moderate"]
            results.append(RuleResult("OCR", "ocr_moderate", "OCR Consistency Moderate (80-94%)", cfg["score"], cfg["description"], True))
        else:
            cfg = RISK_RULES_CONFIG["ocr_low"]
            results.append(RuleResult("OCR", "ocr_low", "OCR Consistency Low (<80%)", cfg["score"], cfg["description"], True))
        return results


class ImageRules:
    @staticmethod
    def evaluate(features: Dict[str, Any]) -> List[RuleResult]:
        results = []
        img_score = float(features.get("image_score", {}).get("value", 0.0))
        if img_score >= 0.85:
            cfg = RISK_RULES_CONFIG["image_authentic"]
            results.append(RuleResult("Image", "image_authentic", "Authentic Image", cfg["score"], cfg["description"], True))
        elif img_score < 0.50:
            cfg = RISK_RULES_CONFIG["image_manipulated"]
            results.append(RuleResult("Image", "image_manipulated", "Possible Manipulation", cfg["score"], cfg["description"], True))
        return results


class DocumentRules:
    @staticmethod
    def evaluate(features: Dict[str, Any]) -> List[RuleResult]:
        results = []
        if features.get("all_docs_present", {}).get("value"):
            cfg = RISK_RULES_CONFIG["all_docs_present"]
            results.append(RuleResult("Document", "all_docs_present", "All Documents Present", cfg["score"], cfg["description"], True))
        if features.get("missing_docs", {}).get("value"):
            cfg = RISK_RULES_CONFIG["missing_docs"]
            results.append(RuleResult("Document", "missing_docs", "Missing Documents", cfg["score"], cfg["description"], True))
        return results


class StoryRules:
    @staticmethod
    def evaluate(features: Dict[str, Any]) -> List[RuleResult]:
        results = []
        story = float(features.get("story_consistency", {}).get("value", 0.0))
        if story >= 0.90:
            cfg = RISK_RULES_CONFIG["story_high"]
            results.append(RuleResult("Story", "story_high", "Story Consistency High (>=90%)", cfg["score"], cfg["description"], True))
        elif story >= 0.70:
            cfg = RISK_RULES_CONFIG["story_moderate"]
            results.append(RuleResult("Story", "story_moderate", "Story Consistency Moderate (70-89%)", cfg["score"], cfg["description"], True))
        else:
            cfg = RISK_RULES_CONFIG["story_low"]
            results.append(RuleResult("Story", "story_low", "Story Consistency Low (<70%)", cfg["score"], cfg["description"], True))
        return results


class FinancialRules:
    @staticmethod
    def evaluate(features: Dict[str, Any]) -> List[RuleResult]:
        results = []
        amt = float(features.get("requested_amount", {}).get("value", 0.0))
        if amt <= 50000:
            cfg = RISK_RULES_CONFIG["amount_normal"]
            results.append(RuleResult("Financial", "amount_normal", "Amount Within Normal Range", cfg["score"], cfg["description"], True))
        elif amt > 100000:
            cfg = RISK_RULES_CONFIG["exceeds_policy_limit"]
            results.append(RuleResult("Financial", "exceeds_policy_limit", "Amount Exceeds Policy Limit", cfg["score"], cfg["description"], True))
        elif amt > 75000:
            cfg = RISK_RULES_CONFIG["extremely_high_amount"]
            results.append(RuleResult("Financial", "extremely_high_amount", "Extremely High Amount", cfg["score"], cfg["description"], True))
        return results


class TimingRules:
    @staticmethod
    def evaluate(features: Dict[str, Any]) -> List[RuleResult]:
        results = []
        if features.get("long_delay", {}).get("value"):
            cfg = RISK_RULES_CONFIG["long_submission_delay"]
            results.append(RuleResult("Timing", "long_submission_delay", "Long Submission Delay", cfg["score"], cfg["description"], True))
        else:
            cfg = RISK_RULES_CONFIG["timely_submission"]
            results.append(RuleResult("Timing", "timely_submission", "Submitted Within Expected Time", cfg["score"], cfg["description"], True))
            
        if features.get("sameday_high_value", {}).get("value"):
            cfg = RISK_RULES_CONFIG["sameday_high_value"]
            results.append(RuleResult("Timing", "sameday_high_value", "Same-Day High-Value Claim", cfg["score"], cfg["description"], True))
        return results
