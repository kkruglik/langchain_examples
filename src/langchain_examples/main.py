import sys
import json
import sqlite3
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from langgraph.graph import END, START, StateGraph
from langgraph.checkpoint.sqlite import SqliteSaver

from .agents.agents import editor_node, factchecker_node, user_node, writer_node, tool_node
from .agents.routes import (
    route_after_editor,
    route_after_factchecker,
    route_after_user_input,
    route_after_writer,
)
from .agents.state import PipelineState


def main():
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

    graph.add_edge("tools", "writer_agent")

    graph.add_conditional_edges(
        "writer_agent",
        route_after_writer,
        {"skip_editor": "factchecker_agent", "to_editor": "editor_agent", "tool_use": "tools"},
    )

    graph.add_conditional_edges(
        "editor_agent", route_after_editor, {"approved": "factchecker_agent", "rejected": "writer_agent"}
    )

    graph.add_conditional_edges(
        "factchecker_agent", route_after_factchecker, {"verified": "user_input_node", "rejected": "writer_agent"}
    )

    app = graph.compile(checkpointer=memory)

    try:
        graph_image = app.get_graph().draw_mermaid_png()
        with open(graph_filename, "wb") as f:
            f.write(graph_image)
        print(f"✓ Pipeline graph saved to: {graph_filename}")
    except Exception as e:
        print(f"⚠ Could not save graph visualization: {e}")
    prev_thread_id = input("Enter previous run ID (blank for new run): ")

    if prev_thread_id:
        thread_config = {
            "configurable": {"thread_id": prev_thread_id},
            "recursion_limit": 30,
        }
        current_state = app.get_state(thread_config)
        if current_state.values:
            print(f"✓ Resuming previous run: {prev_thread_id}")
            result = app.invoke(None, config=thread_config)
        else:
            print(f"⚠ Previous run not found: {prev_thread_id}")
            sys.exit(1)
    else:
        thread_config = {"configurable": {"thread_id": run_id}}
        try:
            result = app.invoke(
                {
                    "messages": [],
                    "drafts": [],
                    "article_content": [],
                    "iteration": 0,
                    "editor_approved": False,
                    "factchecker_approved": False,
                    "user_approved": False,
                },
                config=thread_config,
            )
        except KeyboardInterrupt:
            print("Exiting...")
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
        with open(script_filename, "w", encoding="utf-8") as f:
            f.write(final_script)


if __name__ == "__main__":
    main()
