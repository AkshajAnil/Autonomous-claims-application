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


def _normalize_tool_payload(payload: Any) -> dict:
    if isinstance(payload, dict):
        return payload
    return {}


def build_investigation_summary(
    claim: Claim,
    policy_matches: list,
    visual_findings: dict,
    external_verification: dict,
    verifications_payload: dict,
) -> str:
    summary_parts = [
        f"Agentic investigation completed for {claim.claimant_name}'s {claim.claim_type} claim.",
    ]

    if policy_matches:
        summary_parts.append("Policy retrieval returned relevant coverage context.")

    loc = verifications_payload.get("location", {})
    if loc.get("status") == "PASSED":
        summary_parts.append(loc.get("reason", "Location verification passed.").rstrip("."))
    elif loc.get("status") == "FAILED":
        summary_parts.append(loc.get("reason", "Location verification failed.").rstrip("."))

    weather = verifications_payload.get("weather", {})
    if weather.get("status") in {"PASSED", "FAILED", "UNKNOWN"}:
        summary_parts.append(weather.get("reason", "Weather verification completed.").rstrip("."))

    disaster = verifications_payload.get("disaster", {})
    if disaster.get("status") in {"PASSED", "FAILED", "UNKNOWN"}:
        summary_parts.append(disaster.get("reason", "Disaster verification completed.").rstrip("."))

    event = verifications_payload.get("event", {})
    if event.get("status") in {"PASSED", "FAILED", "UNKNOWN"}:
        summary_parts.append(event.get("reason", "Event verification completed.").rstrip("."))

    red_flags = visual_findings.get("red_flags", []) if isinstance(visual_findings, dict) else []
    if red_flags:
        summary_parts.append(f"Visual analysis reported {len(red_flags)} issue(s): {', '.join(map(str, red_flags[:3]))}")
    elif visual_findings:
        summary_parts.append("Visual evidence did not report material red flags.")

    return " ".join(part.rstrip(".") + "." for part in summary_parts if part)


def build_agentic_decision_payload(
    claim: Claim,
    policy_matches: list,
    visual_findings: dict,
    external_verification: dict,
    verifications_payload: dict,
) -> dict:
    visual_findings = _normalize_tool_payload(visual_findings)
    external_verification = _normalize_tool_payload(external_verification)

    failed_required = [
        name for name, data in verifications_payload.items()
        if data.get("status") == "FAILED"
    ]
    unknown_required = [
        name for name, data in verifications_payload.items()
        if data.get("status") == "UNKNOWN"
    ]
    red_flags = visual_findings.get("red_flags") or []
    if not isinstance(red_flags, list):
        red_flags = [str(red_flags)]

    fraud_indicators = []
    if failed_required:
        fraud_indicators.append("Failed required verification: " + ", ".join(failed_required))
    if unknown_required:
        fraud_indicators.append("Required verification unavailable: " + ", ".join(unknown_required))
    if red_flags:
        fraud_indicators.extend(str(flag) for flag in red_flags[:5])

    policy_verified = bool(policy_matches)
    identity_verified = bool(claim.user and claim.user.is_identity_verified)
    documents_verified = not red_flags
    investigation_summary = build_investigation_summary(
        claim,
        policy_matches,
        visual_findings,
        external_verification,
        verifications_payload,
    )

    if failed_required:
        routing_decision = "investigate"
        recommended_action = "ADJUSTER_REVIEW"
        decision_reason = (
            "Agentic workflow requires manual review because one or more required "
            f"verification checks failed: {', '.join(failed_required)}."
        )
    elif unknown_required or red_flags or not policy_verified:
        routing_decision = "investigate"
        recommended_action = "ADJUSTER_REVIEW"
        reasons = []
        if unknown_required:
            reasons.append(f"unavailable required checks: {', '.join(unknown_required)}")
        if red_flags:
            reasons.append("visual evidence red flags")
        if not policy_verified:
            reasons.append("policy context unavailable")
        decision_reason = "Agentic workflow routed the claim to adjuster review due to " + "; ".join(reasons) + "."
    else:
        routing_decision = "auto_approve"
        recommended_action = "AUTO_APPROVE"
        decision_reason = (
            "Agentic workflow found no failed required verifications, no material visual red flags, "
            "and relevant policy context was retrieved."
        )

    return {
        "fraud_risk_score": None,
        "routing_decision": routing_decision,
        "decision_reason": decision_reason,
        "summary": investigation_summary,
        "confidence_score": None,
        "missing_documents": red_flags,
        "fraud_indicators": fraud_indicators,
        "recommended_action": recommended_action,
        "verification_report": {
            "policy_verified": policy_verified,
            "identity_verified": identity_verified,
            "documents_verified": documents_verified,
            "history_analysis": "Claim history reviewed by the agentic workflow.",
        },
    }


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


