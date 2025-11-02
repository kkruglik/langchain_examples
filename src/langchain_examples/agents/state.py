from typing import TypedDict, Annotated

from operator import add
from langchain_core.messages import BaseMessage


class PipelineState(TypedDict):
    messages: Annotated[list[BaseMessage], add]  # Unified message history (HumanMessage, AIMessage, etc.)
    drafts: Annotated[list[str], add]
    article_content: Annotated[list[str], add]
    iteration: int
    editor_approved: bool
    factchecker_approved: bool
    user_approved: bool
