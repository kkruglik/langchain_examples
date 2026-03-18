from langsmith import traceable
import logging

from sentence_transformers import CrossEncoder
from qdrant_client.models import ScoredPoint

logger = logging.getLogger(__name__)

_model = CrossEncoder("cross-encoder/mmarco-mMiniLMv2-L12-H384-v1")


@traceable(name="rerank", run_type="retriever")
def rerank(query: str, points: list[ScoredPoint], top_n: int = 5) -> list[ScoredPoint]:
    if not points:
        return points
    pairs = [(query, p.payload.get("text", "")) for p in points]
    scores = _model.predict(pairs)
    ranked = sorted(zip(scores, points), key=lambda x: x[0], reverse=True)
    logger.info(f"Reranked {len(points)} candidates -> top {top_n}")
    return [p for _, p in ranked[:top_n]]
