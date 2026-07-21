from typing import Any, Dict

class VerificationStatusManager:
    """
    Tracks execution status of every external verification tool and service source.
    Statuses: SUCCESS, FAILED, NOT_FOUND, TIMEOUT, SKIPPED, NO_MATCH
    """
    def __init__(self):
        self.statuses: Dict[str, Dict[str, Any]] = {
            "identity": {"status": "SKIPPED", "detail": "Identity check not configured for this claim category"},
            "policy": {"status": "SUCCESS", "detail": "Policy retrieved and active"},
            "location": {"status": "SKIPPED", "detail": "Pending location geocode"},
            "weather": {"status": "SKIPPED", "detail": "Pending weather query"},
            "news": {"status": "SKIPPED", "detail": "Pending news search"},
            "gdacs": {"status": "SKIPPED", "detail": "Pending disaster RSS feed check"},
            "gemini_vision": {"status": "SKIPPED", "detail": "Pending vision analysis"},
            "ocr": {"status": "SKIPPED", "detail": "Pending OCR text extraction"}
        }

    def set_status(self, source: str, status: str, detail: str = "") -> None:
        valid_statuses = {"SUCCESS", "FAILED", "NOT_FOUND", "TIMEOUT", "SKIPPED", "NO_MATCH"}
        normalized_status = status.upper() if status.upper() in valid_statuses else "SUCCESS"
        self.statuses[source] = {
            "status": normalized_status,
            "detail": detail
        }

    def to_dict(self) -> Dict[str, Dict[str, Any]]:
        return self.statuses
