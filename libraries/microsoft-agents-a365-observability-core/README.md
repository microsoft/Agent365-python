# microsoft-agents-a365-observability-core

[![PyPI](https://img.shields.io/pypi/v/microsoft-agents-a365-observability-core?label=PyPI&logo=pypi)](https://pypi.org/project/microsoft-agents-a365-observability-core)
[![PyPI Downloads](https://img.shields.io/pypi/dm/microsoft-agents-a365-observability-core?label=Downloads&logo=pypi)](https://pypi.org/project/microsoft-agents-a365-observability-core)

Telemetry, tracing, and monitoring components for AI agents built on OpenTelemetry. This package provides structured spans for agent invocation, tool execution, and LLM inference with context propagation and pluggable exporters.

> **Already using OpenTelemetry?** This SDK detects an existing `TracerProvider` and adds its processors to it — your spans flow to your existing backend (Azure Monitor, OTLP collector, vendor exporter, etc.) and, when `ENABLE_A365_OBSERVABILITY_EXPORTER` is enabled with a configured `token_resolver`, also to the Agent 365 backend. See [Integrating with existing OpenTelemetry](../../docs/integrating-with-existing-opentelemetry.md) for setup patterns and troubleshooting.

## Installation

```bash
pip install microsoft-agents-a365-observability-core
```

## Usage

For usage examples and detailed documentation, see the [Observability documentation](https://learn.microsoft.com/microsoft-agent-365/developer/observability?tabs=python) on Microsoft Learn.

### Agent 365 OBS export authentication

When `ENABLE_A365_OBSERVABILITY_EXPORTER` is enabled, exports always use the
S2S OTLP route:

```text
/observabilityService/tenants/{tenantId}/otlp/agents/{agentId}/traces?api-version=1
```

The deprecated `use_s2s_endpoint` option is ignored, even when set to `False`;
domain overrides change only the host. The exporter never falls back to
`/observability` and never reads delegated request-context tokens.

Provide an app-only OBS `token_resolver(agent_id, tenant_id)` for the exporting
agent identity. The resolver is invoked for each export batch and identity
group, so it should cache the acquired token and refresh near expiry. Empty
tokens or resolver failures fail that export batch without sending an HTTP
request or retrying on a delegated route. If the Agent 365 exporter is enabled
without a resolver, the existing `ConsoleSpanExporter` fallback is kept and
nothing is sent to Agent 365.

Resolvers should request the OBS resource `/.default` scope
(`api://9b975845-388f-4429-889e-eab1ef63949c/.default`) and validate the token
before returning it: reject any `scp` claim and any `idtyp` other than `app`;
when `idtyp` is absent, accept only a non-empty `roles` array or a non-empty
`oid` equal to `sub`; also verify `aud` is the OBS resource and the token is not
expired. Workload authentication for MCP, Microsoft Graph, and other OBO calls
is separate and unchanged.

## Support

For issues, questions, or feedback:

- File issues in the [GitHub Issues](https://github.com/microsoft/Agent365-python/issues) section
- See the [main documentation](../../README.md) for more information
 
## Trademarks
 
*Microsoft, Windows, Microsoft Azure and/or other Microsoft products and services referenced in the documentation may be either trademarks or registered trademarks of Microsoft in the United States and/or other countries. The licenses for this project do not grant you rights to use any Microsoft names, logos, or trademarks. Microsoft's general trademark guidelines can be found at http://go.microsoft.com/fwlink/?LinkID=254653.*

## License

Copyright (c) Microsoft Corporation. All rights reserved.

Licensed under the MIT License - see the [LICENSE](../../LICENSE.md) file for details.
