# Examples

This directory contains early experimental scripts used during initial LangChain/LangGraph exploration. These are **not part of the main application** - they were used for learning and testing concepts before building the actual video script pipeline.

## Files

### example1.py
- **Purpose**: Basic LangChain tool calling example
- **Features**: Demonstrates how to define and use tools (multiply, add, etc.) with LLMs
- **Status**: Learning example, not actively maintained

### example2.py
- **Purpose**: Multi-agent essay writing system
- **Features**: Plan → Write → Critique loop with state management
- **Key concepts tested**:
  - LangGraph state machine with TypedDict
  - SqliteSaver for checkpointing
  - Multi-agent rejection loops
  - Agent communication patterns
- **Status**: Prototype that informed the main pipeline design

## Relation to Main Project

The patterns and lessons learned from these examples influenced the design of the main video script pipeline in `src/langchain_examples/`:

- **State management**: AgentState → PipelineState
- **Rejection loops**: Critique agent → Editor/FactChecker agents
- **Message handling**: Tested different approaches before settling on unified BaseMessage list

## Running Examples

These examples may have outdated dependencies or may not run without modification. They are kept for reference only.

If you want to experiment:

```bash
cd examples
python example1.py  # May need dependency updates
python example2.py  # May need dependency updates
```

## Main Application

For the actual working system, see:
- **Entry point**: `src/langchain_examples/main.py`
- **Documentation**: `CLAUDE.md`, `docs/`
- **Current status**: See `TODO.md`
