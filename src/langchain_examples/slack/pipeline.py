"""Runs the pipeline for a single Slack message."""
from datetime import datetime
from pathlib import Path

from langchain_core.messages import HumanMessage

from langchain_examples.agents.graph import build_graph
from langchain_examples.agents.nodes import URL_PATTERN, normalize_url
from langchain_examples.tools.agent_tools import scrape_article, scrape_telegram_post

_app = build_graph()


def run_pipeline_once(text: str) -> dict:
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    run_dir = data_dir / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    urls = list(dict.fromkeys(normalize_url(u) for u in URL_PATTERN.findall(text)))
    article_content = []
    for url in urls:
        if "t.me/" in url:
            article_content.append(scrape_telegram_post.invoke({"url": url}))
        else:
            article_content.append(scrape_article.invoke({"url": url}))

    if not article_content:
        article_content.append(text)

    initial_state = {
        "messages": [HumanMessage(content=text)],
        "article_content": article_content,
        "drafts": [],
        "iteration": 0,
        "editor_approved": False,
        "factchecker_approved": False,
        "user_approved": False,
        "last_agent": "",
        "editor_iteration": 0,
        "factchecker_iteration": 0,
        "research_output": "",
        "swarm_output": "",
        "run_dir": str(run_dir),
        "image_paths": [],
    }

    return _app.invoke(initial_state, config={"recursion_limit": 40})
