import asyncio
import base64
import json
import re
import sys
import time
import urllib.parse
import xml.etree.ElementTree as ET
from typing import Any

import requests

from app.config import get_settings
from app.rag import search_policy


TOOLS = [
    {
        "name": "policy_rag_search",
        "description": "Search insurance policy clauses and routing rules in Qdrant.",
        "inputSchema": {
            "type": "object",
            "properties": {"query": {"type": "string"}, "limit": {"type": "integer", "default": 3}},
            "required": ["query"],
        },
    },
    {
        "name": "visual_damage_assessment",
        "description": "Use a multimodal model to inspect claim image URLs for damage consistency.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "claim_description": {"type": "string"},
                "image_urls": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["claim_description", "image_urls"],
        },
    },
    {
        "name": "verify_external_facts",
        "description": "Call live APIs to verify location, weather (Open-Meteo), disasters (GDACS), flights (OpenSky), and vehicle VINs (NHTSA).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "claim_type": {"type": "string"},
                "description": {"type": "string"},
                "incident_date": {"type": "string"},
                "location": {"type": "string"},
                "policy_number": {"type": "string"}
            },
            "required": ["claim_type", "description", "incident_date", "location", "policy_number"]
        }
    },
    {
        "name": "fraud_risk_score",
        "description": "Calculate a transparent fraud score from policy evidence, visual findings, and external verification reports.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "policy_matches": {"type": "array"},
                "visual_findings": {"type": "object"},
                "amount_requested": {"type": "number"},
                "external_verification": {"type": "object"}
            },
            "required": ["policy_matches", "visual_findings", "amount_requested", "external_verification"],
        },
    },
]


def text_result(request_id: int, payload: Any) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {"content": [{"type": "text", "text": json.dumps(payload)}]},
    }


def _is_gemini_rate_limited(exc: requests.HTTPError) -> bool:
    response = exc.response
    return bool(response and (response.status_code == 429 or "ResourceExhausted" in response.text))


def gemini_generate(payload: dict[str, Any], timeout: int = 60) -> requests.Response:
    """Call Gemini, trying the backup key once only for a quota/rate-limit response."""
    settings = get_settings()
    api_keys = [settings.gemini_api_key]
    if settings.gemini_backup_api_key and settings.gemini_backup_api_key != settings.gemini_api_key:
        api_keys.append(settings.gemini_backup_api_key)

    last_error: Exception | None = None
    for index, api_key in enumerate(api_keys):
        if not api_key:
            continue
        endpoint = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{settings.gemini_model}:generateContent?key={api_key}"
        )
        try:
            response = requests.post(endpoint, json=payload, timeout=timeout)
            response.raise_for_status()
            if index:
                print("Gemini primary key rate-limited; backup key succeeded.", file=sys.stderr)
            return response
        except requests.HTTPError as exc:
            last_error = exc
            if _is_gemini_rate_limited(exc) and index < len(api_keys) - 1:
                print("Gemini primary key rate-limited; retrying with backup key.", file=sys.stderr)
                continue
            if _is_gemini_rate_limited(exc) and index:
                raise RuntimeError("Gemini backup key was also rate-limited (429).") from exc
            raise
        except requests.RequestException as exc:
            last_error = exc
            raise
    raise RuntimeError("No Gemini API key is configured.") from last_error


