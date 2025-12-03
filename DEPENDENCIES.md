# Agent 365 SDK Python Package Dependencies

This diagram shows the internal dependencies between Agent 365 SDK Python packages.

```mermaid
graph TD
    %% Package Nodes
    notifications["microsoft-agents-a365-notifications"]
    observability_core["microsoft-agents-a365-observability-core"]
    observability_extensions_langchain["microsoft-agents-a365-observability-extensions-langchain"]
    observability_extensions_openai["microsoft-agents-a365-observability-extensions-openai"]
    observability_extensions_semantic_kernel["microsoft-agents-a365-observability-extensions-semantic-kernel"]
    observability_extensions_agent_framework["microsoft-agents-a365-observability-extensions-agent-framework"]
    runtime["microsoft-agents-a365-runtime"]
    tooling["microsoft-agents-a365-tooling"]
    tooling_extensions_azureaifoundry["microsoft-agents-a365-tooling-extensions-azureaifoundry"]
    tooling_extensions_openai["microsoft-agents-a365-tooling-extensions-openai"]
    tooling_extensions_semantickernel["microsoft-agents-a365-tooling-extensions-semantickernel"]
    tooling_extensions_agentframework["microsoft-agents-a365-tooling-extensions-agentframework"]

    %% Dependencies
    observability_core --> runtime
    observability_extensions_langchain --> observability_core
    observability_extensions_openai --> observability_core
    observability_extensions_semantic_kernel --> observability_core
    observability_extensions_agent_framework --> observability_core
    tooling_extensions_azureaifoundry --> tooling
    tooling_extensions_openai --> tooling
    tooling_extensions_semantickernel --> tooling
    tooling_extensions_agentframework --> tooling

    %% Styling
    classDef notifications fill:#ffcdd2,stroke:#c62828,color:#280505,stroke-width:2px
    class notifications notifications
    classDef runtime fill:#bbdefb,stroke:#1565c0,color:#0d1a26,stroke-width:2px
    class runtime runtime
    classDef observability fill:#c8e6c9,stroke:#2e7d32,color:#142a14,stroke-width:2px
    class observability_core observability
    classDef observability_extensions fill:#e8f5e9,stroke:#66bb6a,color:#1f3d1f,stroke-width:2px
    class observability_extensions_langchain,observability_extensions_openai,observability_extensions_semantic_kernel,observability_extensions_agent_framework observability_extensions
    classDef tooling fill:#ffe0b2,stroke:#e65100,color:#331a00,stroke-width:2px
    class tooling tooling
    classDef tooling_extensions fill:#fff3e0,stroke:#fb8c00,color:#4d2600,stroke-width:2px
    class tooling_extensions_azureaifoundry,tooling_extensions_openai,tooling_extensions_semantickernel,tooling_extensions_agentframework tooling_extensions
```

## Package Types

- **Notifications** (Red): Notification and messaging extensions
- **Runtime** (Blue): Core runtime components
- **Observability** (Green): Telemetry and monitoring core
- **Observability Extensions** (Light Green): Framework-specific observability integrations
- **Tooling** (Orange): Agent tooling SDK core
- **Tooling Extensions** (Light Orange): Framework-specific tooling integrations
