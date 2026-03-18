.PHONY: run scrape scrape-news scrape-articles rag drop-rag qdrant qdrant-down lint fix format check install

run:
	uv run python -m langchain_examples.main

scrape:
	uv run python -m langchain_examples.rag.ingestion.scraper

scrape-news:
	uv run python -m langchain_examples.rag.ingestion.scraper --category news

scrape-articles:
	uv run python -m langchain_examples.rag.ingestion.scraper --category article

rag:
	uv run python -m langchain_examples.rag.ingestion

drop-rag:
	uv run python -c "from langchain_examples.rag.ingestion.vdb import client, config; client.delete_collection(config.qdrant.collection_name); print(f'Dropped: {config.qdrant.collection_name}')"

qdrant:
	docker compose up -d

qdrant-down:
	docker compose down

lint:
	uv run ruff check src/

fix:
	uv run ruff check --fix src/

format:
	uv run ruff format src/

check: lint
	uv run ruff format --check src/

install:
	uv sync