def assess_visual_damage(claim_description: str, image_urls: list[str]) -> dict[str, Any]:
    settings = get_settings()
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is required for visual_damage_assessment")

    parts: list[dict[str, Any]] = [
        {
            "text": (
                "Inspect these claim images. Return compact JSON with keys: "
                "damage_summary, consistency, red_flags, confidence. "
                "Return only valid JSON, no markdown. "
                f"Claim description: {claim_description}"
            ),
        }
    ]
    for url in image_urls:
        response = requests.get(url, timeout=20)
        response.raise_for_status()
        mime_type = response.headers.get("content-type", "image/jpeg").split(";")[0]
        parts.append(
            {
                "inline_data": {
                    "mime_type": mime_type,
                    "data": base64.b64encode(response.content).decode("utf-8"),
                }
            }
        )

    import time
    max_retries = 5
    for attempt in range(max_retries):
        try:
            response = gemini_generate({"contents": [{"parts": parts}]})
            break
        except (requests.HTTPError, requests.RequestException) as exc:
            # Check if this is a transient server error (500, 502, 503, 504)
            is_transient = False
            if isinstance(exc, requests.HTTPError) and exc.response is not None:
                if exc.response.status_code in [500, 502, 503, 504]:
                    is_transient = True
            else:
                is_transient = True # Network timeouts, DNS issues are transient
                
            if attempt == max_retries - 1 or not is_transient:
                raise
            time.sleep(2 ** attempt)

    payload = response.json()
    text = payload["candidates"][0]["content"]["parts"][0]["text"]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def query_osm_location(location_name: str) -> dict[str, Any]:
    import urllib.parse
    url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(location_name)}&format=json&countrycodes=in&limit=1"
    try:
        r = requests.get(url, headers=HTTP_HEADERS, timeout=15)
        r.raise_for_status()
        res = r.json()
        if res:
            return {
                "name": res[0].get("display_name"),
                "lat": float(res[0].get("lat")),
                "lon": float(res[0].get("lon")),
                "valid": True
            }
    except Exception:
        pass
    return {"name": location_name, "lat": None, "lon": None, "valid": False}


def query_open_meteo(lat: float, lon: float, date_str: str) -> dict[str, Any]:
    url = f"https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}&start_date={date_str}&end_date={date_str}&daily=rain_sum,wind_speed_10m_max&timezone=auto"
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        res = r.json()
        daily = res.get("daily", {})
        rain = daily.get("rain_sum", [0])[0] or 0
        wind = daily.get("wind_speed_10m_max", [0])[0] or 0
        return {
            "rain_mm": rain,
            "wind_kmh": wind,
            "weather_verified": True
        }
    except Exception:
        pass
    return {"rain_mm": 0, "wind_kmh": 0, "weather_verified": False}


HTTP_HEADERS = {"User-Agent": "AutonomousClaimsAgent/1.0 (insurance-verification)"}

PUBLIC_EVENT_KEYWORDS = (
    "protest", "strike", "riot", "rally", "festival", "celebration",
    "demonstration", "curfew", "lockdown", "mob", "gathering",
)

KNOWN_CLAIM_CITIES = {
    "mumbai": ("mumbai", "bombay"),
    "bengaluru": ("bengaluru", "bangalore"),
    "delhi": ("delhi", "new delhi"),
    "chennai": ("chennai", "madras"),
    "kolkata": ("kolkata", "calcutta"),
    "hyderabad": ("hyderabad",),
    "pune": ("pune",),
}


def description_location_conflict(description: str, selected_location: str) -> str | None:
    """Return the city named in the description when it conflicts with the selected location."""
    description_lower = description.lower()
    selected_lower = selected_location.lower()
    for city, aliases in KNOWN_CLAIM_CITIES.items():
        if any(alias in description_lower for alias in aliases) and not any(alias in selected_lower for alias in aliases):
            return city.title()
    return None


def _is_public_event_claim(description: str) -> bool:
    desc_lower = description.lower()
    return any(keyword in desc_lower for keyword in PUBLIC_EVENT_KEYWORDS)


