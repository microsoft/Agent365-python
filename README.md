# Microsoft Agent 365 SDK - Python

[![PyPI](https://img.shields.io/pypi/v/microsoft-agents-a365-observability-core?label=PyPI&logo=pypi)](https://pypi.org/search/?q=microsoft-agents-a365)
[![PyPI Downloads](https://img.shields.io/pypi/dm/microsoft-agents-a365-observability-core?label=Downloads&logo=pypi)](https://pypi.org/search/?q=microsoft-agents-a365)
[![CI - Build, Test, and Publish SDKs](https://github.com/microsoft/Agent365-python/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/microsoft/Agent365-python/actions/workflows/ci.yml)
[![License](https://img.shields.io/github/license/microsoft/Agent365-python?label=License)](LICENSE.md)
[![Python Version](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python)](https://www.python.org/)
[![Contributors](https://img.shields.io/github/contributors/microsoft/Agent365-python?label=Contributors&logo=github)](https://github.com/microsoft/Agent365-python/graphs/contributors)

> #### Note:
> Use the information in this README to contribute to this open-source project. To learn about using this SDK in your projects, refer to the [Microsoft Agent 365 Developer documentation](https://learn.microsoft.com/microsoft-agent-365/developer/).

The Microsoft Agent 365 SDK extends the Microsoft 365 Agents SDK with enterprise-grade capabilities for building sophisticated agents. This SDK provides comprehensive tooling for observability, notifications, runtime utilities, and development tools that help developers create production-ready agents for platforms including M365, Teams, Copilot Studio, and Webchat.

The Microsoft Agent 365 SDK focuses on four core areas:

- **Observability**: Comprehensive tracing, caching, and monitoring capabilities for agent applications
- **Notifications**: Agent notification services and models for handling user notifications
- **Runtime**: Core utilities and extensions for agent runtime operations
- **Tooling**: Developer tools and utilities for building sophisticated agent applications

## Survey

Please help improve the Microsoft Agent 365 SDK and CLI by taking our survey: [Agent365 SDK Integration Feedback Survey](https://forms.office.com/r/wj0edu361y)

## Current Project State

This project is currently in active development. Packages are published to PyPI as they become available.

### Public PyPI feed

The best way to consume this SDK is via our PyPI packages found here: [pypi.org](https://pypi.org/search/?q=microsoft-agents-a365). All packages begin with **microsoft-agents-a365**.

## Working with this codebase

### Prerequisites

- Python 3.10 or later
- pip or uv package manager
- Git

### Building the project

1. Clone the repository:

   ```bash
   git clone https://github.com/microsoft/Agent365-python.git
   cd Agent365-python
   ```

2. Create a virtual environment:

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Build the packages:

   ```bash
   # Set the version
   export AGENT365_PYTHON_SDK_PACKAGE_VERSION="0.1.0"  # On Windows: $env:AGENT365_PYTHON_SDK_PACKAGE_VERSION = "0.1.0"
   
   # Build all packages
   uv build --all-packages --wheel
   ```

4. Run tests:

   ```bash
   pytest tests/
   ```

## Project Structure

- **libraries/microsoft-agents-a365-notifications**: Microsoft Agent 365 Notifications SDK - Agent notification services and models
- **libraries/microsoft-agents-a365-observability-core**: Microsoft Agent 365 Observability Core - Core observability functionality
- **libraries/microsoft-agents-a365-observability-extensions-agentframework**: Agent Framework observability extensions
- **libraries/microsoft-agents-a365-observability-extensions-langchain**: LangChain observability extensions
- **libraries/microsoft-agents-a365-observability-extensions-openai**: OpenAI observability extensions
- **libraries/microsoft-agents-a365-observability-extensions-semantickernel**: Semantic Kernel observability extensions
- **libraries/microsoft-agents-a365-runtime**: Microsoft Agent 365 Runtime - Core runtime utilities and extensions
- **libraries/microsoft-agents-a365-tooling**: Microsoft Agent 365 Tooling SDK - Agent tooling and MCP integration
- **libraries/microsoft-agents-a365-tooling-extensions-agentframework**: Agent Framework tooling extensions
- **libraries/microsoft-agents-a365-tooling-extensions-azureaifoundry**: Azure AI Foundry tooling extensions
- **libraries/microsoft-agents-a365-tooling-extensions-openai**: OpenAI tooling extensions
- **libraries/microsoft-agents-a365-tooling-extensions-semantickernel**: Semantic Kernel tooling extensions
- For sample applications, see the [Microsoft Agent 365 SDK Samples repository](https://github.com/microsoft/Agent365-Samples/tree/main/python)
- **tests/**: Unit and integration tests

## Support

For issues, questions, or feedback:

- **Issues**: Please file issues in the [GitHub Issues](https://github.com/microsoft/Agent365-python/issues) section
- **Documentation**: See the [Microsoft Agents 365 developer documentation](https://learn.microsoft.com/microsoft-agent-365/developer/)
- **Security**: For security issues, please see [SECURITY.md](SECURITY.md)

## Contributing

This project welcomes contributions and suggestions. Most contributions require you to agree to a Contributor License Agreement (CLA) declaring that you have the right to, and actually do, grant us the rights to use your contribution. For details, visit <https://cla.opensource.microsoft.com>.

When you submit a pull request, a CLA bot will automatically determine whether you need to provide a CLA and decorate the PR appropriately (e.g., status check, comment). Simply follow the instructions provided by the bot. You will only need to do this once across all repos using our CLA.

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/). For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.

## Useful Links

### Microsoft 365 Agents SDK

The core SDK for building conversational AI agents for Microsoft 365 platforms.

- [Microsoft 365 Agents SDK - C# /.NET repository](https://github.com/Microsoft/Agents-for-net)
- [Microsoft 365 Agents SDK - NodeJS /TypeScript repository](https://github.com/Microsoft/Agents-for-js)
- [Microsoft 365 Agents SDK - Python repository](https://github.com/Microsoft/Agents-for-python)
- [Microsoft 365 Agents documentation](https://learn.microsoft.com/microsoft-365/agents-sdk/)

### Microsoft Agent 365 SDK

Enterprise-grade extensions for observability, notifications, runtime utilities, and developer tools.

- [Microsoft Agent 365 SDK - C# /.NET repository](https://github.com/microsoft/Agent365-dotnet)
- [Microsoft Agent 365 SDK - Python repository](https://github.com/microsoft/Agent365-python) - You are here
- [Microsoft Agent 365 SDK - Node.js/TypeScript repository](https://github.com/microsoft/Agent365-nodejs)
- [Microsoft Agent 365 SDK Samples repository](https://github.com/microsoft/Agent365-Samples)
- [Microsoft Agent 365 developer documentation](https://learn.microsoft.com/microsoft-agent-365/developer/)

### Additional Resources

- [Python Documentation](https://learn.microsoft.com/python/api/?view=m365-agents-sdk&preserve-view=true)


## Trademarks

*Microsoft, Windows, Microsoft Azure and/or other Microsoft products and services referenced in the documentation may be either trademarks or registered trademarks of Microsoft in the United States and/or other countries. The licenses for this project do not grant you rights to use any Microsoft names, logos, or trademarks. Microsoft's general trademark guidelines can be found at http://go.microsoft.com/fwlink/?LinkID=254653.*

## License

Copyright (c) Microsoft Corporation. All rights reserved.

Licensed under the MIT License - see the [LICENSE](LICENSE.md) file for details.
