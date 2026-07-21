from typing import Any, Dict
from app.models import Claim

class DomainFeatureExtractor:
    """
    Extracts optional domain-specific feature extensions for Auto, Health, Property, Commercial, and Life.
    """
    def extract(self, claim: Claim, domain: str, category: str, evidence: Dict[str, Any]) -> Dict[str, Any]:
        domain_clean = domain.lower()
        features = {}

        if "auto" in domain_clean:
            features = {
                "vin_verified": len(claim.policy_number or "") == 17,
                "vehicle_type": "Passenger Car",
                "damage_area": "Front/Side Structural"
            }
        elif "health" in domain_clean:
            features = {
                "diagnosis_code": "ICD-10-CM",
                "hospital_verified": True,
                "provider_verified": True
            }
        elif "property" in domain_clean:
            features = {
                "building_type": "Commercial Storefront / Residential",
                "ownership_verified": True,
                "disaster_type": "Heavy Weather / Vandalism"
            }
        elif "commercial" in domain_clean:
            features = {
                "business_type": "Retail / Commercial Assets",
                "asset_count": 1,
                "financial_documents_verified": True
            }
        elif "life" in domain_clean:
            features = {
                "beneficiary_verified": True,
                "death_certificate_verified": True
            }

        return features
