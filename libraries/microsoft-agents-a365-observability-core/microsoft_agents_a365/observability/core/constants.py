# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

# Constants for SDK OpenTelemetry implementation.

# Span operation names
INVOKE_AGENT_OPERATION_NAME = "invoke_agent"
EXECUTE_TOOL_OPERATION_NAME = "execute_tool"
OUTPUT_MESSAGES_OPERATION_NAME = "output_messages"
CHAT_OPERATION_NAME = "chat"

# OpenTelemetry semantic conventions
ERROR_TYPE_KEY = "error.type"
ERROR_MESSAGE_KEY = "error.message"
AZ_NAMESPACE_KEY = "az.namespace"
SERVER_ADDRESS_KEY = "server.address"
SERVER_PORT_KEY = "server.port"
AZURE_RP_NAMESPACE_VALUE = "Microsoft.CognitiveServices"
SOURCE_NAME = "Agent365Sdk"
ENABLE_OPENTELEMETRY_SWITCH = "Azure.Experimental.EnableActivitySource"
TRACE_CONTENTS_SWITCH = "Azure.Experimental.TraceGenAIMessageContent"
TRACE_CONTENTS_ENVIRONMENT_VARIABLE = "AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED"
ENABLE_OBSERVABILITY = "ENABLE_OBSERVABILITY"
ENABLE_A365_OBSERVABILITY_EXPORTER = "ENABLE_A365_OBSERVABILITY_EXPORTER"
ENABLE_A365_OBSERVABILITY = "ENABLE_A365_OBSERVABILITY"

# GenAI semantic conventions
GEN_AI_CLIENT_OPERATION_DURATION_METRIC_NAME = "gen_ai.client.operation.duration"
GEN_AI_CLIENT_TOKEN_USAGE_METRIC_NAME = "gen_ai.client.token.usage"
GEN_AI_OPERATION_NAME_KEY = "gen_ai.operation.name"
GEN_AI_REQUEST_MAX_TOKENS_KEY = "gen_ai.request.max_tokens"
GEN_AI_REQUEST_MODEL_KEY = "gen_ai.request.model"
GEN_AI_REQUEST_TEMPERATURE_KEY = "gen_ai.request.temperature"
GEN_AI_REQUEST_TOP_P_KEY = "gen_ai.request.top_p"
GEN_AI_RESPONSE_FINISH_REASONS_KEY = "gen_ai.response.finish_reasons"
GEN_AI_RESPONSE_MODEL_KEY = "gen_ai.response.model"
GEN_AI_RESPONSE_ID_KEY = "gen_ai.response.id"
GEN_AI_AGENT_ID_KEY = "gen_ai.agent.id"
GEN_AI_AGENT_NAME_KEY = "gen_ai.agent.name"
GEN_AI_AGENT_DESCRIPTION_KEY = "gen_ai.agent.description"
GEN_AI_AGENT_PLATFORM_ID_KEY = "microsoft.a365.agent.platform.id"
GEN_AI_AGENT_THOUGHT_PROCESS_KEY = "microsoft.a365.agent.thought.process"
GEN_AI_CONVERSATION_ID_KEY = "gen_ai.conversation.id"
GEN_AI_CONVERSATION_ITEM_LINK_KEY = "microsoft.conversation.item.link"
GEN_AI_TOKEN_TYPE_KEY = "gen_ai.token.type"
GEN_AI_USAGE_INPUT_TOKENS_KEY = "gen_ai.usage.input_tokens"
GEN_AI_USAGE_OUTPUT_TOKENS_KEY = "gen_ai.usage.output_tokens"
GEN_AI_CHOICE = "gen_ai.choice"
GEN_AI_PROVIDER_NAME_KEY = "gen_ai.provider.name"

GEN_AI_SYSTEM_INSTRUCTIONS_KEY = "gen_ai.system_instructions"
GEN_AI_INPUT_MESSAGES_KEY = "gen_ai.input.messages"
GEN_AI_OUTPUT_MESSAGES_KEY = "gen_ai.output.messages"

# Tool execution constants
GEN_AI_TOOL_CALL_ID_KEY = "gen_ai.tool.call.id"
GEN_AI_TOOL_NAME_KEY = "gen_ai.tool.name"
GEN_AI_TOOL_DESCRIPTION_KEY = "gen_ai.tool.description"
GEN_AI_TOOL_ARGS_KEY = "gen_ai.tool.call.arguments"
GEN_AI_TOOL_CALL_RESULT_KEY = "gen_ai.tool.call.result"
GEN_AI_TOOL_TYPE_KEY = "gen_ai.tool.type"

# Human caller dimensions (OTel user.* namespace)
USER_ID_KEY = "user.id"
USER_NAME_KEY = "user.name"
USER_EMAIL_KEY = "user.email"
GEN_AI_CALLER_CLIENT_IP_KEY = "client.address"

# Agent to Agent caller agent dimensions
GEN_AI_CALLER_AGENT_USER_ID_KEY = "microsoft.a365.caller.agent.user.id"
GEN_AI_CALLER_AGENT_EMAIL_KEY = "microsoft.a365.caller.agent.user.email"
GEN_AI_CALLER_AGENT_NAME_KEY = "microsoft.a365.caller.agent.name"
GEN_AI_CALLER_AGENT_ID_KEY = "microsoft.a365.caller.agent.id"
GEN_AI_CALLER_AGENT_APPLICATION_ID_KEY = "microsoft.a365.caller.agent.blueprint.id"
GEN_AI_CALLER_AGENT_PLATFORM_ID_KEY = "microsoft.a365.caller.agent.platform.id"

# Agent-specific dimensions
AGENT_ID_KEY = "gen_ai.agent.id"
GEN_AI_TASK_ID_KEY = "gen_ai.task.id"
SESSION_ID_KEY = "microsoft.session.id"
SESSION_DESCRIPTION_KEY = "microsoft.session.description"
GEN_AI_ICON_URI_KEY = "gen_ai.agent365.icon_uri"
TENANT_ID_KEY = "microsoft.tenant.id"

# Baggage keys
GEN_AI_AGENT_AUID_KEY = "microsoft.agent.user.id"
GEN_AI_AGENT_EMAIL_KEY = "microsoft.agent.user.email"
GEN_AI_AGENT_BLUEPRINT_ID_KEY = "microsoft.a365.agent.blueprint.id"

# Error type constants
ERROR_TYPE_CANCELLED = "TaskCanceledException"

# Execution context dimensions
GEN_AI_EXECUTION_PAYLOAD_KEY = "gen_ai.execution.payload"

# Channel dimensions
CHANNEL_NAME_KEY = "microsoft.channel.name"
CHANNEL_LINK_KEY = "microsoft.channel.link"

# Custom parent id and parent name key
CUSTOM_PARENT_SPAN_ID_KEY = "custom.parent.span.id"
CUSTOM_SPAN_NAME_KEY = "custom.span.name"

# Service attributes
SERVICE_NAME_KEY = "service.name"

# Telemetry SDK attributes
TELEMETRY_SDK_NAME_KEY = "telemetry.sdk.name"
TELEMETRY_SDK_LANGUAGE_KEY = "telemetry.sdk.language"
TELEMETRY_SDK_VERSION_KEY = "telemetry.sdk.version"
TELEMETRY_SDK_NAME_VALUE = "A365ObservabilitySDK"
TELEMETRY_SDK_LANGUAGE_VALUE = "python"
