from typing import Any, Dict

class EvidenceConfidenceCalculator:
    """
    Computes Evidence Confidence Score (0-100%) reflecting overall evidence quality and source coverage.
    """
    def calculate(self, features: Dict[str, Any], verification_statuses: Dict[str, Dict[str, Any]]) -> int:
        base_confidence = 100.0

        # Deduct if OCR / Image confidence is low
        ocr_conf = float(features.get("ocr_score", {}).get("confidence", 0.95))
        img_conf = float(features.get("image_score", {}).get("confidence", 0.95))
        story_conf = float(features.get("story_consistency", {}).get("confidence", 0.90))

        if ocr_conf < 0.80:
            base_confidence -= 15.0
        if img_conf < 0.80:
            base_confidence -= 15.0
        if story_conf < 0.80:
            base_confidence -= 10.0

        # Check verification API statuses
        for src, status_obj in verification_statuses.items():
            st = status_obj.get("status", "SUCCESS")
            if st in ("FAILED", "TIMEOUT"):
                base_confidence -= 10.0
            elif st == "SKIPPED":
                base_confidence -= 2.0

        # Deduct for missing documents
        if features.get("missing_docs", {}).get("value"):
            base_confidence -= 15.0

        clamped = max(0, min(100, int(round(base_confidence))))
        return clamped
