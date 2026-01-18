# Observability Extensions - Semantic Kernel - Design Document

This document describes the architecture and design of the `microsoft-agents-a365-observability-extensions-semantickernel` package.

## Overview

This extension integrates the Agent365 observability infrastructure with Semantic Kernel, enabling automatic tracing of kernel function executions and LLM calls.

## Key Components

### SemanticKernelTraceInstrumentor

The main instrumentor class that integrates with Semantic Kernel's telemetry.

```python
from microsoft_agents_a365.observability.extensions.semantickernel import (
    SemanticKernelTraceInstrumentor
)

# Initialize and instrument
instrumentor = SemanticKernelTraceInstrumentor()
instrumentor.instrument()
```

### SpanProcessor

Custom span processor that captures Semantic Kernel-specific telemetry.

### Integration Flow

```
Semantic Kernel Execution
       │
       ▼
TraceInstrumentor (intercepts kernel calls)
       │
       ▼
SpanProcessor (creates Agent365 spans)
       │
       ▼
InferenceScope / ExecuteToolScope
       │
       ▼
Agent365 Backend
```

## File Structure

```
microsoft_agents_a365/observability/extensions/semantickernel/
├── __init__.py              # Public API
├── trace_instrumentor.py    # Main instrumentor
└── span_processor.py        # Custom span processor
```

## Dependencies

- `semantic-kernel` - Semantic Kernel framework
- `microsoft-agents-a365-observability-core` - Core observability
