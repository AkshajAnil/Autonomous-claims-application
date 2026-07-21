from app.config import get_settings
from app.policies import POLICY_DOCUMENTS

try:
    from qdrant_client import QdrantClient
    from llama_index.core import Document, StorageContext, VectorStoreIndex
    from llama_index.core.node_parser import SentenceSplitter
    from llama_index.embeddings.gemini import GeminiEmbedding
    from llama_index.vector_stores.qdrant import QdrantVectorStore
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False


def get_qdrant():
    if not QDRANT_AVAILABLE:
        return None
    settings = get_settings()
    try:
        return QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None)
    except Exception:
        return None


def seed_policy_collection() -> None:
    if not QDRANT_AVAILABLE:
        return
    settings = get_settings()
    client = get_qdrant()
    if client is None:
        return
    
    try:
        collections = {item.name for item in client.get_collections().collections}
        if settings.qdrant_collection in collections:
            client.delete_collection(settings.qdrant_collection)
            
        documents = [
            Document(
                text=doc["text"],
                doc_id=doc["id"],
                metadata={"policy_id": doc["id"]},
                excluded_embed_metadata_keys=["policy_id"],
                excluded_llm_metadata_keys=["policy_id"]
            )
            for doc in POLICY_DOCUMENTS
        ]
        
        embed_model = GeminiEmbedding(
            model_name="models/gemini-embedding-001", 
            api_key=settings.gemini_api_key
        )
        
        parser = SentenceSplitter(chunk_size=512, chunk_overlap=20)
        nodes = parser.get_nodes_from_documents(documents)
        
        vector_store = QdrantVectorStore(client=client, collection_name=settings.qdrant_collection)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        
        VectorStoreIndex(
            nodes,
            storage_context=storage_context,
            embed_model=embed_model
        )
    except Exception:
        pass


def search_policy(query: str, limit: int = 3) -> list[dict]:
    if QDRANT_AVAILABLE:
        try:
            settings = get_settings()
            seed_policy_collection()
            
            client = get_qdrant()
            if client is not None:
                vector_store = QdrantVectorStore(client=client, collection_name=settings.qdrant_collection)
                embed_model = GeminiEmbedding(
                    model_name="models/gemini-embedding-001", 
                    api_key=settings.gemini_api_key
                )
                index = VectorStoreIndex.from_vector_store(vector_store, embed_model=embed_model)
                retriever = index.as_retriever(similarity_top_k=limit)
                nodes = retriever.retrieve(query)
                
                return [
                    {
                        "policy_id": ns.node.metadata.get("policy_id"),
                        "text": ns.node.text,
                        "score": ns.score,
                    }
                    for ns in nodes
                ]
        except Exception:
            pass

    # Keyword fallback search when Qdrant is unavailable
    results = []
    query_lower = query.lower()
    for doc in POLICY_DOCUMENTS:
        text_lower = doc["text"].lower()
        score = sum(1 for word in query_lower.split() if word in text_lower)
        if score > 0:
            results.append({
                "policy_id": doc["id"],
                "text": doc["text"][:300] + "...",
                "score": float(score) / 10.0
            })
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:limit] if results else [{"policy_id": "DEFAULT", "text": "Standard policy terms apply.", "score": 0.5}]
