.PHONY: run run-supervisor run-ui run-textual run-textual-web run-gradio scrape scrape-news scrape-articles lint fix format check install

run:
	uv run python -m langchain_examples.main

run-supervisor:
	uv run python -m langchain_examples.main_supervisor

run-ui:
	uv run streamlit run run_streamlit.py

run-textual:
	uv run python -m langchain_examples.ui.textual_app

run-textual-web:
	uv run textual serve src/langchain_examples/ui/textual_app.py:PipelineApp

run-gradio:
	uv run python -m langchain_examples.ui.gradio_app

scrape:
	uv run src/langchain_examples/scripts/verstka_scraper.py

scrape-news:
	uv run src/langchain_examples/scripts/verstka_scraper.py --category news

scrape-articles:
	uv run src/langchain_examples/scripts/verstka_scraper.py --category article

# Linting
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
