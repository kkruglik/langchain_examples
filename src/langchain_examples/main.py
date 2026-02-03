import json
import signal
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from .agents.nodes import editor_node, factchecker_node, tool_node, user_node, writer_node
from .agents.routes import (
    route_after_editor,
    route_after_factchecker,
    route_after_tool,
    route_after_user_input,
    route_after_writer,
)
from .agents.state import PipelineState
from .display import show_final_script
from .logging import get_logger, setup_logging

logger = get_logger(__name__)


def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully."""
    logger.warning("Interrupted by user. Exiting...")
    sys.exit(0)


def main():
    setup_logging()
    signal.signal(signal.SIGINT, signal_handler)

    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = data_dir / "runs" / run_id
    run_dir.mkdir(exist_ok=True, parents=True)

    conn = sqlite3.connect(str(data_dir / "checkpoints.db"), check_same_thread=False)
    memory = SqliteSaver(conn)

    pipeline_filename = run_dir / "pipeline_result.json"
    graph_filename = run_dir / "pipeline_graph.png"
    script_filename = run_dir / "final_script.txt"

    graph = StateGraph(PipelineState)

    graph.add_node("user_input_node", user_node)
    graph.add_node("writer_agent", writer_node)
    graph.add_node("editor_agent", editor_node)
    graph.add_node("factchecker_agent", factchecker_node)
    graph.add_node("tools", tool_node)

    graph.add_edge(START, "user_input_node")

    graph.add_conditional_edges("user_input_node", route_after_user_input, {"continue": "writer_agent", "end": END})

    graph.add_conditional_edges(
        "tools",
        route_after_tool,
        {"to_writer": "writer_agent", "to_editor": "editor_agent", "to_factchecker": "factchecker_agent"},
    )

    graph.add_conditional_edges(
        "writer_agent",
        route_after_writer,
        {"skip_editor": "factchecker_agent", "to_editor": "editor_agent", "tool_use": "tools"},
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

    app = graph.compile(checkpointer=memory)

    try:
        graph_image = app.get_graph().draw_mermaid_png()
        with open(graph_filename, "wb") as f:
            f.write(graph_image)
        logger.info("Pipeline graph saved to: %s", graph_filename)
    except Exception as e:
        logger.warning("Could not save graph visualization: %s", e)

    prev_thread_id = input("Enter previous run ID (blank for new run): ")

    try:
        if prev_thread_id:
            thread_config = {
                "configurable": {"thread_id": prev_thread_id},
                "recursion_limit": 30,
            }
            current_state = app.get_state(thread_config)
            if current_state.values:
                logger.info("Resuming previous run: %s", prev_thread_id)
                result = app.invoke(None, config=thread_config)
            else:
                logger.error("Previous run not found: %s", prev_thread_id)
                sys.exit(1)
        else:
            thread_config = {
                "configurable": {"thread_id": run_id},
                "recursion_limit": 30,
            }
            result = app.invoke(
                {
                    "messages": [],
                    "drafts": [],
                    "article_content": [],
                    "iteration": 0,
                    "editor_approved": False,
                    "factchecker_approved": False,
                    "user_approved": False,
                    "next_agent": "",
                    "last_agent": "",
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
