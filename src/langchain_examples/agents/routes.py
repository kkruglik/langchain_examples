from langchain_core.messages import AIMessage


def _has_tool_calls(state) -> bool:
    """Check if last message has tool calls."""
    last_message = state["messages"][-1]
    return isinstance(last_message, AIMessage) and getattr(last_message, "tool_calls", None)


def route_after_user_input(state):
    """Route to writer if user wants to continue, otherwise end."""
    return "continue" if not state["user_approved"] else "end"


def route_after_writer(state):
    """Route to supervisor (writer no longer has tools)."""
    return "to_supervisor"


def route_after_editor(state):
    """Route to tool_node if tool calls, else based on approval."""
    if _has_tool_calls(state):
        return "tool_use"
    if state["editor_approved"] or state["iteration"] >= 10:
        return "approved"
    return "rejected"


def route_after_factchecker(state):
    """Route to tool_node if tool calls, else based on approval."""
    if _has_tool_calls(state):
        return "tool_use"
    if state["iteration"] >= 5:
        return "verified"
    return "verified" if state["factchecker_approved"] else "rejected"


def route_after_tool(state):
    """Route back to the agent that called the tool."""
    last_agent = state.get("last_agent", "writer")
    return f"to_{last_agent}"


def route_after_editor_supervisor(state):
    """Route for editor in supervisor mode - tool calls or back to supervisor."""
    if _has_tool_calls(state):
        return "tool_use"
    return "to_supervisor"


def route_after_factchecker_supervisor(state):
    """Route for factchecker in supervisor mode - tool calls or back to supervisor."""
    if _has_tool_calls(state):
        return "tool_use"
    return "to_supervisor"


def route_after_researcher_supervisor(state):
    """Route for researcher in supervisor mode - tool calls or back to supervisor."""
    if _has_tool_calls(state):
        return "tool_use"
    return "to_supervisor"


AGENTS = ["writer", "editor", "factchecker", "researcher", "swarm"]


def route_after_supervisor(state) -> str:
    """Route based on supervisor's decision."""
    next_agent = state.get("next_agent", "writer")

    if next_agent == "finish":
        return "user_input_node"
    elif next_agent in AGENTS:
        return f"{next_agent}_agent"
    else:
        return "writer_agent"