def query_gdacs(date_str: str, resolved_location: str = "") -> dict[str, Any]:
    import datetime

    try:
        incident = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        incident = datetime.date.today()

    start = (incident - datetime.timedelta(days=7)).isoformat()
    end = (incident + datetime.timedelta(days=1)).isoformat()
    url = (
        "https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH"
        f"?fromdate={start}&todate={end}&alertlevel=Green;Orange;Red"
    )
    try:
        r = requests.get(url, timeout=30, headers=HTTP_HEADERS)
        r.raise_for_status()
        res = r.json()
        features = res.get("features", [])
        # The GDACS search endpoint is global. Restrict results to the claim's
        # country so unrelated worldwide alerts never influence this claim.
        location_parts = [part.strip().lower() for part in resolved_location.split(",") if part.strip()]
        target_country = location_parts[-1] if location_parts else "india"
        disasters = []
        for feature in features:
            props = feature.get("properties", {})
            name = props.get("name") or props.get("htmldescription") or "Unknown event"
            event_type = props.get("eventtype", "")
            alert_level = props.get("alertlevel", "")
            country = props.get("country", "")
            if target_country not in country.lower():
                continue
            disasters.append(f"{name} ({event_type}) - Alert: {alert_level}, Country: {country}")
        return {
            "disasters_active": disasters[:5],
            "disaster_verified": True,
            "source": "GDACS GeoRSS Feed",
            "details": f"GDACS alerts filtered to {target_country.title()}.",
        }
    except Exception as exc:
        print(f"GDACS query failed: {exc}", file=sys.stderr)
    # GDACS can occasionally reject historical queries or be temporarily down.
    # ReliefWeb is an independent humanitarian-disaster catalogue.
    settings = get_settings()
    app_name = settings.reliefweb_app_name or "claims_agent_app"

    try:
        response = requests.get(
            "https://api.reliefweb.int/v2/disasters",
            params={"appname": app_name, "limit": 20},
            timeout=20,
            headers=HTTP_HEADERS,
        )
        response.raise_for_status()
        records = response.json().get("data", [])
        disasters = []
        for record in records:
            fields = record.get("fields", {})
            name = fields.get("name") or record.get("id")
            if name:
                disasters.append(str(name))
        return {
            "disasters_active": disasters[:5],
            "disaster_verified": True,
            "source": "ReliefWeb Disasters API (GDACS fallback)",
            "fallback_used": True,
        }
    except Exception as exc:
        print(f"ReliefWeb disaster fallback failed: {exc}", file=sys.stderr)
        return {
            "disasters_active": [],
            "disaster_verified": False,
            "available": False,
            "source": "GDACS / ReliefWeb",
            "details": "Both disaster verification providers were unavailable.",
        }


def query_nhtsa_vin(vin: str) -> dict[str, Any]:
    url = f"https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValues/{vin}?format=json"
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        res = r.json()
        results = res.get("Results", [{}])[0]
        make = results.get("Make")
        model = results.get("Model")
        year = results.get("ModelYear")
        if make and model:
            return {
                "make": make,
                "model": model,
                "year": year,
                "vin_valid": True
            }
    except Exception:
        pass
    return {"make": None, "model": None, "year": None, "vin_valid": False}


def query_opensky_flight(airport_icao: str, date_str: str) -> dict[str, Any]:
    import datetime
    try:
        dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        epoch_start = int(dt.timestamp())
        epoch_end = epoch_start + 86400
        url = f"https://opensky-network.org/api/flights/arrival?airport={airport_icao}&begin={epoch_start}&end={epoch_end}"
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        flights = r.json() or []
        return {
            "flight_count_verified": len(flights),
            "flight_verified": True
        }
    except Exception:
        pass
    return {"flight_count_verified": 0, "flight_verified": False}


def extract_city(description: str) -> str:
    settings = get_settings()
    prompt = (
        "Identify the primary city or location in India mentioned in this insurance claim description. "
        "Return ONLY the city name (e.g. 'Mumbai', 'Bengaluru', 'Chennai', 'Delhi'). "
        "Do not include any other text, punctuation, or markdown. If no location is mentioned, return 'India'.\n"
        f"Description: {description}"
    )
    try:
        r = gemini_generate({"contents": [{"parts": [{"text": prompt}]}]}, timeout=15)
        city = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        city = re.sub(r'[^a-zA-Z\s]', '', city).strip()
        return city if city else "Delhi"
    except Exception:
        return "Delhi"


