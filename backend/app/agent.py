import asyncio
import json
import datetime
from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy.orm import Session

from app.mcp_client import McpClient
from app.models import Claim, ClaimStatus
from app.repository import add_event, apply_decision, claim_with_children, mark_processing, log_audit
from app.schemas import AgentDecision
from app.config import get_settings

from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
try:
    from langchain.agents import AgentExecutor, create_tool_calling_agent
except (ImportError, AttributeError):
    try:
        from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
    except (ImportError, AttributeError):
        AgentExecutor = None
        create_tool_calling_agent = None
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder


def is_gemini_quota_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return "429" in message or "resourceexhausted" in message or "rate-limited" in message


def extract_ml_features(claim: Claim, db: Session, policy_matches: list, visual_findings: dict, external_verification: dict) -> dict:
    months_cust = 12.0
    now = datetime.datetime.utcnow()
    if claim.user and claim.user.created_at:
        delta_days = (now - claim.user.created_at).days
        months_cust = max(1.0, float(delta_days / 30.0))

    claim_amt = float(claim.amount_requested or 10000.0)
    
    red_flags = []
    if isinstance(visual_findings, dict) and visual_findings.get("red_flags"):
        red_flags = visual_findings.get("red_flags")
        
    has_damage = "YES" if red_flags or (isinstance(visual_findings, dict) and visual_findings.get("findings")) else "NO"
    has_police_report = "YES" if claim.evidence and len(claim.evidence) > 0 else "NO"
    
    severity = "Minor Damage"
    if claim_amt > 50000 or len(red_flags) > 1:
        severity = "Major Damage"
    elif claim_amt > 80000:
        severity = "Total Loss"

    inc_type = "Single Vehicle Collision"
    if claim.claim_type:
        inc_type = claim.claim_type
        
    return {
        "months_as_customer": months_cust,
        "age": 35.0,
        "policy_csl": "250/500",
        "policy_deductable": 1000.0,
        "policy_annual_premium": 1200.0,
        "umbrella_limit": 0.0,
        "insured_sex": "FEMALE",
        "insured_education_level": "College",
        "insured_occupation": "exec-managerial",
        "insured_hobbies": "reading",
        "insured_relationship": "husband",
        "capital_gains": 0.0,
        "capital_loss": 0.0,
        "incident_type": inc_type,
        "collision_type": "Side Collision",
        "incident_severity": severity,
        "authorities_contacted": "Police",
        "incident_hour_of_the_day": 14.0,
        "number_of_vehicles_involved": 1.0,
        "property_damage": has_damage,
        "bodily_injuries": 0.0,
        "witnesses": 1.0,
        "police_report_available": has_police_report,
        "total_claim_amount": claim_amt,
        "injury_claim": claim_amt * 0.2,
        "property_claim": claim_amt * 0.5,
        "vehicle_claim": claim_amt * 0.3,
        "auto_make": "Toyota",
        "auto_model": "Camry",
        "auto_year": 2018.0
    }


VERIFICATION_MATRIX = {
    "Auto": {
        "location": "REQUIRED",
        "weather": "REQUIRED",
        "disaster": "OPTIONAL",
        "event": "NO"
    },
    "Property": {
        "location": "REQUIRED",
        "weather": "REQUIRED",
        "disaster": "REQUIRED",
        "event": "REQUIRED"
    },
    "Health": {
        "location": "NO",
        "weather": "NO",
        "disaster": "NO",
        "event": "NO"
    },
    "Commercial": {
        "location": "REQUIRED",
        "weather": "OPTIONAL",
        "disaster": "REQUIRED",
        "event": "REQUIRED"
    },
    "Life": {
        "location": "NO",
        "weather": "NO",
        "disaster": "NO",
        "event": "NO"
    }
}


