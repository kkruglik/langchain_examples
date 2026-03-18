import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from .config import config
from .embedders import apply_dense_embeddings, apply_bm25_embeddings
from .splitters import chunk_text
from .vdb import upsert, article_ingested

logger = logging.getLogger(__name__)


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def rag_pipeline() -> None:
    logs_dir = Path("logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(logs_dir / f"rag_pipeline_{timestamp}.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )

    batch_size = config.batch_size
    collection_path = Path(config.collection_path)

    batch = []
    total_upserted = 0
    total_skipped = 0
    total_added = 0

    for path in collection_path.glob("**/*.json"):
        record = load_json(path)
        url = record["url"]
        if article_ingested(url):
            logger.info("Skipped (already ingested): %s", url)
            total_skipped += 1
            continue

        chunks = chunk_text(record)
        batch.extend(chunks)
        total_added += 1
        logger.info("Queued for ingestion: %s (%d chunks)", url, len(chunks))

        if len(batch) >= batch_size:
            dense_vectors = apply_dense_embeddings(batch[:batch_size])
            bm25_vectors = apply_bm25_embeddings(batch[:batch_size])
            upsert(batch[:batch_size], dense_vectors, bm25_vectors)
            total_upserted += batch_size
            batch = batch[batch_size:]
            logger.info("Upserted %d chunks so far", total_upserted)

    if batch:
        dense_vectors = apply_dense_embeddings(batch)
        bm25_vectors = apply_bm25_embeddings(batch)
        upsert(batch, dense_vectors, bm25_vectors)
        total_upserted += len(batch)

    logger.info(
        "Pipeline done. Added: %d articles, skipped: %d, total chunks upserted: %d",
        total_added,
        total_skipped,
        total_upserted,
    )
