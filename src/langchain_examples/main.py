import json
import os
import signal
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from .agents.nodes import (
    editor_node,
    factchecker_node,
    researcher_node,
    swarm_node,
    tool_node,
    user_node,
    writer_node,
)
from .agents.routes import (
    route_after_editor,
    route_after_factchecker,
    route_after_researcher,
    route_after_tool,
    route_after_user_input,
    route_after_writer,
)
from .agents.state import PipelineState
from .config import DEFAULT_CONFIG, agents_config as loaded_agents_config
from .display import show_config, show_final_script, show_previous_state
from .logging import get_logger, setup_logging

logger = get_logger(__name__)


def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully."""
    logger.warning("Interrupted by user. Exiting...")
    sys.exit(0)


def main():
    setup_logging()
    signal.signal(signal.SIGINT, signal_handler)

    config_file = os.getenv("CONFIG_FILE", DEFAULT_CONFIG)
    show_config(config_file, loaded_agents_config)

    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)

    conn = sqlite3.connect(str(data_dir / "checkpoints.db"), check_same_thread=False)
    memory = SqliteSaver(conn)

    graph = StateGraph(PipelineState)

    graph.add_node("user_input_node", user_node)
    graph.add_node("researcher_agent", researcher_node)
    graph.add_node("swarm_agent", swarm_node)
    graph.add_node("writer_agent", writer_node)
    graph.add_node("editor_agent", editor_node)
    graph.add_node("factchecker_agent", factchecker_node)
    graph.add_node("tools", tool_node)

    graph.add_edge(START, "user_input_node")

    graph.add_conditional_edges(
        "user_input_node",
        route_after_user_input,
        {"to_researcher": "researcher_agent", "to_writer": "writer_agent", "end": END},
    )

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
        {"approved": "factchecker_agent", "rejected": "writer_agent", "tool_use": "tools"},
    )

    graph.add_conditional_edges(
        "factchecker_agent",
        route_after_factchecker,
        {"verified": "user_input_node", "rejected": "writer_agent", "tool_use": "tools"},
    )

    graph.add_conditional_edges(
        "tools",
        route_after_tool,
        {"to_editor": "editor_agent", "to_factchecker": "factchecker_agent", "to_researcher": "researcher_agent"},
    )

    app = graph.compile(checkpointer=memory)

    prev_thread_id = input("Enter previous run ID (blank for new run): ").strip()

    if prev_thread_id:
        run_id = prev_thread_id
        thread_config = {
            "configurable": {"thread_id": prev_thread_id},
            "recursion_limit": 100,
        }
        current_state = app.get_state(thread_config)
        if not current_state.values:
            logger.error("Previous run not found: %s", prev_thread_id)
            sys.exit(1)
        logger.info("Resuming previous run: %s", prev_thread_id)
        show_previous_state(current_state.values)
        app.update_state(thread_config, {"user_approved": False}, as_node="user_input_node")
    else:
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        thread_config = {
            "configurable": {"thread_id": run_id},
            "recursion_limit": 100,
        }
        logger.info("Starting new run: %s", run_id)

    run_dir = data_dir / "runs" / run_id
    run_dir.mkdir(exist_ok=True, parents=True)

    pipeline_filename = run_dir / "pipeline_result.json"
    graph_filename = run_dir / "pipeline_graph.png"
    script_filename = run_dir / "final_script.md"

    try:
        graph_image = app.get_graph().draw_mermaid_png()
        with open(graph_filename, "wb") as f:
            f.write(graph_image)
        logger.info("Pipeline graph saved to: %s", graph_filename)
    except Exception as e:
        logger.warning("Could not save graph visualization: %s", e)

    try:
        if prev_thread_id:
            result = app.invoke(None, config=thread_config)
        else:
            result = app.invoke(
                {
                    "messages": [],
                    "drafts": [],
                    "article_content": [],
                    "iteration": 0,
                    "editor_approved": False,
                    "factchecker_approved": False,
                    "user_approved": False,
                    "last_agent": "",
                    "editor_iteration": 0,
                    "factchecker_iteration": 0,
                },
                config=thread_config,
            )
    except KeyboardInterrupt:
        logger.warning("Interrupted by user. Exiting...")
        sys.exit(0)

    serializable_result = {**result}
    serializable_result["messages"] = [
        {"type": msg.__class__.__name__, "content": msg.content, "name": getattr(msg, "name", None)}
        for msg in result.get("messages", [])
    ]

    with open(pipeline_filename, "w", encoding="utf-8") as f:
        json.dump(serializable_result, f, indent=2, ensure_ascii=False)

    if result.get("drafts"):
        final_script = result["drafts"][-1]
        show_final_script(final_script)
        with open(script_filename, "w", encoding="utf-8") as f:
            f.write(final_script)
        logger.info("Final script saved to: %s", script_filename)


if __name__ == "__main__":
    main()
