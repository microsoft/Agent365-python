# Microsoft Agent 365 SDK Python Package Dependencies

This diagram shows the internal dependencies between Microsoft Agent 365 SDK Python packages.

```mermaid
graph LR
    %% Package Nodes
    microsoft_agents_a365_notifications["microsoft-agents-a365-notifications"]
    microsoft_agents_a365_observability_core["microsoft-agents-a365-observability-core"]
    microsoft_agents_a365_observability_extensions_langchain["microsoft-agents-a365-observability-extensions-langchain"]
    microsoft_agents_a365_observability_extensions_openai["microsoft-agents-a365-observability-extensions-openai"]
    microsoft_agents_a365_observability_extensions_semantic_kernel["microsoft-agents-a365-observability-extensions-semantic-kernel"]
    microsoft_agents_a365_observability_extensions_agent_framework["microsoft-agents-a365-observability-extensions-agent-framework"]
    microsoft_agents_a365_runtime["microsoft-agents-a365-runtime"]
    microsoft_agents_a365_tooling["microsoft-agents-a365-tooling"]
    microsoft_agents_a365_tooling_extensions_azureaifoundry["microsoft-agents-a365-tooling-extensions-azureaifoundry"]
    microsoft_agents_a365_tooling_extensions_openai["microsoft-agents-a365-tooling-extensions-openai"]
    microsoft_agents_a365_tooling_extensions_semantickernel["microsoft-agents-a365-tooling-extensions-semantickernel"]
    microsoft_agents_a365_tooling_extensions_agentframework["microsoft-agents-a365-tooling-extensions-agentframework"]

    %% Dependencies
    microsoft_agents_a365_observability_core --> microsoft_agents_a365_runtime
    microsoft_agents_a365_observability_extensions_langchain --> microsoft_agents_a365_observability_core
    microsoft_agents_a365_observability_extensions_openai --> microsoft_agents_a365_observability_core
    microsoft_agents_a365_observability_extensions_semantic_kernel --> microsoft_agents_a365_observability_core
    microsoft_agents_a365_observability_extensions_agent_framework --> microsoft_agents_a365_observability_core
    microsoft_agents_a365_tooling_extensions_azureaifoundry --> microsoft_agents_a365_tooling
    microsoft_agents_a365_tooling_extensions_openai --> microsoft_agents_a365_tooling
    microsoft_agents_a365_tooling_extensions_semantickernel --> microsoft_agents_a365_tooling
    microsoft_agents_a365_tooling_extensions_agentframework --> microsoft_agents_a365_tooling

    %% Styling
    classDef notifications fill:#ffcdd2,stroke:#c62828,color:#280505,stroke-width:2px
    class microsoft_agents_a365_notifications notifications
    classDef runtime fill:#bbdefb,stroke:#1565c0,color:#0d1a26,stroke-width:2px
    class microsoft_agents_a365_runtime runtime
    classDef observability fill:#c8e6c9,stroke:#2e7d32,color:#142a14,stroke-width:2px
    class microsoft_agents_a365_observability_core observability
    classDef observability_extensions fill:#e8f5e9,stroke:#66bb6a,color:#1f3d1f,stroke-width:2px
    class microsoft_agents_a365_observability_extensions_langchain,microsoft_agents_a365_observability_extensions_openai,microsoft_agents_a365_observability_extensions_semantic_kernel,microsoft_agents_a365_observability_extensions_agent_framework observability_extensions
    classDef tooling fill:#ffe0b2,stroke:#e65100,color:#331a00,stroke-width:2px
    class microsoft_agents_a365_tooling tooling
    classDef tooling_extensions fill:#fff3e0,stroke:#fb8c00,color:#4d2600,stroke-width:2px
    class microsoft_agents_a365_tooling_extensions_azureaifoundry,microsoft_agents_a365_tooling_extensions_openai,microsoft_agents_a365_tooling_extensions_semantickernel,microsoft_agents_a365_tooling_extensions_agentframework tooling_extensions
```

## Package Types

- **Notifications** (Red): Notification and messaging extensions
- **Runtime** (Blue): Core runtime components
- **Observability** (Green): Telemetry and monitoring core
- **Observability Extensions** (Light Green): Framework-specific observability integrations
- **Tooling** (Orange): Agent tooling SDK core
- **Tooling Extensions** (Light Orange): Framework-specific tooling integrations
