from langsmith import traceable
import logging
from uuid import uuid4

from langchain_core.documents import Document
from qdrant_client import QdrantClient, models
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    ScoredPoint,
    UpdateStatus,
    VectorParams,
)

from .config import config

logger = logging.getLogger(__name__)


client = QdrantClient(url=config.qdrant.url)


vector_config = {
    "openai-dense": VectorParams(
        size=config.qdrant.vector_size,
        distance=Distance[config.qdrant.distance.upper()],
    ),
}


def create_collection():
    if not client.collection_exists(config.qdrant.collection_name):
        client.create_collection(
            collection_name=config.qdrant.collection_name,
            vectors_config=vector_config,
            on_disk_payload=True,
            sparse_vectors_config={"bm25": models.SparseVectorParams(modifier=models.Modifier.IDF)},
        )

        client.create_payload_index(
            collection_name=config.qdrant.collection_name,
            field_name="category",
            field_schema=PayloadSchemaType.KEYWORD,
        )

        client.create_payload_index(
            collection_name=config.qdrant.collection_name,
            field_name="date",
            field_schema=PayloadSchemaType.DATETIME,
        )

        client.create_payload_index(
            collection_name=config.qdrant.collection_name,
            field_name="source",
            field_schema=PayloadSchemaType.KEYWORD,
        )


create_collection()


def upsert(
    chunks: list[Document],
    dense_vectors: list[list[float]],
    bm25_vectors: list,
) -> bool:
    logger.info(f"Upserting {len(chunks)} points to {config.qdrant.collection_name}")
    points = [
        PointStruct(
            id=uuid4().hex,
            vector={
                "openai-dense": dense,
                "bm25": models.SparseVector(indices=bm25.indices.tolist(), values=bm25.values.tolist()),
            },
            payload=doc.metadata | {"text": doc.page_content},
        )
        for dense, bm25, doc in zip(dense_vectors, bm25_vectors, chunks)
    ]
    result = client.upsert(
        collection_name=config.qdrant.collection_name,
        wait=True,
        points=points,
    )
    if result.status == UpdateStatus.COMPLETED:
        return True

    return False


@traceable(name="rag_search")
def search(
    dense_vector: list[float],
    bm25_vector: models.SparseVector,
    k: int,
    filters: dict | None = None,
) -> list[ScoredPoint]:
    query_filter = None
    if filters:
        conditions = [FieldCondition(key=key, match=MatchValue(value=val)) for key, val in filters.items()]
        query_filter = Filter(must=conditions)

    result = client.query_points(
        collection_name=config.qdrant.collection_name,
        prefetch=[
            models.Prefetch(query=dense_vector, using="openai-dense", limit=k * 4),
            models.Prefetch(query=bm25_vector, using="bm25", limit=k * 4),
        ],
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        limit=k,
        query_filter=query_filter,
    )

    return result.points
