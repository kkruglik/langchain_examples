import logging

from qdrant_client import models
from qdrant_client.models import ScoredPoint
from langsmith import traceable

from .embedders import bm25_embedding_model, dense_embeddings
from .reranker import rerank
from .vdb import search

logger = logging.getLogger(__name__)


@traceable(name="rag_query")
def rag_query(text: str, k: int = 5, filters: dict | None = None) -> list[ScoredPoint]:
    dense_vector = dense_embeddings.embed_query(text)
    bm25_vector = next(bm25_embedding_model.query_embed(text))
    bm25_sparse = models.SparseVector(
        indices=bm25_vector.indices.tolist(),
        values=bm25_vector.values.tolist(),
    )

    candidates = search(dense_vector, bm25_sparse, k=k * 4, filters=filters)
    return rerank(text, candidates, top_n=k)
