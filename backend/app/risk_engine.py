from typing import Any, Dict, List
from app.risk_rules import (
    IdentityRules, PolicyRules, LocationRules, WeatherRules,
    NewsRules, OCRRules, ImageRules, DocumentRules,
    StoryRules, FinancialRules, TimingRules, RuleResult
)

class UniversalRiskEngine:
    """
    Evaluates UniversalFeatures against all 11 rule category evaluators.
    Initializes Base Risk Score = 50, clamps final score between 0 and 100.
    """
    def __init__(self, base_score: int = 50):
        self.base_score = base_score

    def evaluate(self, features: Dict[str, Any]) -> Dict[str, Any]:
        all_rules: List[RuleResult] = []
        
        # Execute evaluators
        all_rules.extend(IdentityRules.evaluate(features))
        all_rules.extend(PolicyRules.evaluate(features))
        all_rules.extend(LocationRules.evaluate(features))
        all_rules.extend(WeatherRules.evaluate(features))
        all_rules.extend(NewsRules.evaluate(features))
        all_rules.extend(OCRRules.evaluate(features))
        all_rules.extend(ImageRules.evaluate(features))
        all_rules.extend(DocumentRules.evaluate(features))
        all_rules.extend(StoryRules.evaluate(features))
        all_rules.extend(FinancialRules.evaluate(features))
        all_rules.extend(TimingRules.evaluate(features))

        # Calculate final risk score
        score_deltas = sum(r.score for r in all_rules)
        raw_score = self.base_score + score_deltas
        clamped_score = max(0, min(100, raw_score))

        # Categorize positive (+) and negative (-) rules
        positive_rules = [r.to_dict() for r in all_rules if r.score > 0]
        negative_rules = [r.to_dict() for r in all_rules if r.score < 0]
        triggered_rules = [r.to_dict() for r in all_rules]

        return {
            "risk_score": clamped_score,
            "base_score": self.base_score,
            "triggered_rules": triggered_rules,
            "positive_rules": positive_rules,
            "negative_rules": negative_rules
        }
