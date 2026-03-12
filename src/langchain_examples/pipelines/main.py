import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from .config import config
from .embedders import apply_dense_embeddings, apply_bm25_embeddings
from .splitters import chunk_text
from .vdb import upsert

logger = logging.getLogger(__name__)

SEEN_FILE = "seen_files.json"


def load_seen(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def save_seen(path: Path, seen: dict) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(seen, f, ensure_ascii=False, indent=2)


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
    seen_path = Path("data/rag/meta") / SEEN_FILE

    seen = load_seen(seen_path)
    batch = []
    total_upserted = 0
    now = datetime.now(timezone.utc).isoformat()

    for path in collection_path.glob("**/*.json"):
        if path.name == SEEN_FILE:
            continue
        if str(path) in seen:
            continue

        record = load_json(path)
        chunks = chunk_text(record)
        batch.extend(chunks)

        seen[str(path)] = now

        if len(batch) >= batch_size:
            dense_vectors = apply_dense_embeddings(batch[:batch_size])
            bm25_vectors = apply_bm25_embeddings(batch[:batch_size])

            upsert(
                batch[:batch_size],
                dense_vectors,
                bm25_vectors,
            )
            total_upserted += batch_size
            batch = batch[batch_size:]
            save_seen(seen_path, seen)
            logger.info("Upserted %d chunks so far", total_upserted)

    if batch:
        dense_vectors = apply_dense_embeddings(batch)
        bm25_vectors = apply_bm25_embeddings(batch)
        upsert(
            batch,
            dense_vectors,
            bm25_vectors,
        )
        total_upserted += len(batch)

    save_seen(seen_path, seen)
    logger.info("Pipeline done. Total chunks upserted: %d", total_upserted)
