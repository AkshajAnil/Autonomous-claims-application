from typing import Any, Dict, List
from app.domain_taxonomy import INSURANCE_TAXONOMY, resolve_domain_and_category

class WorkflowPlanner:
    """
    Resolves Insurance Domain (Auto, Health, Property, Commercial, Life),
    Claim Category (20 categories), selects required/optional MCP tools,
    and defines the tool execution sequence.
    """
    def plan(self, claim_type: str, description: str = "") -> Dict[str, Any]:
        domain, category, icon = resolve_domain_and_category(claim_type)
        
        domain_info = INSURANCE_TAXONOMY.get(domain, INSURANCE_TAXONOMY["Auto Insurance"])
        default_tools = domain_info.get("default_verifications", ["weather", "location", "gemini_vision"])
        
        # Category-specific required & optional tool rules
        required_tools = list(default_tools)
        optional_tools = []

        if "Collision" in category or "Accident" in category:
            required_tools = ["gemini_damage", "weather", "location", "police_report"]
            optional_tools = ["witness_verification", "dashcam_analysis"]
        elif "Comprehensive" in category or "Building" in category or "Property" in category:
            required_tools = ["weather", "gdacs", "news", "location"]
            optional_tools = ["vehicle_registry", "property_inspection"]
        elif "Hospitalization" in category or "Medical" in category:
            required_tools = ["medical_ocr", "hospital_verification", "identity"]
            optional_tools = ["pharmacy_ocr", "prescription_verification"]
        elif "Death" in category or "Disability" in category:
            required_tools = ["death_certificate_ocr", "hospital_records", "identity", "beneficiary"]
            optional_tools = ["doctor_verification"]

        return {
            "domain": domain,
            "category": category,
            "icon": icon,
            "required_tools": required_tools,
            "optional_tools": optional_tools,
            "execution_sequence": required_tools + optional_tools,
            "workflow_version": "v1.0"
        }
