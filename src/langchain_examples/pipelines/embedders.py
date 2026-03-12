from langsmith import traceable
import logging

from fastembed import SparseEmbedding, SparseTextEmbedding
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings

from .config import config

logger = logging.getLogger(__name__)

dense_embeddings = OpenAIEmbeddings(model=config.embedding_model, openai_api_key=config.openai_api_key)
bm25_embedding_model = SparseTextEmbedding("Qdrant/bm25")

# late_interaction_embedding_model = LateInteractionTextEmbedding(
#     "answerdotai/answerai-colbert-small-v1",
#     providers=["CoreMLExecutionProvider", "CPUExecutionProvider"],
# )


@traceable(name="apply_dense_embeddings")
def apply_dense_embeddings(documents: list[Document]) -> list[list[float]]:
    logger.info(f"Embedding {len(documents)} chunks")
    return dense_embeddings.embed_documents([doc.page_content for doc in documents])


@traceable(name="apply_bm25_embeddings")
def apply_bm25_embeddings(documents: list[Document]) -> list[SparseEmbedding]:
    logger.info(f"BM25 embedding {len(documents)} chunks")
    return list(bm25_embedding_model.embed([doc.page_content for doc in documents]))


# def apply_late_embeddings(documents: list[Document]) -> list[list[list[float]]]:
#     logger.info(f"ColBERT embedding {len(documents)} chunks")
#     return list(late_interaction_embedding_model.embed([doc.page_content for doc in documents]))
