.PHONY: run run-supervisor run-ui run-textual run-textual-web run-gradio scrape scrape-news scrape-articles rag drop-rag qdrant qdrant-down lint fix format check install

run:
	uv run python -m langchain_examples.main

scrape:
	uv run src/langchain_examples/scripts/verstka_scraper.py

scrape-news:
	uv run src/langchain_examples/scripts/verstka_scraper.py --category news

scrape-articles:
	uv run src/langchain_examples/scripts/verstka_scraper.py --category article

rag:
	uv run python -m langchain_examples.pipelines

drop-rag:
	uv run python -c "from src.langchain_examples.pipelines.vdb import client, config; client.delete_collection(config.qdrant.collection_name); print(f'Dropped: {config.qdrant.collection_name}')"
	echo "{}" > data/rag/meta/seen_files.json

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