def query_event_verification(resolved_location: str, date_str: str, description: str) -> dict[str, Any]:
    if not _is_public_event_claim(description):
        return {
            "event_verified": True,
            "details": "No public gathering or community-wide event mentioned in the claim description.",
            "source": "Rule-based verification",
        }

    keywords = ["protest", "strike", "riot", "vandalism", "accident", "fire", "flood", "disaster", "rally", "festival", "celebration"]
    matched_keywords = [w for w in keywords if w in description.lower()]
    
    query_parts = [resolved_location]
    if matched_keywords:
        query_parts.append(matched_keywords[0])
    else:
        query_parts.append("incident")
        
    query = " ".join(query_parts)
    rss_url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl=en-IN&gl=IN&ceid=IN:en"
    headlines = []
    
    try:
        r = requests.get(rss_url, timeout=10, headers=HTTP_HEADERS)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        for item in root.findall(".//item")[:10]:
            title_el = item.find("title")
            if title_el is not None and title_el.text:
                headlines.append(title_el.text)
    except Exception as exc:
        print(f"Failed to fetch or parse news RSS: {exc}", file=sys.stderr)

    settings = get_settings()
    if not settings.gemini_api_key:
        return {
            "event_verified": True,
            "details": "Public event mentioned but Gemini unavailable; default verification passed.",
            "source": "Rule-based verification",
        }
        
    prompt = (
        "You are an AI insurance claim event verification assistant.\n"
        "Your task is to verify if the event described in the claim (e.g. protests, riots, public celebrations, strikes) actually occurred at the specified location and date.\n"
        "You MUST rely on the provided list of news headlines as your primary source of truth. Do not make up facts.\n"
        f"Location: {resolved_location}\n"
        f"Date: {date_str}\n"
        f"Claim Description: {description}\n"
        f"News Headlines fetched: {json.dumps(headlines)}\n\n"
        "Instructions:\n"
        "1. If the claim description does NOT mention any public gathering, crowd event, protest, riot, strike, or community-wide event (e.g., it is a simple private car accident, private kitchen fire, or isolated shop break-in/vandalism not attributed to public events), set 'event_verified' to true and explain that no public event check was required.\n"
        "2. If a public event (e.g. protests, riots, strikes, festivals) IS mentioned, check if the news headlines corroborate that this event happened at this location on or around that date.\n"
        "3. If no matching news reports are found in the headlines, set 'event_verified' to false and explain that no public reports of this event were found in the news search.\n"
        "4. If the headlines verify the event, set 'event_verified' to true with details.\n\n"
        "Return ONLY a valid JSON object with these exact keys:\n"
        "{\n"
        '  "event_verified": true/false,\n'
        '  "details": "Explanation of verification results..."\n'
        "}"
    )
    
    try:
        r = gemini_generate({"contents": [{"parts": [{"text": prompt}]}]}, timeout=15)
        res_text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        try:
            parsed = json.loads(res_text)
        except Exception:
            match = re.search(r"\{.*\}", res_text, re.DOTALL)
            parsed = json.loads(match.group(0)) if match else {"event_verified": True, "details": "Verification parsed failed"}
        return {
            "event_verified": bool(parsed.get("event_verified", True)),
            "details": str(parsed.get("details", "Verification completed.")),
            "source": "Google News RSS via Gemini Adjudication"
        }
    except Exception as exc:
        if headlines:
            return {
                "event_verified": False,
                "available": False,
                "details": (
                    f"News search returned {len(headlines)} headline(s) for {resolved_location}. "
                    "AI adjudication was unavailable, so the headlines were not treated as verified corroboration."
                ),
                "source": "Google News RSS",
            }
        return {
            "event_verified": False,
            "available": False,
            "details": f"Event verification service failed: {str(exc)}",
            "source": "Google News RSS via Gemini Adjudication",
        }


