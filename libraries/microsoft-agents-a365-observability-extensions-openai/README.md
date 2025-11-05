# Microsoft Agent 365 Observability Extensions - OpenAI Agents
[![PyPI version](https://badge.fury.io/py/microsoft-agents-a365-observability-extensions-openai.svg)](https://badge.fury.io/py/microsoft-agents-a365-observability-extensions-openai)

OpenAI Agents SDK observability and tracing extensions for AI agent applications built with the Microsoft Agent 365 SDK. Enable comprehensive monitoring and telemetry for your OpenAI Agents-powered applications with automatic instrumentation and OpenTelemetry integration.

## What is this?

This library is part of the Microsoft Agent 365 SDK for Python - a comprehensive framework for building enterprise-grade conversational AI agents. The OpenAI Agents observability extensions specifically provide automatic instrumentation and monitoring for agents built using the OpenAI Agents SDK, capturing detailed traces, metrics, and performance data.

## Key Features

✅ **Automatic OpenAI Agents Instrumentation** - Zero-configuration tracing for OpenAI Agents SDK components  
✅ **Agent Workflow Monitoring** - Comprehensive tracking of agent execution and decision-making  
✅ **Tool Invocation Telemetry** - Granular monitoring of individual tool calls and performance  
✅ **Thread Management Tracing** - Track conversation threads and message flows  
✅ **OpenTelemetry Compliance** - Full compatibility with OpenTelemetry standards and tooling  
✅ **Production Ready** - Built for enterprise-scale monitoring and observability  

## Installation

```bash
pip install microsoft-agents-a365-observability-extensions-openai
```

## Quick Start

### Basic Concepts

The Microsoft Agent 365 OpenAI Agents Observability Extensions automatically instrument your OpenAI Agents applications to provide comprehensive monitoring. Key concepts include:

- **Automatic Instrumentation**: Zero-configuration tracing for OpenAI Agents SDK components
- **Agent Tracing**: Monitor agent creation, execution, and lifecycle events
- **Thread Monitoring**: Track conversation threads and message processing
- **Tool Execution**: Monitor individual tool calls and their performance
- **Context Propagation**: Automatic correlation of related operations across async workflows

### Getting Started

1. Install the package: `pip install microsoft-agents-a365-observability-extensions-openai`
2. Configure the observability system with your service details
3. Enable OpenAI Agents instrumentation with a single line of code
4. Your OpenAI Agents applications will be automatically traced

### Basic Integration

```python
from microsoft_agents_a365.observability.core.config import configure
from microsoft_agents_a365.observability.extensions.openai_agents import OpenAIAgentsTraceInstrumentor

# Configure observability
configure(
    service_name="my-openai-agent",
    service_namespace="ai.agents"
)

# Enable automatic instrumentation
instrumentor = OpenAIAgentsTraceInstrumentor()
instrumentor.instrument()

# Your OpenAI Agents code is now automatically traced
```

## Supported OpenAI Agents Components

| Component | Instrumentation | Description |
|-----------|----------------|-------------|
| **Agents** | Automatic | Agent creation, execution, and lifecycle monitoring |
| **Threads** | Automatic | Conversation thread management and message flow tracking |
| **Tools** | Automatic | Individual tool invocation and performance metrics |
| **Runs** | Automatic | Agent run execution, status changes, and completion tracking |
| **Messages** | Automatic | Message creation, processing, and response generation |
| **Function Calls** | Automatic | Function execution and result processing |

## Advanced Usage

### Observability Features

- **Performance Metrics**: Execution times, token usage, and throughput analysis
- **Error Tracking**: Comprehensive error capture and failure analysis
- **Context Correlation**: Automatic linking of related operations across async workflows
- **Custom Attributes**: Add business-specific metadata to traces and spans

### Environment Configuration

```properties
# Core observability settings
ENABLE_OBSERVABILITY=true
ENABLE_A365_OBSERVABILITY_EXPORTER=true
PYTHON_ENVIRONMENT=production

# OpenAI Agents-specific settings
OPENAI_API_KEY=your_api_key_here
OPENAI_ORG_ID=your_org_id_here
```

## Architecture

The observability extensions follow a layered architecture:

- **Instrumentor Layer**: Automatic detection and wrapping of OpenAI Agents SDK components
- **Span Management**: Hierarchical span creation following OpenTelemetry conventions
- **Context Propagation**: Automatic correlation across async operations and tool calls
- **Export Pipeline**: Efficient batching and export to observability backends

## Integration with Microsoft Agent 365 SDK

This package works seamlessly with other Microsoft Agent 365 SDK components:

| Package | Integration |
|---------|-------------|
| `microsoft-agents-a365-observability-core` | Core telemetry and tracing infrastructure |
| `microsoft-agents-a365-runtime` | Agent execution runtime and lifecycle |
| `microsoft-agents-a365-tooling` | Tool management and execution |
| `microsoft-agents-a365-hosting-core` | Agent hosting and middleware |

## Sample Applications

Check out these working examples:

| Sample | Description | Location |
|--------|-------------|----------|
| **Customer Service Agent** | OpenAI agent with support ticket handling | `samples/openai-customer-service/` |
| **Code Assistant** | Programming assistant with code analysis tools | `samples/openai-code-assistant/` |
| **Data Analysis Agent** | Data processing agent with visualization tools | `samples/openai-data-analyst/` |

## Requirements

- **Python**: 3.11+
- **Dependencies**:
  - `microsoft-agents-a365-observability-core >= 0.1.0`
  - `openai-agents >= 0.2.6`
  - `opentelemetry-api >= 1.20.0`
  - `opentelemetry-sdk >= 1.20.0`
  - `opentelemetry-instrumentation >= 0.41b0`

## Common Use Cases

### Development and Debugging
- Monitor agent execution flow and identify bottlenecks
- Track tool selection and execution patterns
- Analyze token usage and optimize costs
- Debug complex multi-step agent workflows

### Production Monitoring
- Monitor agent performance and reliability at scale
- Track success rates and error patterns
- Analyze user interaction patterns and agent effectiveness
- Set up alerts for performance degradation or failures

### Analytics and Optimization
- Understand agent behavior and usage patterns
- Identify opportunities for workflow optimization
- Monitor cost and performance trade-offs
- Generate insights for agent improvement

## Quick Links

📦 [All SDK Packages on PyPI](TODO: Update when packages are published)  
📖 [Complete Documentation](https://github.com/microsoft/Agent365/tree/main/python)  
💡 [Python Samples Repository](https://github.com/microsoft/Agent365/tree/main/samples)  
🐛 [Report Issues](https://github.com/microsoft/Agent365/issues)  
🤖 [OpenAI Agents Documentation](https://platform.openai.com/docs/assistants/overview)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.