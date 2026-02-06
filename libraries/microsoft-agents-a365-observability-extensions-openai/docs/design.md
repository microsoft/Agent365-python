# Observability Extensions - OpenAI - Design Document

This document describes the architecture and design of the `microsoft-agents-a365-observability-extensions-openai` package.

## Overview

This extension integrates the Agent365 observability infrastructure with the OpenAI Agents SDK, enabling automatic tracing of OpenAI API calls.

## Key Components

### OpenAIAgentsTraceInstrumentor

The main instrumentor class that wraps OpenAI agent operations.

```python
from microsoft_agents_a365.observability.extensions.openai import OpenAIAgentsTraceInstrumentor

# Initialize instrumentor
instrumentor = OpenAIAgentsTraceInstrumentor()

# Instrument OpenAI calls
instrumentor.instrument()
```

### TraceProcessor

Custom processor that intercepts OpenAI SDK trace events and converts them to Agent365 spans.

### Integration Flow

```
OpenAI Agents SDK
       │
       ▼
TraceInstrumentor (intercepts calls)
       │
       ▼
TraceProcessor (creates Agent365 spans)
       │
       ▼
InferenceScope / ExecuteToolScope
       │
       ▼
Agent365 Backend
```

## File Structure

```
microsoft_agents_a365/observability/extensions/openai/
├── __init__.py              # Public API
├── trace_instrumentor.py    # OpenAIAgentsTraceInstrumentor
├── trace_processor.py       # Trace event processor
├── constants.py             # OpenAI-specific constants
└── utils.py                 # Utility functions
```

## Dependencies

- `openai-agents` - OpenAI Agents SDK
- `microsoft-agents-a365-observability-core` - Core observability
