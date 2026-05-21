"""Qdrant vector store client for RAG-based glossary lookups."""

import logging

from qdrant_client import QdrantClient, models

from app.config import settings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "military_glossary"
VECTOR_SIZE = 1536  # Matches typical embedding model dimensions


def get_qdrant_client() -> QdrantClient:
    """Get a Qdrant client instance."""
    return QdrantClient(url=settings.qdrant_url)


async def ensure_collection() -> None:
    """Create the glossary collection if it doesn't exist."""
    client = get_qdrant_client()
    collections = client.get_collections().collections
    names = [c.name for c in collections]

    if COLLECTION_NAME not in names:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=models.VectorParams(
                size=VECTOR_SIZE,
                distance=models.Distance.COSINE,
            ),
        )
        logger.info(f"Created Qdrant collection: {COLLECTION_NAME}")


async def search_glossary(query_vector: list[float], limit: int = 5) -> list[dict]:
    """Search the glossary for similar terms."""
    client = get_qdrant_client()

    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=limit,
    )

    return [
        {
            "term": hit.payload.get("term", ""),
            "translation": hit.payload.get("translation", ""),
            "score": hit.score,
        }
        for hit in results.points
    ]
