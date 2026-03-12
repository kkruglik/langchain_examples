from langchain_core.messages import AIMessage


def _has_tool_calls(state) -> bool:
    """Check if last message has tool calls."""
    last_message = state["messages"][-1]
    return isinstance(last_message, AIMessage) and getattr(last_message, "tool_calls", None)


def route_after_user_input(state):
    """Route: end / to_researcher (first run) / to_writer (feedback loop)."""
    if state["user_approved"]:
        return "end"
    if state["drafts"]:
        return "to_writer"
    return "to_researcher"


def route_after_researcher(state):
    """Route: tool_use if tool calls, else done (to swarm)."""
    if _has_tool_calls(state):
        return "tool_use"
    return "done"


def route_after_writer(state):
    """Route: to_editor (editor loop) or to_factchecker (factchecker loop)."""
    if state["editor_approved"]:
        return "to_factchecker"
    return "to_editor"


def route_after_editor(state):
    """Route: approved (max 4 iterations) / rejected."""
    if state["editor_approved"] or state.get("editor_iteration", 0) >= 4:
        return "approved"
    return "rejected"


def route_after_factchecker(state):
    """Route: tool_use / verified (max 3 iterations) / rejected."""
    if _has_tool_calls(state):
        return "tool_use"
    if state["factchecker_approved"] or state.get("factchecker_iteration", 0) >= 3:
        return "verified"
    return "rejected"


def route_after_tool(state):
    """Route back to the agent that called the tool."""
    last_agent = state.get("last_agent", "writer")
    return f"to_{last_agent}"


