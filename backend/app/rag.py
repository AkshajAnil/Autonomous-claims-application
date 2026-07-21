from qdrant_client import QdrantClient
from llama_index.core import Document, StorageContext, VectorStoreIndex
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.gemini import GeminiEmbedding
from llama_index.vector_stores.qdrant import QdrantVectorStore

from app.config import get_settings
from app.policies import POLICY_DOCUMENTS


def get_qdrant() -> QdrantClient:
    settings = get_settings()
    return QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None)


def seed_policy_collection() -> None:
    settings = get_settings()
    client = get_qdrant()
    
    collections = {item.name for item in client.get_collections().collections}
    if settings.qdrant_collection in collections:
        client.delete_collection(settings.qdrant_collection)
        
    # Create and seed
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
    
    # Setup embedding model using Gemini
    embed_model = GeminiEmbedding(
        model_name="models/gemini-embedding-001", 
        api_key=settings.gemini_api_key
    )
    
    # Set up splitter
    parser = SentenceSplitter(chunk_size=512, chunk_overlap=20)
    nodes = parser.get_nodes_from_documents(documents)
    
    # Setup vector store & storage context
    vector_store = QdrantVectorStore(client=client, collection_name=settings.qdrant_collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    
    # Ingest nodes using VectorStoreIndex
    VectorStoreIndex(
        nodes,
        storage_context=storage_context,
        embed_model=embed_model
    )


def search_policy(query: str, limit: int = 3) -> list[dict]:
    settings = get_settings()
    seed_policy_collection()
    
    client = get_qdrant()
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
