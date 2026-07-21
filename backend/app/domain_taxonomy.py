from typing import Any, Dict, List, Tuple

INSURANCE_TAXONOMY: Dict[str, Dict[str, Any]] = {
    "Auto Insurance": {
        "icon": "🚗",
        "categories": {
            "Collision & Accident": [
                "Single Vehicle Collision", "Multi Vehicle Collision", "Parked Vehicle Damage",
                "Hit and Run", "Rollover", "Rear-end Collision"
            ],
            "Comprehensive (Non-Collision)": [
                "Theft", "Fire", "Flood", "Storm", "Hail", "Vandalism", "Falling Object", "Animal Collision"
            ],
            "Injury & Medical": [
                "Driver Injury", "Passenger Injury", "Bodily Injury", "Medical Expenses", "Personal Injury Protection"
            ],
            "Vehicle Damage & Services": [
                "Windshield Damage", "Glass Claims", "Total Loss", "Mechanical Breakdown", "Towing", "Rental Reimbursement"
            ]
        },
        "default_verifications": ["weather", "location", "gemini_vision", "police_report"]
    },
    "Health Insurance": {
        "icon": "🏥",
        "categories": {
            "Hospitalization": ["Inpatient Treatment", "Surgery", "ICU Admission", "Emergency Admission"],
            "Medical Treatment": ["Consultation", "Medicines", "Diagnostics", "Laboratory Tests", "Physiotherapy"],
            "Critical Illness": ["Cancer", "Heart Attack", "Stroke", "Kidney Failure", "Organ Transplant"],
            "Wellness & Other Benefits": ["Preventive Care", "Vaccination", "Health Checkup", "Maternity", "Dental", "Vision"]
        },
        "default_verifications": ["medical_ocr", "hospital_verification", "identity"]
    },
    "Property Insurance": {
        "icon": "🏠",
        "categories": {
            "Building Damage": ["Fire", "Flood", "Storm", "Earthquake", "Structural Damage"],
            "Contents & Personal Property": ["Furniture", "Electronics", "Appliances", "Personal Belongings"],
            "Theft & Vandalism": ["Burglary", "Theft", "Robbery", "Vandalism"],
            "Repair & Restoration": ["Temporary Repairs", "Restoration", "Water Damage Cleanup", "Reconstruction"]
        },
        "default_verifications": ["weather", "gdacs", "gemini_vision", "police_report", "invoice_ocr"]
    },
    "Commercial Insurance": {
        "icon": "🏢",
        "categories": {
            "Property & Assets": ["Office Damage", "Warehouse Damage", "Equipment Damage", "Inventory Loss"],
            "Liability": ["Third Party Injury", "Public Liability", "Product Liability", "Professional Liability"],
            "Business Interruption": ["Income Loss", "Operational Shutdown", "Supply Chain Disruption"],
            "Commercial Vehicle & Equipment": ["Fleet Vehicles", "Heavy Equipment", "Cargo Damage", "Machinery Breakdown"]
        },
        "default_verifications": ["property_inspection", "weather", "financial_audit", "legal_docs"]
    },
    "Life Insurance": {
        "icon": "❤️",
        "categories": {
            "Death Claim": ["Natural Death", "Accidental Death"],
            "Disability": ["Permanent Disability", "Partial Disability", "Accidental Disability"],
            "Critical Illness": ["Cancer", "Stroke", "Heart Disease", "Kidney Failure"],
            "Policy Benefits": ["Maturity Benefit", "Survival Benefit", "Surrender Value", "Policy Loan", "Rider Benefits"]
        },
        "default_verifications": ["death_certificate_ocr", "hospital_records", "identity", "beneficiary"]
    }
}


def resolve_domain_and_category(claim_type_str: str) -> Tuple[str, str, str]:
    """
    Given a claim type string (e.g. 'Property - Theft/Vandalism', 'Auto - Collision'),
    returns (domain_name, category_name, icon).
    """
    if not claim_type_str:
        return "Auto Insurance", "Collision & Accident", "🚗"

    clean_str = claim_type_str.strip()

    # Direct matching against taxonomy
    for domain, d_data in INSURANCE_TAXONOMY.items():
        domain_prefix = domain.split()[0].lower() # e.g. "auto", "health", "property", "commercial", "life"
        if domain_prefix in clean_str.lower():
            for cat_name in d_data["categories"].keys():
                # Compare tokens
                cat_tokens = [t.lower() for t in cat_name.split() if len(t) > 3]
                if any(token in clean_str.lower() for token in cat_tokens):
                    return domain, cat_name, d_data["icon"]
            # Default category for matched domain
            first_cat = list(d_data["categories"].keys())[0]
            return domain, first_cat, d_data["icon"]

    return "Auto Insurance", "Collision & Accident", "🚗"
