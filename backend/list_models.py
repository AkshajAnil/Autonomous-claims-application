import requests
from app.config import get_settings

settings = get_settings()

def list_models():
    print("Listing available models...")
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models?key={settings.gemini_api_key}"
    try:
        response = requests.get(endpoint, timeout=20)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            models = response.json().get("models", [])
            for m in models:
                # Print models that support embedding or all models
                supported_methods = m.get("supportedGenerationMethods", [])
                name = m.get("name")
                if "embedContent" in supported_methods or "embedText" in name.lower() or "embedding" in name.lower():
                    print(f"  - {name} (Supported methods: {supported_methods})")
        else:
            print(f"Failed response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    list_models()
