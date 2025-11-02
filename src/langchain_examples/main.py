import json
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from langgraph.graph import END, START, StateGraph

from .agents.agents import editor_agent, factchecker_agent, user_input_node, writer_agent
from .agents.routes import route_after_editor, route_after_factchecker, route_after_user_input, route_after_writer
from .agents.state import PipelineState


def main():
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = data_dir / "runs" / run_id
    run_dir.mkdir(exist_ok=True, parents=True)

    pipeline_filename = run_dir / "pipeline_result.json"
    graph_filename = run_dir / "pipeline_graph.png"
    script_filename = run_dir / "final_script.txt"

    workflow = StateGraph(PipelineState)

    workflow.add_node("user_input_node", user_input_node)
    workflow.add_node("writer_agent", writer_agent)
    workflow.add_node("editor_agent", editor_agent)
    workflow.add_node("factchecker_agent", factchecker_agent)

    workflow.add_edge(START, "user_input_node")

    workflow.add_conditional_edges("user_input_node", route_after_user_input, {"continue": "writer_agent", "end": END})

    workflow.add_conditional_edges(
        "writer_agent", route_after_writer, {"skip_editor": "factchecker_agent", "to_editor": "editor_agent"}
    )

    workflow.add_conditional_edges(
        "editor_agent", route_after_editor, {"approved": "factchecker_agent", "rejected": "writer_agent"}
    )

    workflow.add_conditional_edges(
        "factchecker_agent", route_after_factchecker, {"verified": "user_input_node", "rejected": "writer_agent"}
    )

    app = workflow.compile()

    result = app.invoke(
        {
            "messages": [],
            "drafts": [],
            "article_content": [],
            "iteration": 0,
            "editor_approved": False,
            "factchecker_approved": False,
            "user_approved": False,
        }
    )

    # Convert messages to serializable format
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

    try:
        graph_image = app.get_graph().draw_mermaid_png()
        with open(graph_filename, "wb") as f:
            f.write(graph_image)
        print(f"✓ Pipeline graph saved to: {graph_filename}")
    except Exception as e:
        print(f"⚠ Could not save graph visualization: {e}")


if __name__ == "__main__":
    main()
