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
    last_agent: str  # Track which agent is waiting for tool results
    editor_iteration: int  # How many times editor has reviewed (max 4 in conditional graph)
    factchecker_iteration: int  # How many times factchecker has reviewed (max 3 in conditional graph)
    research_output: str
    swarm_output: str
    run_dir: str  # Path to current run folder for saving artifacts
    image_paths: Annotated[list[str], add]  # Paths to generated images