def perform_verification(claim_type: str, description: str, incident_date: str, location: str, policy_number: str) -> dict[str, Any]:
    resolved_location = (location or "").strip() or extract_city(description)
    description_city = description_location_conflict(description, resolved_location)
    # 1. Geocode location via Nominatim
    geo = query_osm_location(resolved_location)
    
    # 2. Query Weather via Open-Meteo if location is valid
    weather = {}
    if geo["valid"] and geo["lat"] and geo["lon"] and incident_date:
        weather = query_open_meteo(geo["lat"], geo["lon"], incident_date)
        
    # 3. Query Disasters via GDACS
    disasters = query_gdacs(incident_date, geo.get("name") or resolved_location)
    
    # 4. Query NHTSA if auto claim with 17-char VIN/chassis number
    vehicle = {}
    cleaned_vin = re.sub(r'[^A-Z0-9]', '', policy_number.upper())
    if len(cleaned_vin) == 17:
        vehicle = query_nhtsa_vin(cleaned_vin)
        
    # 5. Query OpenSky flights if airport ICAO resolved
    flights = {}
    # Expanded mapping of major commercial airports across PAN India
    airport_map = {
        "DEL": "VIDP", "DELHI": "VIDP", "IGI": "VIDP",
        "BOM": "VABB", "MUMBAI": "VABB", "CHHATRAPATI": "VABB",
        "BLR": "VOBL", "BENGALURU": "VOBL", "BANGALORE": "VOBL", "KEMPEGOWDA": "VOBL",
        "MAA": "VOMM", "CHENNAI": "VOMM", "MEENAMBAKKAM": "VOMM",
        "CCU": "VECC", "KOLKATA": "VECC", "CALCUTTA": "VECC", "DUM": "VECC",
        "HYD": "VOHS", "HYDERABAD": "VOHS", "SHAMSHABAD": "VOHS", "RAJIV": "VOHS",
        "PNQ": "VAPO", "PUNE": "VAPO",
        "AMD": "VAAH", "AHMEDABAD": "VAAH",
        "COK": "VOCI", "KOCHI": "VOCI", "COCHIN": "VOCI",
        "GOI": "VAGO", "GOA": "VAGO", "DABOLIM": "VAGO",
        "GOX": "VOGA", "MOPA": "VOGA",
        "JAI": "VIJP", "JAIPUR": "VIJP",
        "LKO": "VILK", "LUCKNOW": "VILK",
        "GAU": "VEGT", "GUWAHATI": "VEGT",
        "TRV": "VOTV", "TRIVANDRUM": "VOTV", "THIRUVANANTHAPURAM": "VOTV",
        "CJB": "VOCB", "COIMBATORE": "VOCB",
        "IXE": "VOML", "MANGALURU": "VOML", "MANGLORE": "VOML",
        "CCJ": "VOCL", "KOZHIKODE": "VOCL", "CALICUT": "VOCL",
        "TRZ": "VOTR", "TIRUCHIRAPPALLI": "VOTR", "TRICHY": "VOTR",
        "ATQ": "VIAR", "AMRITSAR": "VIAR",
        "SXR": "VISR", "SRINAGAR": "VISR",
        "IXJ": "VIJU", "JAMMU": "VIJU",
        "DED": "VIDN", "DEHRADUN": "VIDN",
        "PAT": "VEPT", "PATNA": "VEPT",
        "BBI": "VEBS", "BHUBANESWAR": "VEBS", "BHUBANESHWAR": "VEBS",
        "IXR": "VERC", "RANCHI": "VERC",
        "RPR": "VARP", "RAIPUR": "VARP",
        "NAG": "VANP", "NAGPUR": "VANP",
        "IDR": "VAID", "INDORE": "VAID",
        "BHO": "VABP", "BHOPAL": "VABP",
        "BDQ": "VABO", "VADODARA": "VABO", "BARODA": "VABO",
        "STV": "VASU", "SURAT": "VASU",
        "RAJ": "VARK", "RAJKOT": "VARK",
        "VTZ": "VEVZ", "VISAKHAPATNAM": "VEVZ", "VIZAG": "VEVZ",
        "VGA": "VOBZ", "VIJAYAWADA": "VOBZ",
        "TIR": "VOTP", "TIRUPATI": "VOTP",
        "IXM": "VOMD", "MADURAI": "VOMD",
        "IXC": "VICG", "CHANDIGARH": "VICG",
        "UDR": "VAUD", "UDAIPUR": "VAUD",
        "JDH": "VIJO", "JODHPUR": "VIJO",
        "JSA": "VIJR", "JAISALMER": "VIJR",
        "VNS": "VEIB", "VARANASI": "VEIB",
        "IXB": "VEBD", "BAGDOGRA": "VEBD",
        "IMF": "VEIM", "IMPHAL": "VEIM",
        "IXA": "VEAT", "AGARTALA": "VEAT",
        "IXZ": "VOPB", "PORT": "VOPB"
    }
    icao = None
    for k, v in airport_map.items():
        if k in resolved_location.upper() or k in description.upper():
            icao = v
            break
    if icao and incident_date:
        flights = query_opensky_flight(icao, incident_date)
        
    events = query_event_verification(resolved_location, incident_date, description)
        
    result = {
        "location_verification": geo,
        "weather_verification": weather,
        "disaster_verification": disasters,
        "vehicle_verification": vehicle,
        "flight_verification": flights,
        "event_verification": events
    }
    if description_city:
        result["location_conflict"] = {
            "description_city": description_city,
            "selected_location": resolved_location,
        }
    return result


