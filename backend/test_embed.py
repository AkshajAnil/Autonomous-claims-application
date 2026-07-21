from llama_index.embeddings.gemini import GeminiEmbedding
from app.config import get_settings

settings = get_settings()

def test_model(model_name):
    print(f"Testing model: '{model_name}'")
    try:
        embed_model = GeminiEmbedding(model_name=model_name, api_key=settings.gemini_api_key)
        res = embed_model.get_text_embedding("test query")
        print(f"  [OK] Success! Vector dimension: {len(res)}")
        return True
    except Exception as e:
        print(f"  [FAIL] Failed: {e}")
        return False

if __name__ == "__main__":
    test_model("models/text-embedding-004")
    test_model("text-embedding-004")
    test_model("models/embedding-001")
    test_model("embedding-001")
