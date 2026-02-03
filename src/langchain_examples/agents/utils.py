from typing import TypedDict
from langchain_core.messages import BaseMessage
from langchain.messages import HumanMessage, ToolMessage


class MessageFilter(TypedDict):
    agent: str
    count: int


def filter_messages(messages: list[BaseMessage], filters: list[MessageFilter]) -> list[BaseMessage]:
    """Filter messages by agent name, keeping last N per agent in chronological order."""
    keep = set()

    for f in filters:
        agent, count = f["agent"], f["count"]
        if agent == "human":
            indices = [i for i, m in enumerate(messages) if isinstance(m, HumanMessage)]
        else:
            indices = [
                i
                for i, m in enumerate(messages)
                if getattr(m, "name", None) == agent and not getattr(m, "tool_calls", None)
            ]
        keep.update(indices[-count:])

    if messages and isinstance(messages[-1], ToolMessage):
        i = len(messages) - 1
        while i >= 0 and isinstance(messages[i], ToolMessage):
            i -= 1
        keep.update(range(i, len(messages)))  # Include AIMessage with tool_calls + ToolMessages

    return [m for i, m in enumerate(messages) if i in keep]
