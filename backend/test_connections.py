import sys
import os
import requests
from sqlalchemy import text
from app.config import get_settings
from app.database import engine
from app.storage import get_s3_client
from app.rag import get_qdrant

# Force standard output to handle UTF-8 if possible, but fallback to ASCII strings to be safe
sys.stdout.reconfigure(encoding='utf-8') if hasattr(sys.stdout, 'reconfigure') else None

def test_postgresql():
    print("Testing PostgreSQL connection...")
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1")).fetchone()
            if result and result[0] == 1:
                print("[OK] PostgreSQL: Connection successful!")
                return True
            else:
                print("[FAIL] PostgreSQL: Unexpected result.")
                return False
    except Exception as e:
        print(f"[FAIL] PostgreSQL: Connection failed. Error: {e}")
        return False

def test_minio():
    print("\nTesting MinIO/B2 connection...")
    try:
        settings = get_settings()
        client = get_s3_client()
        exists = client.bucket_exists(settings.s3_bucket)
        print(f"[OK] MinIO: Connection successful! Bucket '{settings.s3_bucket}' exists={exists}")
        return True
    except Exception as e:
        print(f"[FAIL] MinIO: Connection failed. Error: {e}")
        return False

def test_qdrant():
    print("\nTesting Qdrant Cloud connection...")
    try:
        settings = get_settings()
        client = get_qdrant()
        collections = client.get_collections().collections
        names = [col.name for col in collections]
        print(f"[OK] Qdrant: Connection successful! Found collections: {names}")
        return True
    except Exception as e:
        print(f"[FAIL] Qdrant: Connection failed. Error: {e}")
        return False

def test_gemini():
    print("\nTesting Gemini API connection...")
    try:
        settings = get_settings()
        if not settings.gemini_api_key:
            print("[FAIL] Gemini API: GEMINI_API_KEY is not set.")
            return False
        
        # Simple test prompt
        payload = {
            "contents": [{"parts": [{"text": "Say hello in one word."}]}]
        }
        endpoint = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{settings.gemini_model}:generateContent?key={settings.gemini_api_key}"
        )
        response = requests.post(endpoint, json=payload, timeout=20)
        response.raise_for_status()
        res_json = response.json()
        text_resp = res_json["candidates"][0]["content"]["parts"][0]["text"].strip()
        print(f"[OK] Gemini API: Connection successful! Response: '{text_resp}'")
        return True
    except Exception as e:
        print(f"[FAIL] Gemini API: Connection failed. Error: {e}")
        return False

if __name__ == "__main__":
    # Make sure we can import from app
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    
    print("==================================================")
    print("         CLAIMS AGENT CONNECTION TEST             ")
    print("==================================================")
    
    pg_ok = test_postgresql()
    minio_ok = test_minio()
    qdrant_ok = test_qdrant()
    gemini_ok = test_gemini()
    
    print("\n==================================================")
    if pg_ok and minio_ok and qdrant_ok and gemini_ok:
        print("[SUCCESS] ALL SYSTEMS ONLINE!")
        sys.exit(0)
    else:
        print("[WARNING] SOME SYSTEMS OFFLINE. Check errors above.")
        sys.exit(1)
