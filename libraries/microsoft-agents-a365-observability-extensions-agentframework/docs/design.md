# Observability Extensions - Agent Framework - Design Document

This document describes the architecture and design of the `microsoft-agents-a365-observability-extensions-agentframework` package.

## Overview

This extension integrates the Agent365 observability infrastructure with the Microsoft Agents SDK (Agent Framework), enabling automatic tracing of agent operations.

## Key Components

### AgentFrameworkTraceInstrumentor

The main instrumentor class that integrates with Agent Framework operations.

```python
from microsoft_agents_a365.observability.extensions.agentframework import (
    AgentFrameworkTraceInstrumentor
)

# Initialize and instrument
instrumentor = AgentFrameworkTraceInstrumentor()
instrumentor.instrument()
```

### SpanProcessor

Custom span processor that captures Agent Framework-specific telemetry.

### Integration Flow

```
Agent Framework Execution
       │
       ▼
TraceInstrumentor (intercepts agent calls)
       │
       ▼
SpanProcessor (creates Agent365 spans)
       │
       ▼
InvokeAgentScope / InferenceScope / ExecuteToolScope
       │
       ▼
Agent365 Backend
```

## File Structure

```
microsoft_agents_a365/observability/extensions/agentframework/
├── __init__.py              # Public API
├── trace_instrumentor.py    # Main instrumentor
└── span_processor.py        # Custom span processor
```

## Dependencies

- `agent-framework-azure-ai` - Microsoft Agents SDK
- `microsoft-agents-a365-observability-core` - Core observability
