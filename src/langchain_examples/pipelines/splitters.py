import logging

from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

from .config import config

logger = logging.getLogger(__name__)

splitter_config = config.splitter

md_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=[("#", "h1"), ("##", "h2")])
char_splitter = RecursiveCharacterTextSplitter(
    chunk_size=splitter_config.chunk_size, chunk_overlap=splitter_config.chunk_overlap
)


def chunk_text(record: dict) -> list[Document]:
    md_chunks = md_splitter.split_text(record["content"])
    chunks = char_splitter.split_documents(md_chunks)
    logger.info(f"Chunked {record.get('url', '')} -> {len(chunks)} chunks")
    for chunk in chunks:
        chunk.metadata.update(
            {
                "url": record["url"],
                "source": record.get("source", ""),
                "title": record["title"],
                "date": record["date"],
                "category": record["category"],
                "tags": record["tags"],
            }
        )
    return chunks