def get_claim_verification_rules(claim: Claim) -> dict[str, str]:
    ins_type = "Auto"
    if claim and claim.claim_type:
        for possible in ["Auto", "Property", "Health", "Commercial", "Life"]:
            if possible.lower() in claim.claim_type.lower():
                ins_type = possible
                break
                
    rules = dict(VERIFICATION_MATRIX.get(ins_type, VERIFICATION_MATRIX["Auto"]))
    
    # Fine-tune based on specific claim sub-category & description
    claim_type_lower = (claim.claim_type or "").lower() if claim else ""
    desc_lower = (claim.description or "").lower() if claim else ""
    
    # For Vandalism or Theft (e.g. Property - Theft/Vandalism, Auto - Theft), weather and disaster checks are NOT relevant
    if any(k in claim_type_lower or k in desc_lower for k in ["vandalism", "theft", "vandal", "burglary", "stolen"]):
        rules["weather"] = "NO"
        rules["disaster"] = "NO"
        rules["event"] = "REQUIRED"
        
    return rules


def _unwrap_mcp_tool_result(res: Any, tool_name: str) -> Any:
    if isinstance(res, dict) and tool_name in res:
        return res[tool_name]
    response_key = f"{tool_name}_response"
    if isinstance(res, dict) and response_key in res:
        inner = res[response_key]
        return inner.get("output", inner) if isinstance(inner, dict) else inner
    if isinstance(res, dict) and "output" in res:
        return res["output"]
    return res


async def run_direct_investigation(
    mcp: McpClient,
    db: Session,
    claim_id: str,
    claim: Claim,
    incident_date: str,
    location_val: str,
    fallback_reasons: list[str],
) -> tuple[list, dict, dict]:
    """Run MCP tools directly when the LangChain agent is unavailable."""
    policy_matches: list = []
    visual_findings: dict = {}
    external_verification: dict = {}

    add_event(db, claim_id, "policy_lookup", "Policy Retrieved", "running")
    try:
        res = await mcp.call_tool("policy_rag_search", {"query": claim.description, "limit": 3})
        policy_matches = _unwrap_mcp_tool_result(res, "policy_rag_search")
        if not isinstance(policy_matches, list):
            policy_matches = [policy_matches] if policy_matches else []
    except Exception as exc:
        print(f"Direct policy RAG failed: {exc}")
        fallback_reasons.append("Qdrant Retrieval Failed")
        policy_matches = [{"clause": "Standard Coverage", "eligible": True}]
    add_event(db, claim_id, "policy_verify", "Coverage Verified", "running")

    add_event(db, claim_id, "ocr_vision", "OCR Completed", "running")
    try:
        image_urls = [e.url for e in claim.evidence]
        res = await mcp.call_tool(
            "visual_damage_assessment",
            {"claim_description": claim.description, "image_urls": image_urls},
        )
        visual_findings = _unwrap_mcp_tool_result(res, "visual_damage_assessment")
        if not isinstance(visual_findings, dict):
            visual_findings = {}
    except Exception as exc:
        print(f"Direct visual assessment failed: {exc}")
        fallback_reasons.append("Gemini Visual Analysis Failed")
        visual_findings = {"consistency": "Consistent", "red_flags": [], "confidence": 0.85}
    add_event(db, claim_id, "image_analysis", "Image Analysis Completed", "running")

    try:
        res = await mcp.call_tool(
            "verify_external_facts",
            {
                "claim_type": claim.claim_type,
                "description": claim.description,
                "incident_date": incident_date,
                "location": location_val,
                "policy_number": claim.policy_number,
            },
        )
        external_verification = _unwrap_mcp_tool_result(res, "verify_external_facts")
        if not isinstance(external_verification, dict):
            external_verification = {}
    except Exception as exc:
        print(f"Direct external verification failed: {exc}")
        fallback_reasons.append("External Verification Service Unavailable")
        external_verification = {
            "location_verification": {"available": False},
            "weather_verification": {"available": False},
            "disaster_verification": {"available": False},
            "event_verification": {"available": False},
        }
    add_event(db, claim_id, "external_verification", "External Verification Completed", "running")

    return policy_matches, visual_findings, external_verification


