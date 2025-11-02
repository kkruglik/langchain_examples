# Design Decisions

## 1. OOP vs Functional: Hybrid Approach

### Decision: Use both paradigms strategically

**OOP for:**
- Agent definitions (encapsulation, state, reusability)
- State models (Pydantic classes)
- UI components (Textual is OOP-based)

**Functional for:**
- State transformations
- Routing logic (pure functions for conditional edges)
- Utility functions

**Rationale:**
- Agents are entities with behavior → natural fit for OOP
- State flow is data transformation → natural fit for functional
- LangGraph works beautifully with both paradigms
- Hybrid approach gives best of both worlds: encapsulation + immutability

**Example:**
```python
# OOP: Agent as a class
class WriterAgent(BaseAgent):
    def __init__(self, model: str):
        self.model = model
        self.llm = ChatOpenAI(model=model)

    async def process(self, state: PipelineState) -> AgentResult:
        # Agent behavior encapsulated
        ...

# Functional: Routing logic
def should_route_to_writer(state: PipelineState) -> str:
    """Pure function for conditional routing"""
    if not state["editor_approved"]:
        return "writer"
    return "factchecker"
```

---

## 2. Agent Registry Pattern

### Decision: Use decorator-based auto-registration

**Pattern:**
```python
# agents/__init__.py
AGENT_REGISTRY = {}

def register_agent(cls):
    AGENT_REGISTRY[cls.__name__] = cls
    return cls

# agents/writer.py
@register_agent
class WriterAgent(BaseAgent):
    ...
```

**Rationale:**
- Zero-config agent discovery
- New agents are automatically available
- No manual registry maintenance
- Config can reference agents by class name

**Alternative considered:** Manual registration
- Rejected: Requires updating registry.py for every new agent
- More error-prone and tedious

---

## 3. State Management

### Decision: TypedDict with Pydantic validation

**Implementation:**
```python
from typing import TypedDict
from pydantic import BaseModel, Field

class Script(BaseModel):
    title: str
    content: str
    duration: int  # seconds

class Feedback(BaseModel):
    agent: str
    iteration: int
    message: str

class PipelineState(TypedDict):
    article_url: str
    article_content: str
    scripts: list[Script]
    current_iteration: int
    feedback_history: list[Feedback]
    status: str
```

**Rationale:**
- TypedDict for LangGraph compatibility (required)
- Pydantic for nested model validation (Scripts, Feedback)
- Type safety throughout the pipeline
- Clear schema for state structure

**Why not pure Pydantic?**
- LangGraph requires TypedDict for state
- Pydantic can be used for nested structures

---

## 4. Configuration Strategy

### Decision: YAML-based configuration with code-based defaults

**Config structure:**
```yaml
pipeline:
  agents:
    - name: writer
      class: WriterAgent
      model: gpt-4o-mini
      params:
        num_scripts: 5
        temperature: 0.7
```

**Code defaults:**
```python
class WriterAgent(BaseAgent):
    DEFAULT_NUM_SCRIPTS = 3
    DEFAULT_TEMPERATURE = 0.8
```

**Rationale:**
- Configuration overrides code defaults
- Sensible defaults work out of the box
- Easy experimentation (change YAML, no code restart)
- Version control friendly

**Alternative considered:** Pure code configuration
- Rejected: Harder to adjust without code changes
- Rejected: Less accessible to non-developers

---

## 5. Persistence Strategy

### Decision: SQLite for state, file-based for queues

**State persistence:**
- SQLite database for pipeline run history
- Stores: article metadata, scripts, feedback, iterations
- Simple queries: "Show all rejected runs", "Get feedback history"

**Queue management (future async):**
- JSON files in `queue/` directory
- One file per pending article
- Simple: just read directory, process files

**Rationale:**
- No external services needed (cost-effective)
- SQLite is built into Python
- File-based queue is dead simple
- Perfect for single-machine deployment