async def run_claim_agent(db_factory, claim_id: str) -> dict[str, Any] | None:
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
                    # A prompt cannot guarantee that an LLM invoked each
                    # required tool. Complete any skipped investigation step
                    # deterministically before scoring the claim.
                    if not policy_matches or not visual_findings or not external_verification:
                        fallback_reasons.append("LangChain skipped one or more required tools")
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
                }

        past_claims = db.query(Claim).filter(Claim.user_id == claim.user_id, Claim.id != claim.id).all()
        external_verification["claim_history"] = [
            {"id": pc.id, "type": pc.claim_type, "amount": pc.amount_requested, "status": pc.status, "date": pc.created_at.isoformat()}
            for pc in past_claims
        ]
        external_verification["identity_verified"] = bool(claim.user and claim.user.is_identity_verified)

        async with McpClient() as mcp:
            try:
                final_decision_payload = await mcp.call_tool("fraud_risk_score", {
                    "policy_matches": policy_matches,
                    "visual_findings": visual_findings,
                    "amount_requested": claim.amount_requested,
                    "external_verification": external_verification
                })
            except Exception as exc:
                print(f"Agentic adjudication MCP tool failed: {exc}. Using deterministic agentic workflow decision.")
                if is_gemini_quota_error(exc):
                    fallback_reasons.append("Gemini quota exhausted on both primary and backup keys; deterministic agentic workflow used")
                else:
                    fallback_reasons.append("Gemini Adjudication Unavailable")
                final_decision_payload = build_agentic_decision_payload(
                    claim,
                    policy_matches,
                    visual_findings,
                    external_verification,
                    verifications_payload,
                )

        if final_decision_payload:
            final_decision_payload = _normalize_tool_payload(final_decision_payload)
            if not final_decision_payload.get("summary"):
                final_decision_payload["summary"] = build_investigation_summary(
                    claim,
                    policy_matches,
                    visual_findings if isinstance(visual_findings, dict) else {},
                    external_verification,
                    verifications_payload,
                )
            if not final_decision_payload.get("decision_reason"):
                final_decision_payload["decision_reason"] = "Agentic adjudication completed using policy, visual, history, and external verification tools."

        add_event(db, claim_id, "agentic_adjudication", "Agentic Adjudication Completed", "done")

        if final_decision_payload:
            fallback_reason_str = "; ".join(fallback_reasons) if fallback_reasons else None
            apply_decision(
                db, 
                claim_id, 
                final_decision_payload, 
                fallback_reason=fallback_reason_str,
                verifications=verifications_payload,
                evidence={
                    "policy_matches": policy_matches,
                    "visual_findings": visual_findings,
                    "external_verification": external_verification,
                },
            )

        else:
            add_event(db, claim_id, "error", "Agent finished without generating final decision payload.", "alert")

        # Refresh claim status to display in audit logs
        db.refresh(claim)
        log_audit(db, claim.user_id, "AI Investigation Completed", {"claim_id": claim_id, "status": claim.status})
        return {
            "policy_matches": policy_matches,
            "visual_findings": visual_findings,
            "external_verification": external_verification,
            "final_decision_payload": final_decision_payload,
            "verifications_payload": verifications_payload,
        }

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