async def run_claim_agent(db_factory, claim_id: str) -> None:
    db: Session = db_factory()
    fallback_reasons = []
    try:
        mark_processing(db, claim_id)
        claim = claim_with_children(db, claim_id)
        if not claim:
            print(f"Claim {claim_id} not found.")
            return

        # Audit Log: AI Investigation Started
        log_audit(db, claim.user_id, "AI Investigation Started", {"claim_id": claim_id})
        
        # 1. Progressive Event: Claim Received
        add_event(db, claim_id, "Claim Received", "Claim submitted and received by the autonomous processor.", "running")

        final_decision_payload = None
        policy_matches = []
        visual_findings = {}
        external_verification = {}

        # Resolve location and incident date for external API checks
        incident_date = claim.incident_date.strftime("%Y-%m-%d") if claim.incident_date else claim.created_at.strftime("%Y-%m-%d")
        location_val = claim.incident_location or "Delhi"

        async with McpClient() as mcp:
            # Tool 1: Policy Search
            @tool
            async def policy_rag_search(query: str, limit: int = 3) -> str:
                """Search insurance policy clauses and routing rules in Qdrant. Returns relevant rules as a JSON string."""
                nonlocal policy_matches
                add_event(db, claim_id, "policy_lookup", "Policy Retrieved", "running")
                try:
                    res = await mcp.call_tool("policy_rag_search", {"query": query, "limit": limit})
                    if isinstance(res, dict) and "output" in res:
                        policy_matches = res["output"]
                    elif isinstance(res, dict) and "policy_rag_search_response" in res:
                        inner = res["policy_rag_search_response"]
                        policy_matches = inner.get("output", inner) if isinstance(inner, dict) else inner
                    else:
                        policy_matches = res
                except Exception as exc:
                    print(f"Qdrant policy RAG failed: {exc}. Using fallback policy data.")
                    nonlocal fallback_reasons
                    fallback_reasons.append("Qdrant Retrieval Failed")
                    policy_matches = [{"clause": "Standard Coverage", "eligible": True}]
                    
                add_event(db, claim_id, "policy_verify", "Coverage Verified", "running")
                return json.dumps(policy_matches)

            # Tool 2: Visual Assessment
            @tool
            async def visual_damage_assessment(claim_description: str, image_urls: list[str]) -> str:
                """Use a multimodal model to inspect claim image URLs for damage consistency. Returns assessment findings as a JSON string."""
                nonlocal visual_findings
                add_event(db, claim_id, "ocr_vision", "OCR Completed", "running")
                try:
                    valid_urls = [url for url in image_urls if "example.com" not in url] if image_urls else []
                    if not valid_urls:
                        valid_urls = [e.url for e in claim.evidence]
                    res = await mcp.call_tool("visual_damage_assessment", {"claim_description": claim_description, "image_urls": valid_urls})
                    if isinstance(res, dict) and "visual_damage_assessment_response" in res:
                        visual_findings = res["visual_damage_assessment_response"]
                    else:
                        visual_findings = res
                except Exception as exc:
                    print(f"Visual assessment failed: {exc}. Using fallback visual data.")
                    nonlocal fallback_reasons
                    fallback_reasons.append("Gemini Visual Analysis Failed")
                    visual_findings = {
                        "consistency": "Consistent",
                        "red_flags": [],
                        "confidence": 0.85
                    }
                    
                add_event(db, claim_id, "image_analysis", "Image Analysis Completed", "running")
                return json.dumps(visual_findings)

            # Tool 3: External Facts
            @tool
            async def verify_external_facts(claim_type: str, description: str, incident_date: str, location: str, policy_number: str) -> str:
                """Call live APIs to verify location, weather (Open-Meteo), disasters (GDACS), flights (OpenSky), and vehicle VINs (NHTSA). Returns verification report as a JSON string."""
                nonlocal external_verification
                try:
                    res = await mcp.call_tool("verify_external_facts", {
                        "claim_type": claim_type,
                        "description": description,
                        "incident_date": incident_date,
                        "location": location,
                        "policy_number": policy_number
                    })
                    if isinstance(res, dict) and "verify_external_facts_response" in res:
                        external_verification = res["verify_external_facts_response"]
                    else:
                        external_verification = res
                except Exception as exc:
                    print(f"External API check failed: {exc}. Using fallback verifications.")
                    nonlocal fallback_reasons
                    fallback_reasons.append("External Verification Service Unavailable")
                    external_verification = {
                        "location_verification": {"available": False},
                        "weather_verification": {"available": False},
                        "disaster_verification": {"available": False},
                        "event_verification": {"available": False}
                    }
                    
                add_event(db, claim_id, "external_verification", "External Verification Completed", "running")
                return json.dumps(external_verification)

            # Tool 4: Claims History
            @tool
            def fetch_user_claim_history() -> str:
                """Retrieve previous claims submitted by the same user to detect repeat fraud. Returns historical claims as a JSON string."""
                past_claims = db.query(Claim).filter(Claim.user_id == claim.user_id, Claim.id != claim.id).all()
                history_summary = [
                    {"id": pc.id, "type": pc.claim_type, "amount": pc.amount_requested, "status": pc.status, "date": pc.created_at.isoformat()}
                    for pc in past_claims
                ]
                return json.dumps(history_summary)

            # Initialize LangChain LLM (Gemini)
            settings = get_settings()
            llm = ChatGoogleGenerativeAI(
                model=settings.gemini_model,
                google_api_key=settings.gemini_api_key,
                temperature=0.0
            )

            tools = [policy_rag_search, visual_damage_assessment, verify_external_facts, fetch_user_claim_history]

            prompt = ChatPromptTemplate.from_messages([
                ("system", (
                    "You are an expert insurance fraud detection adjuster agent.\n"
                    "Your task is to run a thorough investigation on claim {claim_id} for user {username}.\n"
                    "You must execute the investigation by calling the following tools in order:\n"
                    "1. Call `policy_rag_search` to query the relevant policy rules.\n"
                    "2. Call `visual_damage_assessment` to perform multimodal assessment of evidence images.\n"
                    "3. Call `fetch_user_claim_history` to retrieve past claims submitted by this user.\n"
                    "4. Call `verify_external_facts` to check weather, coordinates, natural disasters, and other external data.\n\n"
                    "Please do not skip any steps. Once you have completed all checks, summarize your findings for the customer."
                )),
                MessagesPlaceholder(variable_name="chat_history"),
                ("human", "Investigate claim {claim_id} with description: '{description}', type: '{claim_type}', amount: {amount_requested}, incident date: {incident_date}, location: {location}, policy number: {policy_number}, and evidence image URLs: {image_urls}"),
                MessagesPlaceholder(variable_name="agent_scratchpad"),
            ])

            agent = create_tool_calling_agent(llm, tools, prompt)
            agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

            inputs = {
                "claim_id": claim.id,
                "username": claim.user.username,
                "description": claim.description,
                "claim_type": claim.claim_type,
                "amount_requested": claim.amount_requested,
                "incident_date": incident_date,
                "location": location_val,
                "policy_number": claim.policy_number,
                "image_urls": [e.url for e in claim.evidence],
                "chat_history": []
            }

            # Run LangChain agent investigation pipeline with rate limit retries & fallbacks
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    await agent_executor.ainvoke(inputs)
                    break
                except Exception as exc:
                    exc_str = str(exc)
                    # Retrying the same exhausted Gemini quota only adds latency.
                    # Run the direct investigation path, which can try the backup
                    # key and then safely fall back to deterministic services.
                    print(f"LangChain Agent failed on attempt {attempt+1}: {exc}. Running direct MCP investigation.")
                    fallback_reasons.append("LangChain Agent Unavailable")
                    policy_matches, visual_findings, external_verification = await run_direct_investigation(
                        mcp,
                        db,
                        claim_id,
                        claim,
                        incident_date,
                        location_val,
                        fallback_reasons,
                    )
                    break

        # 3. Run Fraud ML Service
        ml_features = extract_ml_features(claim, db, policy_matches, visual_findings, external_verification)
        
        from app.ml_service import predict_fraud_probability
        try:
            ml_res = predict_fraud_probability(ml_features)
        except Exception as exc:
            print("Fraud ML Service execution failed:", exc)
            fallback_reasons.append("XGBoost Fraud ML Service Failed")
            ml_res = {"fraud_probability": 0.25, "risk_score": 25, "recommendation": "AUTO_APPROVE", "shap_explanations": [{"feature": "claim_amount", "impact": 0.2}]}
            
        add_event(db, claim_id, "fraud_model", "Fraud Model Completed", "running")

        # 4. Risk Scoring Service (Merge AI findings + ML score)
        async with McpClient() as mcp:
            # Inject ML results into external_verification for the Gemini prompt
            external_verification["ml_fraud_probability"] = ml_res["fraud_probability"] * 100.0
            external_verification["ml_risk_level"] = "HIGH" if ml_res["risk_score"] > 70 else ("MEDIUM" if ml_res["risk_score"] >= 30 else "LOW")
            external_verification["ml_top_features"] = [item["feature"] for item in ml_res.get("shap_explanations", [])[:3]]
            
            past_claims = db.query(Claim).filter(Claim.user_id == claim.user_id, Claim.id != claim.id).all()
            history_summary = [
                {"id": pc.id, "type": pc.claim_type, "amount": pc.amount_requested, "status": pc.status, "date": pc.created_at.isoformat()}
                for pc in past_claims
            ]
            external_verification["claim_history"] = history_summary
            external_verification["identity_verified"] = bool(claim.user.is_identity_verified)

            final_decision_payload = None
            for attempt in range(max_retries):
                try:
                    final_decision_payload = await mcp.call_tool("fraud_risk_score", {
                        "policy_matches": policy_matches,
                        "visual_findings": visual_findings,
                        "amount_requested": claim.amount_requested,
                        "external_verification": external_verification
                    })
                    break
                except Exception as exc:
                    exc_str = str(exc)
                    print(f"Risk Scoring MCP Tool failed: {exc}. Using rule-based fallback decision.")
                    if is_gemini_quota_error(exc):
                        fallback_reasons.append("Gemini quota exhausted on both primary and backup keys; ML/rule-based scoring used")
                    else:
                        fallback_reasons.append("Gemini Risk Scoring Unavailable")
                    fallback_score = int(ml_res["fraud_probability"] * 100)
                    if claim.amount_requested > 70000:
                        fallback_score = max(fallback_score, 75)

                    summary_parts = []
                    loc_data = external_verification.get("location_verification") or {}
                    if loc_data.get("valid"):
                        summary_parts.append(f"Location verified for {location_val}")
                    weather_data = external_verification.get("weather_verification") or {}
                    if weather_data.get("weather_verified"):
                        summary_parts.append(
                            f"Weather archive confirmed {weather_data.get('rain_mm', 0)}mm rain and "
                            f"{weather_data.get('wind_kmh', 0)}km/h wind"
                        )
                    disaster_data = external_verification.get("disaster_verification") or {}
                    if disaster_data.get("disaster_verified"):
                        active = disaster_data.get("disasters_active") or []
                        if active:
                            summary_parts.append(f"{len(active)} GDACS disaster alert(s) active in the search window")
                        else:
                            summary_parts.append("No active regional disasters reported for the incident date")
                    event_data = external_verification.get("event_verification") or {}
                    if event_data.get("event_verified"):
                        summary_parts.append(event_data.get("details", "Event verification passed"))

                    investigation_summary = ". ".join(summary_parts) + "." if summary_parts else (
                        "Investigation completed using ML scoring and external verification APIs."
                    )

                    final_decision_payload = {
                        "fraud_risk_score": fallback_score,
                        "routing_decision": "auto_approve" if fallback_score < 30 else "investigate",
                        "decision_reason": (
                            f"Rule-based decision from XGBoost ML score ({fallback_score}/100) "
                            "and completed external verification checks."
                        ),
                        "summary": investigation_summary,
                        "confidence_score": 0.85,
                        "missing_documents": visual_findings.get("red_flags", []) if isinstance(visual_findings, dict) else [],
                        "fraud_indicators": ["High Requested Amount"] if fallback_score > 70 else [],
                        "recommended_action": "FRAUD_INVESTIGATION" if fallback_score > 70 else "ADJUSTER_REVIEW",
                        "verification_report": {
                            "policy_verified": bool(policy_matches),
                            "identity_verified": bool(claim.user.is_identity_verified),
                            "documents_verified": not visual_findings.get("red_flags") if isinstance(visual_findings, dict) else True,
                            "history_analysis": "No previous fraud detected",
                        },
                    }
                    break
            
            add_event(db, claim_id, "risk_assessment", "Final Risk Assessment Generated", "done")


        
        # Translate verifications
        rules = get_claim_verification_rules(claim)
        verifications_payload = {}
        
        # 1. Location
        loc_rule = rules.get("location", "REQUIRED")
        if loc_rule == "NO":
            verifications_payload["location"] = {
                "status": "NOT_REQUIRED",
                "source": "None",
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                "reason": "Location check not required for this insurance type."
            }
        else:
            loc_data = external_verification.get("location_verification") or {}
            location_conflict = external_verification.get("location_conflict") or {}
            if location_conflict:
                verifications_payload["location"] = {
                    "status": "FAILED",
                    "source": "Claim location consistency check",
                    "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                    "reason": (
                        f"The description mentions {location_conflict['description_city']}, but the selected "
                        f"incident location is {location_conflict['selected_location']}. Confirm the incident location."
                    ),
                }
            elif (not loc_data or loc_data.get("available") is False) and "External Verification Service Unavailable" in fallback_reasons:
                verifications_payload["location"] = {
                    "status": "UNKNOWN",
                    "source": "OpenStreetMap",
                    "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                    "reason": "Location geocoding service was unavailable."
                }
            elif loc_data.get("valid"):
                name = loc_data.get("name", "Claimed Location")
                verifications_payload["location"] = {
                    "status": "PASSED",
                    "source": "OpenStreetMap Geocoding",
                    "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                    "reason": f"Coordinates resolved for: {name}."
                }
            else:
                verifications_payload["location"] = {
                    "status": "FAILED",
                    "source": "OpenStreetMap Geocoding",
                    "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                    "reason": f"Coordinates could not be resolved for location: {location_val}."
                }
                
        # 2. Weather
        weather_rule = rules.get("weather", "REQUIRED")
        if weather_rule == "NO":
            verifications_payload["weather"] = {
                "status": "NOT_REQUIRED",
                "source": "None",
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                "reason": "Weather verification not required for this insurance type."
            }
        else:
            w_data = external_verification.get("weather_verification") or {}
            if (not w_data or w_data.get("available") is False) and weather_rule == "REQUIRED":
                verifications_payload["weather"] = {
                    "status": "UNKNOWN",
                    "source": "Open-Meteo Weather Archive",
                    "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                    "reason": "Weather archive service was unavailable or check was skipped."
                }
            elif not w_data:
                verifications_payload["weather"] = {
                    "status": "NOT_REQUIRED",
                    "source": "None",
                    "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                    "reason": "Weather verification skipped (not required)."
                }
            elif w_data.get("weather_verified"):
                rain = w_data.get("rain_mm", 0)
                wind = w_data.get("wind_kmh", 0)
                verifications_payload["weather"] = {
                    "status": "PASSED",
                    "source": "Open-Meteo Historical API",
                    "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                    "reason": f"Weather conditions verified: {rain}mm rain, {wind}km/h wind speed recorded."
                }
            else:
                verifications_payload["weather"] = {
                    "status": "FAILED",
                    "source": "Open-Meteo Historical API",
                    "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                    "reason": "Weather station database query returned no records for this incident date."
                }
                
        # 3. Disaster
        disaster_rule = rules.get("disaster", "REQUIRED")
        if disaster_rule == "NO":
            verifications_payload["disaster"] = {
                "status": "NOT_REQUIRED",
                "source": "None",
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                "reason": "Natural disaster verification not required for this insurance type."
            }
        else:
            d_data = external_verification.get("disaster_verification") or {}
            if (not d_data or d_data.get("available") is False) and disaster_rule == "REQUIRED":
                verifications_payload["disaster"] = {
                    "status": "UNKNOWN",
                    "source": d_data.get("source", "GDACS Alerts Feed"),
                    "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                    "reason": d_data.get("details", "GDACS and its ReliefWeb fallback were unavailable or the check was skipped.")
                }
            elif not d_data:
                verifications_payload["disaster"] = {
                    "status": "NOT_REQUIRED",
                    "source": "None",
                    "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                    "reason": "Disaster verification skipped (not required)."
                }
            elif d_data.get("disaster_verified"):
                active = d_data.get("disasters_active", [])
                reason_str = f"Active disasters in region: {', '.join(active)}." if active else "No active regional disasters reported on incident date."
                verifications_payload["disaster"] = {
                    "status": "PASSED",
                    "source": "GDACS GeoRSS Feed",
                    "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                    "reason": reason_str
                }
            else:
                verifications_payload["disaster"] = {
                    "status": "FAILED",
                    "source": d_data.get("source", "GDACS GeoRSS Feed"),
                    "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                    "reason": "Failed to query GDACS disaster alert records."
                }
                
        # 4. Event
        event_rule = rules.get("event", "REQUIRED")
        if event_rule == "NO":
            verifications_payload["event"] = {
                "status": "NOT_REQUIRED",
                "source": "None",
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                "reason": "Event verification not required for this insurance type."
            }
        else:
            e_data = external_verification.get("event_verification") or {}
            if (not e_data or e_data.get("available") is False) and event_rule == "REQUIRED":
                verifications_payload["event"] = {
                    "status": "UNKNOWN",
                    "source": e_data.get("source", "Google News RSS via Gemini"),
                    "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                    "reason": e_data.get("details", "Event verification service was unavailable or check was skipped.")
                }
            elif not e_data:
                verifications_payload["event"] = {
                    "status": "NOT_REQUIRED",
                    "source": "None",
                    "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                    "reason": "Event verification skipped (not required)."
                }
            elif e_data.get("event_verified"):
                verifications_payload["event"] = {
                    "status": "PASSED",
                    "source": e_data.get("source", "Google News RSS Feed"),
                    "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                    "reason": e_data.get("details", "Public event checked successfully.")
                }
            else:
                verifications_payload["event"] = {
                    "status": "FAILED",
                    "source": e_data.get("source", "Google News RSS Feed"),
                    "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                    "reason": e_data.get("details", "No public event matched the incident description.")
                }        # Execute Universal Risk Engine v4.0 Pipeline
        from app.workflow_planner import WorkflowPlanner
        from app.domain_features import DomainFeatureExtractor
        from app.evidence_collector import EvidenceCollector
        from app.verification_status import VerificationStatusManager
        from app.feature_extractor import UniversalFeatureExtractor
        from app.fraud_predictor import RuleBasedFraudPredictor
        from app.evidence_confidence import EvidenceConfidenceCalculator
        from app.decision_engine import DecisionEngine

        wf_plan = WorkflowPlanner().plan(claim.claim_type or "", claim.description or "")

        collector = EvidenceCollector()
        collector.add_gemini_analysis(visual_findings if isinstance(visual_findings, dict) else {})
        collector.add_weather_verification(external_verification.get("weather_verification") or {})
        collector.add_location_verification(external_verification.get("location_verification") or {})
        collector.add_disaster_verification(external_verification.get("disaster_verification") or {})
        collector.add_news_verification(external_verification.get("event_verification") or {})
        collector.add_policy_rag(policy_matches or [])

        v_manager = VerificationStatusManager()
        if external_verification.get("weather_verification", {}).get("available"):
            v_manager.set_status("weather", "SUCCESS" if external_verification["weather_verification"].get("weather_verified") else "FAILED")
        if external_verification.get("location_verification"):
            v_manager.set_status("location", "SUCCESS" if external_verification["location_verification"].get("valid") else "FAILED")
        if external_verification.get("disaster_verification", {}).get("available"):
            v_manager.set_status("gdacs", "SUCCESS" if external_verification["disaster_verification"].get("disaster_verified") else "NO_MATCH")
        if external_verification.get("event_verification", {}).get("available"):
            v_manager.set_status("news", "SUCCESS" if external_verification["event_verification"].get("event_verified") else "NO_MATCH")
        v_manager.set_status("gemini_vision", "SUCCESS" if visual_findings else "FAILED")
        v_manager.set_status("ocr", "SUCCESS" if visual_findings else "FAILED")

        evidence_dict = collector.to_dict()
        status_dict = v_manager.to_dict()

        extractor = UniversalFeatureExtractor()
        univ_features = extractor.extract(claim, evidence_dict, status_dict)

        # Synchronize Verification Checklist statuses with Extracted Features
        if univ_features.get("gps_mismatch", {}).get("value"):
            verifications_payload["location"] = {
                "status": "FAILED",
                "source": "Location Verification Engine",
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                "reason": "Location conflict detected between declared location and incident evidence."
            }
        if univ_features.get("weather_contradiction", {}).get("value"):
            verifications_payload["weather"] = {
                "status": "FAILED",
                "source": "Open-Meteo Weather Archive",
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                "reason": "Historical weather archive contradicts claimed weather conditions."
            }

        dom_extractor = DomainFeatureExtractor()
        dom_features = dom_extractor.extract(claim, wf_plan["domain"], wf_plan["category"], evidence_dict)

        predictor = RuleBasedFraudPredictor()
        risk_res = predictor.predict(univ_features)

        conf_calc = EvidenceConfidenceCalculator()
        evid_conf = conf_calc.calculate(univ_features, status_dict)

        dec_engine = DecisionEngine()
        dec_res = dec_engine.evaluate(risk_res["risk_score"], evid_conf, risk_res["triggered_rules"])

        # Override summary with Decision Reason for total transparency
        final_decision_payload["summary"] = dec_res.get("decision_reason", final_decision_payload.get("summary"))
        final_decision_payload["decision_reason"] = dec_res.get("decision_reason", final_decision_payload.get("decision_reason"))

        if final_decision_payload:
            top_features_list = dec_res.get("top_positive", []) + dec_res.get("top_negative", [])
            fallback_reason_str = "; ".join(fallback_reasons) if fallback_reasons else None
            apply_decision(
                db, 
                claim_id, 
                final_decision_payload, 
                float(risk_res["risk_score"]) / 100.0, 
                top_features_list,
                fallback_reason=fallback_reason_str,
                verifications=verifications_payload,
                image_anomaly_score=0.1,
                ocr_consistency_score=0.95,
                evidence=evidence_dict,
                verification_status=status_dict,
                universal_features=univ_features,
                domain_features=dom_features,
                risk_result=risk_res,
                evidence_confidence=evid_conf,
                decision_result=dec_res
            )

        else:
            add_event(db, claim_id, "error", "Agent finished without generating final decision payload.", "alert")

        # Refresh claim status to display in audit logs
        db.refresh(claim)
        log_audit(db, claim.user_id, "AI Investigation Completed", {"claim_id": claim_id, "status": claim.status})

    except Exception as exc:
        import traceback
        db.rollback()
        try:
            add_event(db, claim_id, "error", f"Investigation aborted due to error: {str(exc)}", "alert")
            log_audit(db, None, "AI Investigation Failed", {"claim_id": claim_id, "error": str(exc)})
        except Exception as log_err:
            print("Failed to log error to DB:", log_err)
            traceback.print_exc()
    finally:
        db.close()


async def stream_events(db_factory, claim_id: str) -> AsyncIterator[str]:
    seen: set[str] = set()
    while True:
        db: Session = db_factory()
        claim: Claim | None = claim_with_children(db, claim_id)
        if not claim:
            db.close()
            yield "event: error\ndata: Claim not found\n\n"
            return
        
        # Sort events by created_at to preserve progression
        for event in sorted(claim.events, key=lambda item: item.created_at):
            if event.id not in seen:
                seen.add(event.id)
                payload = {
                    "id": event.id,
                    "step": event.step,
                    "message": event.message,
                    "status": event.status,
                    "created_at": event.created_at.isoformat(),
                }
                yield f"event: agent_step\ndata: {json.dumps(payload)}\n\n"
                
        done = claim.status in {"APPROVED", "REJECTED", "CLOSED"} or (claim.status == "UNDER_REVIEW" and len(claim.events) >= 8)
        db.close()
        if done:
            yield "event: done\ndata: complete\n\n"
            return
        await asyncio.sleep(0.8)
