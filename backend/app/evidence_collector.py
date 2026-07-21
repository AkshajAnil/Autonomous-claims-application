import datetime
from typing import Any, Dict

class EvidenceCollector:
    """
    Captures and stores raw un-transformed JSON outputs from every AI model 
    and MCP tool execution prior to feature extraction.
    """
    def __init__(self):
        self.evidence: Dict[str, Any] = {
            "gemini": {},
            "weather": {},
            "osm": {},
            "gdacs": {},
            "reliefweb": {},
            "news": {},
            "policy_rag": {},
            "identity": {},
            "business": {}
        }

    def add_gemini_analysis(self, data: Dict[str, Any]) -> None:
        if isinstance(data, dict):
            self.evidence["gemini"] = data

    def add_weather_verification(self, data: Dict[str, Any]) -> None:
        if isinstance(data, dict):
            self.evidence["weather"] = data

    def add_location_verification(self, data: Dict[str, Any]) -> None:
        if isinstance(data, dict):
            self.evidence["osm"] = data

    def add_disaster_verification(self, data: Dict[str, Any]) -> None:
        if isinstance(data, dict):
            self.evidence["gdacs"] = data

    def add_news_verification(self, data: Dict[str, Any]) -> None:
        if isinstance(data, dict):
            self.evidence["news"] = data

    def add_policy_rag(self, data: Any) -> None:
        self.evidence["policy_rag"] = data if isinstance(data, (dict, list)) else {"summary": str(data)}

    def to_dict(self) -> Dict[str, Any]:
        return self.evidence
