# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

# Constants for SDK OpenTelemetry implementation.

# Span operation names
INVOKE_AGENT_OPERATION_NAME = "invoke_agent"
EXECUTE_TOOL_OPERATION_NAME = "execute_tool"

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
GEN_AI_RESPONSE_ID_KEY = "gen_ai.response.id"
GEN_AI_RESPONSE_FINISH_REASONS_KEY = "gen_ai.response.finish_reasons"
GEN_AI_RESPONSE_MODEL_KEY = "gen_ai.response.model"
GEN_AI_SYSTEM_KEY = "gen_ai.system"
GEN_AI_SYSTEM_VALUE = "az.ai.agent365"
GEN_AI_THOUGHT_PROCESS_KEY = "gen_ai.agent.thought.process"

GEN_AI_AGENT_ID_KEY = "gen_ai.agent.id"
GEN_AI_AGENT_NAME_KEY = "gen_ai.agent.name"
GEN_AI_AGENT_DESCRIPTION_KEY = "gen_ai.agent.description"
GEN_AI_CONVERSATION_ID_KEY = "gen_ai.conversation.id"
GEN_AI_CONVERSATION_ITEM_LINK_KEY = "gen_ai.conversation.item.link"
GEN_AI_TOKEN_TYPE_KEY = "gen_ai.token.type"
GEN_AI_USAGE_INPUT_TOKENS_KEY = "gen_ai.usage.input_tokens"
GEN_AI_USAGE_OUTPUT_TOKENS_KEY = "gen_ai.usage.output_tokens"
GEN_AI_CHOICE = "gen_ai.choice"
GEN_AI_PROVIDER_NAME_KEY = "gen_ai.provider.name"
GEN_AI_AGENT_TYPE_KEY = "gen_ai.agent.type"

GEN_AI_SYSTEM_INSTRUCTIONS_KEY = "gen_ai.system_instructions"
GEN_AI_INPUT_MESSAGES_KEY = "gen_ai.input.messages"
GEN_AI_OUTPUT_MESSAGES_KEY = "gen_ai.output.messages"
GEN_AI_EVENT_CONTENT = "gen_ai.event.content"

# Tool execution constants
GEN_AI_TOOL_CALL_ID_KEY = "gen_ai.tool.call.id"
GEN_AI_TOOL_NAME_KEY = "gen_ai.tool.name"
GEN_AI_TOOL_DESCRIPTION_KEY = "gen_ai.tool.description"
GEN_AI_TOOL_ARGS_KEY = "gen_ai.tool.arguments"
GEN_AI_TOOL_CALL_RESULT_KEY = GEN_AI_EVENT_CONTENT  # GEN_AI_EVENT_CONTENT
GEN_AI_TOOL_TYPE_KEY = "gen_ai.tool.type"

# Agent user(user tied to agent instance during creation) or caller dimensions
GEN_AI_AGENT_USER_ID_KEY = "gen_ai.agent.userid"
GEN_AI_CALLER_USER_ID_KEY = "gen_ai.caller.userid"
GEN_AI_CALLER_TENANT_ID_KEY = "gen_ai.caller.tenantid"
GEN_AI_CALLER_ID_KEY = "gen_ai.caller.id"
GEN_AI_CALLER_NAME_KEY = "gen_ai.caller.name"
GEN_AI_CALLER_UPN_KEY = "gen_ai.caller.upn"
GEN_AI_CALLER_CLIENT_IP_KEY = "gen_ai.caller.client.ip"

# Agent to Agent caller agent dimensions
GEN_AI_CALLER_AGENT_USER_ID_KEY = "gen_ai.caller.agent.userid"
GEN_AI_CALLER_AGENT_UPN_KEY = "gen_ai.caller.agent.upn"
GEN_AI_CALLER_AGENT_TENANT_ID_KEY = "gen_ai.caller.agent.tenantid"
GEN_AI_CALLER_AGENT_NAME_KEY = "gen_ai.caller.agent.name"
GEN_AI_CALLER_AGENT_ID_KEY = "gen_ai.caller.agent.id"
GEN_AI_CALLER_AGENT_APPLICATION_ID_KEY = "gen_ai.caller.agent.applicationid"
GEN_AI_CALLER_AGENT_TYPE_KEY = "gen_ai.caller.agent.type"
GEN_AI_CALLER_AGENT_USER_CLIENT_IP = "gen_ai.caller.agent.user.client.ip"

# Agent-specific dimensions
AGENT_ID_KEY = "gen_ai.agent.id"
GEN_AI_TASK_ID_KEY = "gen_ai.task.id"
SESSION_ID_KEY = "session.id"
GEN_AI_ICON_URI_KEY = "gen_ai.agent365.icon_uri"
TENANT_ID_KEY = "tenant.id"

# Baggage keys
OPERATION_SOURCE_KEY = "operation.source"
GEN_AI_AGENT_AUID_KEY = "gen_ai.agent.user.id"
GEN_AI_AGENT_UPN_KEY = "gen_ai.agent.upn"
GEN_AI_AGENT_BLUEPRINT_ID_KEY = "gen_ai.agent.applicationid"
CORRELATION_ID_KEY = "correlation.id"
HIRING_MANAGER_ID_KEY = "hiring.manager.id"
SESSION_DESCRIPTION_KEY = "session.description"

# Execution context dimensions
GEN_AI_EXECUTION_TYPE_KEY = "gen_ai.execution.type"
GEN_AI_EXECUTION_PAYLOAD_KEY = "gen_ai.execution.payload"

# Source metadata dimensions
GEN_AI_EXECUTION_SOURCE_NAME_KEY = "gen_ai.channel.name"
GEN_AI_EXECUTION_SOURCE_DESCRIPTION_KEY = "gen_ai.channel.link"

# custom parent id and parent name key
CUSTOM_PARENT_SPAN_ID_KEY = "custom.parent.span.id"
CUSTOM_SPAN_NAME_KEY = "custom.span.name"
