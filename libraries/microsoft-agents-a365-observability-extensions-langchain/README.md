# Microsoft Agent 365 Observability Extensions - LangChain
[![PyPI version](https://badge.fury.io/py/microsoft-agents-a365-observability-extensions-langchain.svg)](https://badge.fury.io/py/microsoft-agents-a365-observability-extensions-langchain)

LangChain observability and tracing extensions for AI agent applications built with the Microsoft Agent 365 SDK. Enable comprehensive monitoring and telemetry for your LangChain-powered agents with automatic instrumentation and OpenTelemetry integration.

## What is this?

This library is part of the Microsoft Agent 365 SDK for Python - a comprehensive framework for building enterprise-grade conversational AI agents. The LangChain observability extensions specifically provide automatic instrumentation and monitoring for agents built using the LangChain framework, capturing detailed traces, metrics, and performance data.

## Key Features

✅ **Automatic LangChain Instrumentation** - Zero-configuration tracing for chains, agents, and tools  
✅ **Chain Execution Monitoring** - Detailed visibility into sequential and parallel chain operations  
✅ **Agent Workflow Tracing** - Comprehensive tracking of agent reasoning and decision-making  
✅ **Tool Invocation Telemetry** - Granular monitoring of individual tool calls and performance  
✅ **OpenTelemetry Compliance** - Full compatibility with OpenTelemetry standards and tooling  
✅ **Production Ready** - Built for enterprise-scale monitoring and observability  

## Installation

```bash
pip install microsoft-agents-a365-observability-extensions-langchain
```

## Quick Start

### Basic Concepts

The Microsoft Agent 365 LangChain Observability Extensions automatically instrument your LangChain applications to provide comprehensive monitoring. Key concepts include:

- **Automatic Instrumentation**: Zero-configuration tracing for LangChain components
- **Chain Tracing**: Monitor the flow and performance of LangChain chains
- **Agent Monitoring**: Track agent reasoning, tool selection, and execution
- **Context Propagation**: Automatic correlation of related operations across async workflows

### Getting Started

1. Install the package: `pip install microsoft-agents-a365-observability-extensions-langchain`
2. Configure the observability system with your service details
3. Enable LangChain instrumentation with a single line of code
4. Your LangChain applications will be automatically traced

### Basic Integration

```python
from microsoft_agents_a365.observability.core.config import configure
from microsoft_agents_a365.observability.extensions.langchain import CustomLangChainInstrumentor

# Configure observability
configure(
    service_name="my-langchain-agent",
    service_namespace="ai.agents"
)

# Enable automatic instrumentation
instrumentor = CustomLangChainInstrumentor()
instrumentor.instrument()

# Your LangChain code is now automatically traced
```

## Supported LangChain Components

| Component | Instrumentation | Description |
|-----------|----------------|-------------|
| **Chains** | Automatic | Sequential and parallel chain execution tracking |
| **Agents** | Automatic | Agent reasoning, tool selection, and execution monitoring |
| **Tools** | Automatic | Individual tool invocation and performance metrics |
| **LLMs** | Automatic | Language model calls, token usage, and latency tracking |
| **Retrievers** | Automatic | Document retrieval and similarity search operations |
| **Memory** | Automatic | Conversation memory and context management |

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

# LangChain-specific settings  
LANGCHAIN_TRACING_V2=false    # Disable to avoid duplicate tracing
```

## Architecture

The observability extensions follow a layered architecture:

- **Instrumentor Layer**: Automatic detection and wrapping of LangChain components
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
| **Research Agent** | LangChain agent with search and analysis tools | `samples/langchain-research-agent/` |
| **Document Assistant** | Multi-step document processing chains | `samples/langchain-document-assistant/` |
| **Data Analyst** | SQL and visualization agent with observability | `samples/langchain-data-analyst/` |

## Requirements

- **Python**: 3.11+
- **Dependencies**:
  - `microsoft-agents-a365-observability-core >= 0.1.0`
  - `langchain >= 0.1.0`
  - `langchain-core >= 0.1.0`
  - `opentelemetry-api >= 1.20.0`
  - `opentelemetry-sdk >= 1.20.0`
  - `opentelemetry-instrumentation >= 0.41b0`

## Common Use Cases

### Development and Debugging
- Monitor chain execution flow and identify bottlenecks
- Track agent reasoning and tool selection patterns
- Analyze LLM token usage and optimize costs
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
📊 [OpenTelemetry Documentation](https://opentelemetry.io/)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.