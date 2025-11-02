# Extensibility Guide

## Adding New Agents

The system is designed for zero-refactoring agent addition. Follow these steps:

### 1. Create Agent File

Create a new file in `agents/` directory:

```python
# agents/seo_agent.py
from agents.base import BaseAgent, AgentResult
from core.state import PipelineState
from langchain_openai import ChatOpenAI

@register_agent
class SEOAgent(BaseAgent):
    """Checks scripts for SEO optimization and keyword usage."""

    def __init__(self, model: str = "gpt-4o-mini", **kwargs):
        super().__init__()
        self.model = model
        self.llm = ChatOpenAI(model=model)
        self.config = kwargs

    @property
    def name(self) -> str:
        return "seo"

    async def process(self, state: PipelineState) -> AgentResult:
        """Check SEO compliance of scripts."""

        # Build prompt with context
        prompt = f"""
        Analyze these video scripts for SEO optimization:

        {self._format_scripts(state["scripts"])}

        Check for:
        - Keyword usage and density
        - Title optimization
        - Description quality
        - Call-to-action presence

        Provide feedback if improvements needed.
        """

        response = await self.llm.ainvoke(prompt)

        # Determine if approved
        approved = "approved" in response.content.lower()

        return AgentResult(
            approved=approved,
            output=state["scripts"],  # Scripts unchanged by SEO check
            feedback=None if approved else response.content,
            next_agent="factchecker" if approved else None
        )

    def _format_scripts(self, scripts):
        return "\n\n".join([
            f"Script {i+1}: {s.title}\n{s.content}"
            for i, s in enumerate(scripts)
        ])
```

### 2. Register in __init__.py

The `@register_agent` decorator automatically adds your agent to the registry. Just make sure to import it:

```python
# agents/__init__.py
from agents.base import register_agent
from agents.writer import WriterAgent
from agents.editor import EditorAgent
from agents.factchecker import FactCheckerAgent
from agents.seo_agent import SEOAgent  # Add this line
```

### 3. Update Configuration

Add your agent to `config.yaml`:

```yaml
pipeline:
  agents:
    - name: writer
      class: WriterAgent
      model: gpt-4o-mini
      max_retries: 3

    - name: editor
      class: EditorAgent
      model: gpt-4o
      can_reject: true

    # ADD YOUR NEW AGENT HERE
    - name: seo
      class: SEOAgent
      model: gpt-4o-mini
      can_reject: true

    - name: factchecker
      class: FactCheckerAgent
      model: gpt-4o
      can_reject: true

  flow:
    - writer → editor
    - editor → seo (if approved) | writer (if rejected)
    - seo → factchecker (if approved) | writer (if rejected)
    - factchecker → user (if approved) | writer (if rejected)
```

### 4. That's It!

No changes needed to:
- Pipeline builder (automatically detects agent)
- State management (uses existing state)
- UI (picks up new agent automatically)

---

## Agent Capabilities

### Can Reject and Provide Feedback

```python
return AgentResult(
    approved=False,
    output=state["scripts"],
    feedback="Scripts need more engaging hooks in the first 3 seconds.",
    next_agent=None  # Will route to writer by default
)
```

### Can Modify Content

```python
# Transform scripts
modified_scripts = [
    Script(
        title=self._optimize_title(s.title),
        content=s.content,
        duration=s.duration
    )
    for s in state["scripts"]
]

return AgentResult(
    approved=True,
    output=modified_scripts,
    feedback=None,
    next_agent="factchecker"
)
```

### Can Access Full State

```python
async def process(self, state: PipelineState) -> AgentResult:
    # Access article
    article = state["article_content"]

    # Access previous feedback
    feedback_history = state["feedback_history"]

    # Access iteration count
    iteration = state["current_iteration"]

    # Use all context for decision-making
    ...
```

### Can Use Custom Configuration

```python
# config.yaml
- name: seo
  class: SEOAgent
  model: gpt-4o-mini
  params:
    target_keywords: ["AI", "technology", "innovation"]
    min_keyword_density: 0.02
    require_cta: true

# Agent implementation
class SEOAgent(BaseAgent):
    def __init__(self, model: str, params: dict = None, **kwargs):
        self.target_keywords = params.get("target_keywords", [])
        self.min_density = params.get("min_keyword_density", 0.01)
        self.require_cta = params.get("require_cta", False)
```

---

## Extending State

If your agent needs additional state fields:

### 1. Update State Definition

```python
# core/state.py
class PipelineState(TypedDict):
    article_url: str
    article_content: str
    scripts: list[Script]
    current_iteration: int
    feedback_history: list[Feedback]
    status: str

    # ADD NEW FIELDS
    seo_score: Optional[float]  # New field for SEO agent
    keyword_density: Optional[dict[str, float]]  # New field
```

### 2. Initialize in Pipeline

```python
# core/pipeline.py
initial_state = PipelineState(
    article_url=url,
    article_content=content,
    scripts=[],
    current_iteration=0,
    feedback_history=[],
    status="in_progress",
    seo_score=None,  # Initialize new fields
    keyword_density=None,
)
```

### 3. Use in Agents

```python
async def process(self, state: PipelineState) -> AgentResult:
    # Calculate and store in state
    seo_score = self._calculate_seo_score(state["scripts"])

    # Update state through result
    state["seo_score"] = seo_score
    state["keyword_density"] = self._analyze_keywords(state["scripts"])

    return AgentResult(...)
```

---

## Custom Routing Logic

For complex routing beyond "approve → next" or "reject → writer":