**Alternatives considered:**
- PostgreSQL: Rejected, overkill for this use case
- Redis: Rejected, requires external service
- In-memory only: Rejected, lose state on restart

---

## 6. Error Handling & Retries

### Decision: Multi-level retry strategy

**Agent level:**
```python
class WriterAgent(BaseAgent):
    max_retries: int = 3  # Config-driven

    async def process(self, state: PipelineState) -> AgentResult:
        for attempt in range(self.max_retries):
            try:
                return await self._generate_scripts(state)
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
```

**Pipeline level:**
```python
class Pipeline:
    max_iterations: int = 5  # Prevent infinite rejection loops

    async def run(self, article_url: str):
        if state["current_iteration"] >= self.max_iterations:
            raise MaxIterationsError(...)
```

**Rationale:**
- Agent retries handle transient API errors
- Pipeline iterations handle rejection loops
- Clear failure modes and limits
- Prevents runaway costs

---

## 7. LLM Model Selection

### Decision: Different models for different agents

**Configuration:**
- Writer: `gpt-4o-mini` (fast, cheap, creative)
- Editor: `gpt-4o` (better judgment, quality assessment)
- FactChecker: `gpt-4o` (critical thinking, accuracy)

**Rationale:**
- Cost optimization: Use mini for bulk generation
- Quality where it matters: Use full model for review
- Flexibility: Easy to adjust per agent

**Cost comparison (estimated):**
- All gpt-4o: ~$0.015 per article
- Mixed approach: ~$0.008 per article
- 47% cost reduction

---

## 8. Rejection Loop Design

### Decision: Feedback accumulation in state

**Implementation:**
```python
if not agent_result.approved:
    state["feedback_history"].append(
        Feedback(
            agent=agent.name,
            iteration=state["current_iteration"],
            message=agent_result.feedback
        )
    )
    # Route back to writer
    return "writer"
```

**Writer uses accumulated feedback:**
```python
class WriterAgent:
    async def process(self, state: PipelineState) -> AgentResult:
        feedback_context = "\n".join([
            f"{fb.agent}: {fb.message}"
            for fb in state["feedback_history"]
        ])
        # Include in prompt
```

**Rationale:**
- Writer sees all historical feedback
- Can address multiple concerns simultaneously
- Prevents repetitive issues
- Clear audit trail

**Alternative considered:** Only last feedback
- Rejected: Writer might fix one issue but reintroduce another
- Accumulated feedback is more robust

---

## 9. UI Strategy

### Decision: Textual TUI with minimal initial features

**Phase 1 (MVP):**
- Display pipeline progress
- Show current agent status
- User approval prompt (approve/reject/provide feedback)

**Phase 2 (future):**
- Live script preview
- Feedback history viewer
- Multi-article queue management

**Rationale:**
- TUI is cost-effective (no web server, no frontend complexity)
- Terminal-friendly for developers
- Textual provides rich components
- Can be enhanced incrementally

**Alternative considered:** Web UI
- Rejected: Adds complexity (backend, frontend, deployment)
- Rejected: Not cost-effective for single-user tool

---

## 10. Pluggability Strategy

### Decision: Convention over configuration

**How to add a new agent:**

1. Create file: `agents/new_agent.py`
2. Implement `BaseAgent`
3. Add decorator: `@register_agent`
4. Update config: Add to `config.yaml`

**Example - SEO Agent:**
```python
# agents/seo_agent.py
@register_agent
class SEOAgent(BaseAgent):
    async def process(self, state: PipelineState) -> AgentResult:
        # Check keywords, title optimization, etc.
        ...
```

```yaml
# config.yaml
pipeline:
  agents:
    # ... existing agents ...
    - name: seo
      class: SEOAgent
      model: gpt-4o-mini

  flow:
    # Insert into flow
    - editor → seo → factchecker
```

**No code changes required in:**
- Pipeline builder
- State management
- UI (automatically picks up new agent)

**Rationale:**
- True plug-and-play
- Encourages experimentation
- Easy to disable agents (remove from config)
- Minimal coupling between components
