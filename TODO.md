# TODO - Agentic Video Script System

## Completed ✅

- [x] **Unified message history with BaseMessage** (Nov 2024)
  - Removed separate user_input and feedback fields
  - All agents use AIMessage with name parameter (writer/editor/factchecker)
  - Single source of truth for conversation flow
  - Follows LangChain best practices

- [x] **Pydantic structured outputs** (Nov 2024)
  - EditorOutput: approved, feedback
  - FactCheckerOutput: approved, feedback
  - Writer uses string parsing (due to tool binding limitation)

- [x] **Prompt improvements for tone matching** (Nov 2024)
  - Writer now reads user tone request from first draft (funny/serious/ironic)
  - Editor prioritizes tone matching as #1 criterion
  - Fixed issue where writer defaulted to dry/journalistic tone

- [x] **Modular agent structure** (Nov 2024)
  - agents/: agents.py, prompts.py, models.py, routes.py, state.py
  - tools/: scrapers.py
  - Moved examples to examples/ directory

## High Priority

- [x] **Fix approval flag persistence bug**
  - Flags don't reset when user provides new feedback
  - Current behavior: editor_approved=True persists across user iterations
  - Result: New user requests skip editor and go straight to factchecker
  - Fix: Reset flags in user_input_node when user provides feedback

- [ ] **Add checkpointing for state persistence**
  - Use SqliteSaver for conversation state
  - Enable resume/replay of interrupted runs
  - Debug past conversations
  - Implementation: `from langgraph.checkpoint.sqlite import SqliteSaver`

- [ ] **Different models for different agents**
  - Writer: gpt-4o-mini with temperature=0.7 (creative, cheap)
  - Editor: gpt-4o with temperature=0.3 (analytical, better judgment)
  - FactChecker: gpt-4o with temperature=0 (deterministic)
  - Cost optimization: ~47% cheaper than all gpt-4o
  - Note: Currently all use gpt-5-mini (placeholder)

## Medium Priority

- [ ] **Add interrupt-based human-in-the-loop**
  - Replace input() calls with LangGraph interrupts
  - Better for async/web UIs
  - `interrupt_before=["user_input_node"]`
  - Separates I/O from business logic

- [ ] **Message trimming (if needed)**
  - Current: No trimming (not needed for short task cycles)
  - Future: Keep first HumanMessage + recent N messages
  - Prevents token overflow on very long conversations
  - Decision: YAGNI for now, add if >20 messages per task

- [ ] **Async migration**
  - Convert invoke() to ainvoke()
  - Enable parallel operations
  - Better performance for web UIs
  - Phase 2 enhancement

- [ ] **Error handling and retries**
  - Add RunnableRetry to LLM calls
  - Retry on API failures (3 attempts)
  - Exponential backoff with jitter
  - Graceful degradation

- [ ] **Add UI (Textual TUI)**
  - Live pipeline status display
  - Real-time agent progress
  - Draft preview
  - Interactive feedback input
  - History browser

- [ ] **Add more tools to agents**
  - Writer: readability scorer, keyword extractor
  - Editor: grammar checker, tone analyzer
  - FactChecker: web search for real-time verification, source credibility checker
  - All: logging/telemetry tools

## Low Priority

- [ ] **LangSmith tracing**
  - Enable debugging and observability
  - Track token usage and latency
  - Set LANGCHAIN_TRACING_V2=true

- [ ] **Streaming for real-time output**
  - Use app.stream() instead of invoke()
  - Show agent progress as it happens
  - Better UX for terminal UI

- [ ] **Configuration-driven models**
  - Move model selection to config.yaml
  - Per-agent temperature/model settings
  - Easy experimentation

- [ ] **Extract tool calling to separate node**
  - More modular than loop inside writer
  - Cleaner separation of concerns
  - Better for graph visualization

- [ ] **Consider memory implementation**
  - Evaluate need for cross-run memory
  - Vector DB for previous scripts (if useful)
  - User preference storage
  - Performance pattern learning
  - Decision: Likely not needed for MVP

## Future Enhancements

- [ ] Async execution (ainvoke)
- [ ] Parallel agent execution where possible
- [ ] Caching for repeated content
- [ ] Batch processing multiple articles
- [ ] A/B testing different prompts
- [ ] Metrics and analytics dashboard
- [ ] Export to video production formats
- [ ] Integration with video editing tools
- [ ] Multi-language support
- [ ] Human-in-the-loop approval workflow

## Documentation

- [ ] Add usage examples to docs/
- [ ] Create agent prompt engineering guide
- [ ] Document model selection rationale
- [ ] Add troubleshooting guide
- [ ] Create contributing guidelines

## Testing

- [ ] Unit tests for individual agents
- [ ] Integration tests for full pipeline
- [ ] Test rejection loop edge cases
- [ ] Performance benchmarks
- [ ] Cost analysis per article