def calculate_score(policy_matches: list[dict], visual_findings: dict, amount_requested: float, external_verification: dict) -> dict[str, Any]:
    settings = get_settings()
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is required for fraud_risk_score")

    prompt = (
        "You are an insurance claims AI adjuster. Evaluate this claim and return a compact JSON object. "
        "Calculate a risk score (0-100). If the risk score is 0-30, routing_decision must be 'auto_approve'. "
        "If the risk score is 31-100, routing_decision must be 'investigate'. "
        "\nAll currency details must be in Indian Rupees (INR, ₹). Make sure the decision_reason, summary, and recommended_action refer to ₹ / INR instead of dollars ($).\n"
        "\nReturn ONLY valid JSON with these exact keys:\n"
        "{\n"
        '  "summary": "Concise claim summary...",\n'
        '  "extracted_info": {"Key": "Value", ...},\n'
        '  "fraud_risk_score": 45,\n'
        '  "routing_decision": "investigate",\n'
        '  "decision_reason": "Detailed explanation of decision...",\n'
        '  "confidence_score": 0.85,\n'
        '  "missing_documents": ["document1", ...],\n'
        '  "fraud_indicators": ["red flag 1", ...],\n'
        '  "recommended_action": "Recommended next action...",\n'
        '  "verification_report": {"policy_verified": true, "identity_verified": true, "documents_verified": true, "history_analysis": "Duplicate claim analysis details..."}\n'
        "}\n\n"
        f"Input Data:\n"
        f"- Policy Matches: {json.dumps(policy_matches)}\n"
        f"- Visual Findings: {json.dumps(visual_findings)}\n"
        f"- Amount Requested (in INR): ₹{amount_requested}\n"
        f"- Live External API Verifications: {json.dumps(external_verification)}\n"
        f"- Independent Fraud ML Service Probability Score: {external_verification.get('ml_fraud_probability', 'N/A')}\n"
    )

    max_retries = 5
    for attempt in range(max_retries):
        try:
            response = gemini_generate({"contents": [{"parts": [{"text": prompt}]}]})
            break
        except (requests.HTTPError, requests.RequestException) as exc:
            is_transient = False
            if isinstance(exc, requests.HTTPError) and exc.response is not None:
                if exc.response.status_code in [500, 502, 503, 504]:
                    is_transient = True
            else:
                is_transient = True
            if attempt == max_retries - 1 or not is_transient:
                raise
            time.sleep(2 ** attempt)

    payload = response.json()
    text = payload["candidates"][0]["content"]["parts"][0]["text"]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


async def handle(request: dict[str, Any]) -> dict[str, Any]:
    request_id = request.get("id")
    method = request.get("method")
    params = request.get("params") or {}
    if method == "initialize":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"serverInfo": {"name": "claims-mcp-tools", "version": "0.1.0"}, "capabilities": {"tools": {}}}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        name = params["name"]
        args = params.get("arguments") or {}
        if name == "policy_rag_search":
            return text_result(request_id, search_policy(args["query"], args.get("limit", 3)))
        if name == "visual_damage_assessment":
            return text_result(request_id, assess_visual_damage(args["claim_description"], args["image_urls"]))
        if name == "verify_external_facts":
            return text_result(request_id, perform_verification(args["claim_type"], args["description"], args["incident_date"], args["location"], args["policy_number"]))
        if name == "fraud_risk_score":
            return text_result(request_id, calculate_score(args["policy_matches"], args["visual_findings"], args["amount_requested"], args["external_verification"]))
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": f"Unknown method {method}"}}


async def main() -> None:
    while True:
        line = await asyncio.to_thread(sys.stdin.readline)
        if not line:
            break
        try:
            response = await handle(json.loads(line))
        except Exception as exc:
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32000, "message": str(exc)}}
        print(json.dumps(response), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
