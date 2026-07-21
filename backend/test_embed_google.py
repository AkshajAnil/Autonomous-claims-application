import requests
from app.config import get_settings

settings = get_settings()

def test_google_embed(api_version, model_name):
    print(f"Testing direct HTTP embed for: {api_version}/{model_name}")
    try:
        payload = {
            "model": model_name,
            "content": {"parts": [{"text": "Hello world"}]}
        }
        endpoint = f"https://generativelanguage.googleapis.com/{api_version}/{model_name}:embedContent?key={settings.gemini_api_key}"
        response = requests.post(endpoint, json=payload, timeout=20)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            res_json = response.json()
            print(f"  [OK] Success! Vector length: {len(res_json['embedding']['values'])}")
            return True
        else:
            print(f"  [FAIL] Response: {response.text}")
            return False
    except Exception as e:
        print(f"  [FAIL] Error: {e}")
        return False

if __name__ == "__main__":
    test_google_embed("v1", "models/text-embedding-004")
    test_google_embed("v1", "models/embedding-001")
    test_google_embed("v1beta", "models/text-embedding-004")
