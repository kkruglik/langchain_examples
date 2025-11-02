# Agentic Video Script System - Architecture

## Overview

This system takes articles from websites and produces multiple short video scripts through a multi-agent pipeline with human-in-the-loop approval.

## Architecture Pattern: Pipeline with State Machine

```
Article Source → Writer Agent → Editor Agent → FactChecker Agent → User Approval
                      ↑______________|__________________|
                      (rejection loop with feedback)
```

### Why LangGraph over LCEL?

**LangGraph provides:**

- **Cycles**: Built-in support for rejection loops
- **Conditional edges**: Natural routing (e.g., `editor → writer` if rejected)
- **State persistence**: Automatic state management across agent interactions
- **Async native**: No refactoring needed when scaling
- **Visualization**: Built-in graph visualization for debugging
- **Checkpointing**: Free retry/resume capability

**LCEL limitations:**

- No cycles (would need custom logic)
- Harder conditional routing
- Manual state management

## System Components

### 1. Agents

All agents implement a common `BaseAgent` protocol:

```python
class BaseAgent(ABC):
    @abstractmethod
    async def process(self, state: PipelineState) -> AgentResult:
        """Process input and return result with approval/rejection"""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        pass
```

**Agent Types:**

- **WriterAgent**: Generates multiple video scripts from article content
- **EditorAgent**: Reviews scripts for readability and catchiness, can reject with feedback
- **FactCheckerAgent**: Verifies factual accuracy, can reject with feedback

### 2. State Management

```python
class PipelineState(TypedDict):
    article_url: str
    article_content: str
    scripts: List[Script]
    current_iteration: int
    feedback_history: List[Feedback]
    status: str  # "in_progress" | "approved" | "rejected"
```

State flows through the pipeline and is accessible to all agents. Each agent can:

- Read current state
- Modify their output
- Add feedback
- Approve or reject (triggering routing back to writer)

### 3. Agent Result Format

```python
class AgentResult:
    approved: bool              # Did this agent approve?
    output: Any                 # Modified scripts/content
    feedback: Optional[str]     # Feedback for writer if rejected
    next_agent: Optional[str]   # For custom routing
```

## Pipeline Flow

### LangGraph Implementation

```python
from langgraph.graph import StateGraph, END

# Define graph
workflow = StateGraph(PipelineState)

# Add nodes (agents)
workflow.add_node("writer", writer_agent.process)
workflow.add_node("editor", editor_agent.process)
workflow.add_node("factchecker", factchecker_agent.process)
workflow.add_node("user_approval", user_approval_handler)

# Define edges with conditional routing
workflow.add_edge("writer", "editor")

workflow.add_conditional_edges(
    "editor",
    lambda state: "writer" if not state["editor_approved"] else "factchecker",
)

workflow.add_conditional_edges(
    "factchecker",
    lambda state: "writer" if not state["facts_approved"] else "user_approval",
)

workflow.add_edge("user_approval", END)

# Compile and run
app = workflow.compile()
result = await app.ainvoke(initial_state)
```

### Rejection Loop

When an agent rejects:

1. Agent sets `approved: False` and provides `feedback`
2. Conditional edge routes back to `writer`
3. Writer receives feedback in state
4. Writer regenerates scripts incorporating feedback
5. Scripts go through pipeline again
6. Maximum retry limit prevents infinite loops

## Project Structure

```
src/
├── agents/
│   ├── base.py              # BaseAgent ABC
│   ├── writer.py            # WriterAgent implementation
│   ├── editor.py            # EditorAgent implementation
│   ├── factchecker.py       # FactCheckerAgent implementation
│   └── __init__.py          # Auto-registration system
├── core/
│   ├── pipeline.py          # LangGraph pipeline builder
│   ├── state.py             # State models (Pydantic/TypedDict)
│   └── registry.py          # Agent registry for plugin system
├── scrapers/
│   └── article_scraper.py   # Article content fetching
├── ui/
│   └── terminal.py          # Textual-based terminal UI
├── config.yaml              # Agent pipeline configuration
└── main.py                  # Entry point
```

## Technology Stack

**Core Framework:**

- LangChain + LangGraph for agent orchestration
- OpenAI API for LLM inference

**UI:**

- Textual for terminal interface (cost-effective, no web server needed)

**State Management:**

- SQLite for persistence (simple, file-based, no separate DB server)
- File-based queuing for async work (JSON files)

**No external dependencies:**

- No message brokers (Redis, RabbitMQ)
- No Docker requirement
- No web server
- Keep it simple and cheap

## Async Strategy

### Phase 1 (Initial): Synchronous

```python
result = workflow.invoke(state)  # Synchronous
```

**Benefits:**

- Simpler debugging
- Faster initial development
- Easier to reason about

### Phase 2 (Future): Async

```python
result = await workflow.ainvoke(state)  # Async
```

**Migration steps:**

1. Add `async` to agent methods
2. Change `invoke()` to `ainvoke()`
3. Done! LangGraph handles the rest

**Benefits:**

- Better resource utilization
- Can process multiple articles concurrently
- UI remains responsive during processing

## Configuration-Driven Design

Agents and pipeline flow are configured via YAML:

```yaml
# config.yaml
pipeline:
  agents:
    - name: writer
      class: WriterAgent
      model: gpt-4o-mini
      max_retries: 3
      params:
        num_scripts: 5

    - name: editor
      class: EditorAgent
      model: gpt-4o
      can_reject: true

    - name: factchecker
      class: FactCheckerAgent
      model: gpt-4o
      can_reject: true

  flow:
    - writer → editor
    - editor → factchecker (if approved) | writer (if rejected)
    - factchecker → user (if approved) | writer (if rejected)
```

This allows changing agent behavior, models, and flow without code changes.
