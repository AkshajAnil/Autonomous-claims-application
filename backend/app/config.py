from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = Field(alias="DATABASE_URL")

    s3_endpoint: str = Field(default="", alias="S3_ENDPOINT")
    s3_access_key: str = Field(default="", alias="S3_ACCESS_KEY")
    s3_secret_key: str = Field(default="", alias="S3_SECRET_KEY")
    s3_bucket: str = Field(default="", alias="S3_BUCKET")
    s3_secure: bool = Field(default=False, alias="S3_SECURE")

    qdrant_url: str = Field(default="http://localhost:6333", alias="QDRANT_URL")
    qdrant_api_key: str = Field(default="", alias="QDRANT_API_KEY")
    qdrant_collection: str = Field(default="claim_policies", alias="QDRANT_COLLECTION")

    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    gemini_backup_api_key: str = Field(default="", alias="GEMINI_BACKUP_API_KEY")
    gemini_model: str = Field(default="gemini-1.5-flash", alias="GEMINI_MODEL")
    reliefweb_app_name: str = Field(default="", alias="RELIEFWEB_APP_NAME")

    investigation_version: str = Field(default="v1.0", alias="INVESTIGATION_VERSION")

    cors_origins: str = Field(default="*", alias="CORS_ORIGINS")

    jwt_secret: str = Field(default="supersecretkey", alias="JWT_SECRET")
    jwt_expiration_minutes: int = Field(default=60, alias="JWT_EXPIRATION_MINUTES")
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


FEATURE_SCHEMA_VERSION = "v1.0"
RISK_RULES_VERSION = "v1.0"
WORKFLOW_VERSION = "v1.0"

RISK_RULES_CONFIG = {
    # 1. Identity Rules
    "identity_verified": {"category": "Identity", "score": 15, "description": "Identity verified via official document/KYC"},
    "face_match": {"category": "Identity", "score": 10, "description": "Biometric face match successfully confirmed"},
    "liveness_passed": {"category": "Identity", "score": 10, "description": "Liveness check passed"},
    "identity_not_verified": {"category": "Identity", "score": -30, "description": "Identity documentation missing or unverified"},
    "identity_mismatch": {"category": "Identity", "score": -40, "description": "Claimant details mismatch identity record"},

    # 2. Policy Rules
    "policy_active": {"category": "Policy", "score": 10, "description": "Policy is active and in good standing"},
    "coverage_valid": {"category": "Policy", "score": 10, "description": "Claim event is covered by active policy terms"},
    "policy_expired": {"category": "Policy", "score": -40, "description": "Incident date falls outside active policy coverage window"},
    "policy_newly_purchased": {"category": "Policy", "score": -20, "description": "Policy purchased less than 30 days before incident date"},

    # 3. Location Rules
    "gps_match": {"category": "Location", "score": 10, "description": "Incident GPS coordinates match claim declaration"},
    "address_match": {"category": "Location", "score": 10, "description": "Declared address matches geocoded location"},
    "gps_mismatch": {"category": "Location", "score": -25, "description": "Photo EXIF/GPS metadata contradicts reported location"},
    "impossible_travel": {"category": "Location", "score": -30, "description": "Geographic distance between events indicates impossible travel"},

    # 4. Weather Rules
    "weather_supports": {"category": "Weather", "score": 10, "description": "Historical weather archive confirms reported weather conditions"},
    "weather_contradicts": {"category": "Weather", "score": -25, "description": "Weather archive contradicts claimed weather conditions (e.g. no rain recorded)"},

    # 5. News Verification Rules
    "incident_verified_news": {"category": "News", "score": 10, "description": "Incident confirmed by news sources"},
    "disaster_confirmed": {"category": "News", "score": 10, "description": "Natural disaster or emergency alert confirmed by GDACS/ReliefWeb"},

    # 6. OCR Rules
    "ocr_high": {"category": "OCR", "score": 15, "description": "OCR consistency score >= 95%"},
    "ocr_moderate": {"category": "OCR", "score": 5, "description": "OCR consistency score between 80% and 94%"},
    "ocr_low": {"category": "OCR", "score": -20, "description": "OCR text extraction consistency below 80%"},

    # 7. Image Rules
    "image_authentic": {"category": "Image", "score": 15, "description": "Images verified authentic without digital manipulation"},
    "image_manipulated": {"category": "Image", "score": -25, "description": "Possible digital manipulation or metadata editing detected"},
    "image_duplicate": {"category": "Image", "score": -35, "description": "Duplicate image detected in past claims database"},

    # 8. Document Rules
    "all_docs_present": {"category": "Document", "score": 10, "description": "All required proof documents provided"},
    "missing_docs": {"category": "Document", "score": -15, "description": "One or more required proof documents missing"},
    "fake_doc_suspected": {"category": "Document", "score": -40, "description": "Document authenticity check flagged suspected forgery"},

    # 9. Story Rules
    "story_high": {"category": "Story", "score": 15, "description": "Story consistency score >= 90%"},
    "story_moderate": {"category": "Story", "score": 5, "description": "Story consistency score between 70% and 89%"},
    "story_low": {"category": "Story", "score": -20, "description": "Story description contains internal contradictions (< 70%)"},

    # 10. Financial Rules
    "amount_normal": {"category": "Financial", "score": 10, "description": "Claim amount within normal statistical range for claim type"},
    "exceeds_policy_limit": {"category": "Financial", "score": -40, "description": "Requested amount exceeds maximum policy coverage limit"},
    "extremely_high_amount": {"category": "Financial", "score": -20, "description": "Extremely high claim amount requested"},

    # 11. Timing Rules
    "timely_submission": {"category": "Timing", "score": 5, "description": "Claim submitted within expected reporting timeframe"},
    "long_submission_delay": {"category": "Timing", "score": -10, "description": "Unusual delay between incident date and claim filing date"},
    "sameday_high_value": {"category": "Timing", "score": -15, "description": "High-value claim filed on the exact same day policy took effect"}
}
