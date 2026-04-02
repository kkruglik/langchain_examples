"""
Slack bot entry point — one-shot pipeline (no human-in-the-loop).

Run:
    uv run python -m langchain_examples.slack_main
"""
import sqlite3
from datetime import datetime
from pathlib import Path

import pypandoc

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from langchain_examples.agents.nodes import (
    URL_PATTERN,
    editor_node,
    factchecker_node,
    illustrator_node,
    normalize_url,
    researcher_node,
    swarm_writer_node,
    tool_node,
    # user_node,  # not used in one-shot mode
    writer_node,
)
from langchain_examples.agents.routes import (
    route_after_editor,
    route_after_factchecker,
    route_after_researcher,
    route_after_tool,
    route_after_writer,
)
from langchain_examples.agents.state import PipelineState
from langchain_examples.config import DEFAULT_CONFIG, agents_config as loaded_agents_config
from langchain_examples.display import show_config
from langchain_examples.logging import get_logger, setup_logging
from langchain_examples.slack.bot import register_handlers
from langchain_examples.tools.agent_tools import scrape_article, scrape_telegram_post

logger = get_logger(__name__)


def _save_docx(path: Path, content: str) -> None:
    lines = content.splitlines()
    cleaned = "\n".join("" if line.strip() == "---" else line for line in lines)
    pypandoc.convert_text(cleaned, "docx", format="markdown-yaml_metadata_block", outputfile=str(path))


def save_artifacts(result: dict) -> list[str]:
    """Save pipeline outputs as DOCX files + collect image paths. Returns file paths to upload."""
    run_dir = Path(result["run_dir"])
    paths = []

    if result.get("research_output"):
        p = run_dir / "research.docx"
        _save_docx(p, result["research_output"])
        paths.append(str(p))

    if result.get("swarm_output"):
        p = run_dir / "swarm.docx"
        _save_docx(p, result["swarm_output"])
        paths.append(str(p))

    if result.get("drafts"):
        p = run_dir / "script.docx"
        _save_docx(p, result["drafts"][-1])
        paths.append(str(p))

    paths.extend(result.get("image_paths", []))
    return paths


def build_one_shot_graph(conn: sqlite3.Connection):
    """Build LangGraph without user_input_node. illustrator_agent goes to END."""
    memory = SqliteSaver(conn)
    graph = StateGraph(PipelineState)

    graph.add_node("researcher_agent", researcher_node)
    graph.add_node("swarm_agent", swarm_writer_node)
    graph.add_node("writer_agent", writer_node)
    graph.add_node("editor_agent", editor_node)
    graph.add_node("factchecker_agent", factchecker_node)
    graph.add_node("illustrator_agent", illustrator_node)
    graph.add_node("tools", tool_node)

    graph.add_edge(START, "researcher_agent")

    graph.add_conditional_edges(
        "researcher_agent",
        route_after_researcher,
        {"tool_use": "tools", "done": "swarm_agent"},
    )
    graph.add_edge("swarm_agent", "writer_agent")
    graph.add_conditional_edges(
        "writer_agent",
        route_after_writer,
        {"to_editor": "editor_agent", "to_factchecker": "factchecker_agent"},
    )
    graph.add_conditional_edges(
        "editor_agent",
        route_after_editor,
        {"approved": "factchecker_agent", "rejected": "writer_agent"},
    )
    graph.add_conditional_edges(
        "factchecker_agent",
        route_after_factchecker,
        {"verified": "illustrator_agent", "rejected": "writer_agent", "tool_use": "tools"},
    )
    graph.add_edge("illustrator_agent", END)
    graph.add_conditional_edges(
        "tools",
        route_after_tool,
        {"to_factchecker": "factchecker_agent", "to_researcher": "researcher_agent"},
    )

    return graph.compile(checkpointer=memory)


def run_pipeline_once(text: str) -> dict:
    """Scrape URLs from text, run the full pipeline, return result state."""
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    run_dir = data_dir / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(data_dir / "checkpoints.db"), check_same_thread=False)

    try:
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

        thread_config = {"configurable": {"thread_id": run_id}, "recursion_limit": 100}
        app = build_one_shot_graph(conn)
        return app.invoke(initial_state, config=thread_config)
    finally:
        conn.close()


def main():
    setup_logging()
    show_config(DEFAULT_CONFIG, loaded_agents_config)

    slack_app = App()
    register_handlers(slack_app, run_pipeline_once, save_artifacts)

    logger.info("Starting Slack bot (Socket Mode)...")
    SocketModeHandler(slack_app).start()


if __name__ == "__main__":
    main()
