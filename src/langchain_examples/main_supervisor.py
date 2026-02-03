import json
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
    supervisor_node,
    swarm_node,
    tool_node,
    user_node,
    writer_node,
)
from .agents.routes import (
    route_after_editor_supervisor,
    route_after_factchecker_supervisor,
    route_after_researcher_supervisor,
    route_after_supervisor,
    route_after_tool,
    route_after_user_input,
)
from .agents.state import PipelineState
from .display import show_final_script, show_node_stats, show_previous_state
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

    conn = sqlite3.connect(str(data_dir / "checkpoints_supervisor.db"), check_same_thread=False)
    memory = SqliteSaver(conn)

    graph = StateGraph(PipelineState)

    graph.add_node("user_input_node", user_node)
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("writer_agent", writer_node)
    graph.add_node("editor_agent", editor_node)
    graph.add_node("factchecker_agent", factchecker_node)
    graph.add_node("researcher_agent", researcher_node)
    graph.add_node("swarm_agent", swarm_node)
    graph.add_node("tools", tool_node)

    graph.add_edge(START, "user_input_node")

    graph.add_conditional_edges("user_input_node", route_after_user_input, {"continue": "supervisor", "end": END})

    graph.add_conditional_edges(
        "supervisor",
        route_after_supervisor,
        {
            "writer_agent": "writer_agent",
            "editor_agent": "editor_agent",
            "factchecker_agent": "factchecker_agent",
            "researcher_agent": "researcher_agent",
            "swarm_agent": "swarm_agent",
            "user_input_node": "user_input_node",
        },
    )

    graph.add_edge("writer_agent", "supervisor")

    graph.add_conditional_edges(
        "tools",
        route_after_tool,
        {
            "to_editor": "editor_agent",
            "to_factchecker": "factchecker_agent",
            "to_researcher": "researcher_agent",
        },
    )

    graph.add_conditional_edges(
        "editor_agent",
        route_after_editor_supervisor,
        {"tool_use": "tools", "to_supervisor": "supervisor"},
    )

    graph.add_conditional_edges(
        "factchecker_agent",
        route_after_factchecker_supervisor,
        {"tool_use": "tools", "to_supervisor": "supervisor"},
    )

    graph.add_conditional_edges(
        "researcher_agent",
        route_after_researcher_supervisor,
        {"tool_use": "tools", "to_supervisor": "supervisor"},
    )

    graph.add_edge("swarm_agent", "supervisor")

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

        # Reset user_approved so it doesn't immediately end, and position at user_input_node
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
    graph_filename = run_dir / "supervisor_graph.png"
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
                    "next_agent": "",
                    "last_agent": "",
                    "node_transitions": {},
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

    # Show node communication stats
    if result.get("node_transitions"):
        show_node_stats(result["node_transitions"])


if __name__ == "__main__":
    main()
