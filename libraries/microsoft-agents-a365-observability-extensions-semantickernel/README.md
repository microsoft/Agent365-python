# Microsoft Agent 365 Observability Extensions - Semantic Kernel
[![PyPI version](https://badge.fury.io/py/microsoft-agents-a365-observability-extensions-semantic-kernel.svg)](https://badge.fury.io/py/microsoft-agents-a365-observability-extensions-semantic-kernel)

Semantic Kernel observability and tracing extensions for AI agent applications built with the Microsoft Agent 365 SDK. Enable comprehensive monitoring and telemetry for your Semantic Kernel-powered applications with automatic instrumentation and OpenTelemetry integration.

## What is this?

This library is part of the Microsoft Agent 365 SDK for Python - a comprehensive framework for building enterprise-grade conversational AI agents. The Semantic Kernel observability extensions specifically provide automatic instrumentation and monitoring for agents built using the Microsoft Semantic Kernel framework, capturing detailed traces, metrics, and performance data.

## Key Features

✅ **Automatic Semantic Kernel Instrumentation** - Zero-configuration tracing for Semantic Kernel components  
✅ **Kernel Function Monitoring** - Comprehensive tracking of function execution and performance  
✅ **Plugin Invocation Telemetry** - Granular monitoring of individual plugin calls and results  
✅ **Planner Execution Tracing** - Track planning processes and step-by-step execution  
✅ **OpenTelemetry Compliance** - Full compatibility with OpenTelemetry standards and tooling  
✅ **Production Ready** - Built for enterprise-scale monitoring and observability  

## Installation

```bash
pip install microsoft-agents-a365-observability-extensions-semantic-kernel
```

## Quick Start

### Basic Concepts

The Microsoft Agent 365 Semantic Kernel Observability Extensions automatically instrument your Semantic Kernel applications to provide comprehensive monitoring. Key concepts include:

- **Automatic Instrumentation**: Zero-configuration tracing for Semantic Kernel components
- **Kernel Tracing**: Monitor kernel creation, configuration, and execution
- **Function Monitoring**: Track kernel function calls and their performance
- **Plugin Execution**: Monitor individual plugin invocations and results
- **Planner Tracing**: Track planning processes and multi-step executions
- **Context Propagation**: Automatic correlation of related operations across async workflows

### Getting Started

1. Install the package: `pip install microsoft-agents-a365-observability-extensions-semantic-kernel`
2. Configure the observability system with your service details
3. Enable Semantic Kernel instrumentation with a single line of code
4. Your Semantic Kernel applications will be automatically traced

### Basic Integration

```python
from microsoft_agents_a365.observability.core.config import configure
from microsoft_agents_a365.observability.extensions.semantic_kernel import SemanticKernelInstrumentor

# Configure observability
configure(
    service_name="my-semantic-kernel-agent",
    service_namespace="ai.agents"
)

# Enable automatic instrumentation
instrumentor = SemanticKernelInstrumentor()
instrumentor.instrument()

# Your Semantic Kernel code is now automatically traced
```

## Supported Semantic Kernel Components

| Component | Instrumentation | Description |
|-----------|----------------|-------------|
| **Kernel** | Automatic | Kernel creation, configuration, and lifecycle monitoring |
| **Functions** | Automatic | Kernel function execution and performance tracking |
| **Plugins** | Automatic | Plugin invocation and result processing |
| **Planners** | Automatic | Planning process execution and step tracking |
| **Memory** | Automatic | Memory operations and retrieval monitoring |
| **Connectors** | Automatic | AI service connector calls and token usage |

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

# Semantic Kernel-specific settings
AZURE_OPENAI_API_KEY=your_api_key_here
AZURE_OPENAI_ENDPOINT=your_endpoint_here
OPENAI_API_KEY=your_openai_key_here
```

## Architecture

The observability extensions follow a layered architecture:

- **Instrumentor Layer**: Automatic detection and wrapping of Semantic Kernel components
- **Span Management**: Hierarchical span creation following OpenTelemetry conventions
- **Context Propagation**: Automatic correlation across async operations and function calls
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
| **Planning Agent** | Semantic Kernel agent with multi-step planning | `samples/semantic-kernel-planner/` |
| **Plugin Orchestrator** | Agent with multiple custom plugins | `samples/semantic-kernel-plugins/` |
| **Memory Assistant** | Conversational agent with persistent memory | `samples/semantic-kernel-memory/` |

## Requirements

- **Python**: 3.11+
- **Dependencies**:
  - `microsoft-agents-a365-observability-core >= 0.1.0`
  - `semantic-kernel >= 1.0.0`
  - `opentelemetry-api >= 1.20.0`
  - `opentelemetry-sdk >= 1.20.0`
  - `opentelemetry-instrumentation >= 0.41b0`

## Common Use Cases

### Development and Debugging
- Monitor kernel function execution flow and identify bottlenecks
- Track plugin selection and execution patterns
- Analyze token usage across different AI connectors
- Debug complex multi-step planning workflows

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
🧠 [Semantic Kernel Documentation](https://learn.microsoft.com/en-us/semantic-kernel/)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.