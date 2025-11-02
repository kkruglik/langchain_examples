def route_after_user_input(state):
    """Route to writer if user wants to continue, otherwise end."""
    return "continue" if not state["user_approved"] else "end"


def route_after_writer(state):
    """Route to factchecker if editor already approved, otherwise to editor."""
    return "skip_editor" if state["editor_approved"] else "to_editor"


def route_after_editor(state):
    """Route to factchecker if approved or max iterations, otherwise back to writer."""
    if state["editor_approved"] or state["iteration"] >= 10:
        return "approved"
    return "rejected"


def route_after_factchecker(state):
    """Route to user approval if facts verified, otherwise back to writer."""
    return "verified" if state["factchecker_approved"] else "rejected"
