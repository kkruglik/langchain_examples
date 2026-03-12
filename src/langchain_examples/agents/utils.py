from typing import TypedDict
from langchain_core.messages import BaseMessage
from langchain.messages import HumanMessage, ToolMessage

from langchain_examples.logging import get_logger

logger = get_logger(__name__)


class MessageFilter(TypedDict):
    agent: str
    count: int


def analyze_script(script: str) -> dict:
    """Analyze script length and estimate speaking time.

    Args:
        script: The script text to analyze

    Returns:
        Dict with character count, word count, and estimated speaking time in seconds
    """
    logger.debug("analyze_script called")
    words = script.split()
    word_count = len(words)
    char_count = len(script)

    # Average speaking rate: 150 words per minute (2.5 words per second)
    speaking_time_seconds = int(word_count / 2.5)

    return {
        "characters": char_count,
        "words": word_count,
        "speaking_time_seconds": speaking_time_seconds,
        "speaking_time_formatted": f"{speaking_time_seconds // 60}:{speaking_time_seconds % 60:02d}",
    }


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