```python
async def process(self, state: PipelineState) -> AgentResult:
    # Analyze scripts
    issues = self._check_scripts(state["scripts"])

    # Custom routing based on issue type
    if "factual_errors" in issues:
        next_agent = "factchecker"  # Skip to fact checker
    elif "readability_issues" in issues:
        next_agent = "editor"  # Send back to editor
    else:
        next_agent = None  # Continue normal flow

    return AgentResult(
        approved="factual_errors" not in issues,
        output=state["scripts"],
        feedback=self._format_issues(issues),
        next_agent=next_agent  # Custom routing
    )
```

Update pipeline builder to handle custom routing:

```python
# core/pipeline.py
def _should_route_back(state: PipelineState, agent_result: AgentResult) -> str:
    # Check for custom routing first
    if agent_result.next_agent:
        return agent_result.next_agent

    # Default: reject → writer
    if not agent_result.approved:
        return "writer"

    # Default: continue to next agent
    return "next"
```

---

## Adding New Data Sources

Beyond article scrapers, you might want other content sources:

### 1. Create Scraper

```python
# scrapers/youtube_scraper.py
from youtube_transcript_api import YouTubeTranscriptApi

class YouTubeScraper:
    async def fetch(self, video_url: str) -> str:
        """Extract transcript from YouTube video."""
        video_id = self._extract_video_id(video_url)
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        return " ".join([entry["text"] for entry in transcript])
```

### 2. Register in Factory

```python
# scrapers/__init__.py
SCRAPER_REGISTRY = {
    "article": ArticleScraper,
    "youtube": YouTubeScraper,
    "podcast": PodcastScraper,
}

def get_scraper(source_type: str):
    return SCRAPER_REGISTRY[source_type]()
```

### 3. Use in Pipeline

```python
# Determine source type
source_type = "youtube" if "youtube.com" in url else "article"
scraper = get_scraper(source_type)
content = await scraper.fetch(url)
```

---

## Testing New Agents

### Unit Test Template

```python
# tests/agents/test_seo_agent.py
import pytest
from agents.seo_agent import SEOAgent
from core.state import PipelineState, Script

@pytest.mark.asyncio
async def test_seo_agent_approves_good_scripts():
    agent = SEOAgent(model="gpt-4o-mini")

    state = PipelineState(
        article_url="https://example.com",
        article_content="Test article",
        scripts=[
            Script(
                title="10 AI Tips You Need to Know",
                content="AI is transforming... [includes keywords]",
                duration=60
            )
        ],
        current_iteration=1,
        feedback_history=[],
        status="in_progress"
    )

    result = await agent.process(state)

    assert result.approved is True
    assert result.feedback is None

@pytest.mark.asyncio
async def test_seo_agent_rejects_poor_scripts():
    agent = SEOAgent(model="gpt-4o-mini")

    state = PipelineState(
        # ... state with scripts lacking keywords
    )

    result = await agent.process(state)

    assert result.approved is False
    assert "keyword" in result.feedback.lower()
```

### Integration Test

```python
# tests/test_pipeline_with_seo.py
@pytest.mark.asyncio
async def test_pipeline_with_seo_agent():
    pipeline = Pipeline.from_config("config.yaml")

    result = await pipeline.run(
        article_url="https://example.com/article"
    )

    # Verify SEO agent was executed
    assert "seo" in result.agents_executed
    assert result.state["seo_score"] is not None
```

---

## Performance Optimization

### Parallel Agent Execution

For agents that don't depend on each other:

```python
# Instead of sequential:
# writer → editor → seo → factchecker

# Run editor and seo in parallel:
workflow.add_node("writer", writer_agent.process)
workflow.add_node("parallel_check", parallel_review)
workflow.add_node("factchecker", factchecker_agent.process)

async def parallel_review(state: PipelineState):
    """Run editor and SEO checks in parallel."""
    editor_task = editor_agent.process(state)
    seo_task = seo_agent.process(state)

    editor_result, seo_result = await asyncio.gather(
        editor_task, seo_task
    )

    # Combine results
    approved = editor_result.approved and seo_result.approved
    feedback = [
        editor_result.feedback,
        seo_result.feedback
    ]

    return AgentResult(
        approved=approved,
        output=seo_result.output,  # Use SEO-modified version
        feedback="\n".join(f for f in feedback if f),
        next_agent=None
    )
```

### Caching LLM Responses

For expensive operations:

```python
from functools import lru_cache

class FactCheckerAgent(BaseAgent):
    @lru_cache(maxsize=100)
    def _check_fact_cached(self, fact: str) -> bool:
        """Cache fact-checking results."""
        # Expensive API call
        return self._verify_with_llm(fact)

    async def process(self, state: PipelineState) -> AgentResult:
        # Use cached version
        facts_valid = all(
            self._check_fact_cached(fact)
            for fact in self._extract_facts(state["scripts"])
        )
```

---

## Debugging Tips

### Enable Agent Logging

```python
import logging

class MyAgent(BaseAgent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(self.__class__.__name__)

    async def process(self, state: PipelineState) -> AgentResult:
        self.logger.info(f"Processing iteration {state['current_iteration']}")
        self.logger.debug(f"Scripts: {len(state['scripts'])}")

        result = await self._do_work(state)

        self.logger.info(f"Result: approved={result.approved}")
        return result
```

### Visualize Pipeline Graph

```python
from langgraph.graph import StateGraph

workflow = build_pipeline()  # Your pipeline builder
workflow.get_graph().draw_mermaid_png(output_file_path="pipeline.png")
```

### Dry Run Mode

```python
# config.yaml
pipeline:
  dry_run: true  # Agents return mock results

# Agent implementation
async def process(self, state: PipelineState) -> AgentResult:
    if self.config.get("dry_run"):
        return AgentResult(approved=True, output=state["scripts"])

    # Real processing
    ...
```
