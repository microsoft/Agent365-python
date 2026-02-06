# Observability Extensions - LangChain - Design Document

This document describes the architecture and design of the `microsoft-agents-a365-observability-extensions-langchain` package.

## Overview

This extension integrates the Agent365 observability infrastructure with LangChain, enabling automatic tracing of LangChain chain executions, LLM calls, and tool invocations.

## Key Components

### LangChainTracerInstrumentor

The main instrumentor class that integrates with LangChain's callback system.

```python
from microsoft_agents_a365.observability.extensions.langchain import LangChainTracerInstrumentor

# Initialize and instrument
instrumentor = LangChainTracerInstrumentor()
instrumentor.instrument()
```

### Tracer Callback

Custom LangChain callback handler that creates Agent365 spans for:
- Chain executions
- LLM calls (with token tracking)
- Tool executions

### Integration Flow

```
LangChain Execution
       │
       ▼
Callback Handler (on_llm_start, on_tool_start, etc.)
       │
       ▼
InferenceScope / ExecuteToolScope
       │
       ▼
Agent365 Backend
```

## File Structure

```
microsoft_agents_a365/observability/extensions/langchain/
├── __init__.py              # Public API
├── tracer.py                # LangChain tracer callback
├── tracer_instrumentor.py   # Main instrumentor
└── utils.py                 # Utility functions
```

## LangChain Callback Events

| Event | Agent365 Scope |
|-------|----------------|
| `on_llm_start` | `InferenceScope` |
| `on_llm_end` | Records tokens, finish reason |
| `on_tool_start` | `ExecuteToolScope` |
| `on_tool_end` | Records tool result |
| `on_chain_start` | `InvokeAgentScope` |
| `on_chain_end` | Records chain output |

## Dependencies

- `langchain` - LangChain framework
- `microsoft-agents-a365-observability-core` - Core observability
