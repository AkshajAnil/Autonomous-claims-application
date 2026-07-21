from abc import ABC, abstractmethod
from typing import Any, Dict
from app.risk_engine import UniversalRiskEngine

class BaseFraudPredictor(ABC):
    """
    Abstract Predictor Interface enabling Phase 1 Rule Engine 
    and Phase 3 Supervised ML (XGBoost/LightGBM) pluggability.
    """
    @abstractmethod
    def predict(self, universal_features: Dict[str, Any]) -> Dict[str, Any]:
        pass


class RuleBasedFraudPredictor(BaseFraudPredictor):
    """
    Phase 1 Active Implementation delegating risk calculation to UniversalRiskEngine.
    """
    def __init__(self, base_score: int = 50):
        self.engine = UniversalRiskEngine(base_score=base_score)

    def predict(self, universal_features: Dict[str, Any]) -> Dict[str, Any]:
        return self.engine.evaluate(universal_features)


class XGBoostFraudPredictor(BaseFraudPredictor):
    """
    Phase 3 Reserved Shell for Supervised Machine Learning Model.
    """
    def __init__(self, model_path: str = "app/artifacts/xgb_model.pkl"):
        self.model_path = model_path

    def predict(self, universal_features: Dict[str, Any]) -> Dict[str, Any]:
        # Fallback to rule engine if model file not trained yet
        return RuleBasedFraudPredictor().predict(universal_features)
