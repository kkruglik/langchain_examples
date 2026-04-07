"""Builds and compiles the one-shot pipeline graph."""
from langgraph.graph import END, START, StateGraph

from langchain_examples.agents.nodes import (
    editor_node,
    factchecker_node,
    illustrator_node,
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


def build_graph():
    # memory = SqliteSaver(conn)  # no persistence needed for one-shot Slack runs
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

    return graph.compile()  # checkpointer=memory
