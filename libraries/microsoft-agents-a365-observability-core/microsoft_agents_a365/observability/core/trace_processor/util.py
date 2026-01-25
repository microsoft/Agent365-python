# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from .. import constants as consts

# Generic / common tracing attributes
COMMON_ATTRIBUTES = [
    consts.TENANT_ID_KEY,  # tenant.id
    consts.CUSTOM_PARENT_SPAN_ID_KEY,  # custom.parent.span.id
    consts.CUSTOM_SPAN_NAME_KEY,  # custom.span.name
    consts.CORRELATION_ID_KEY,  # correlation.id
    consts.GEN_AI_CONVERSATION_ID_KEY,  # conversation.id
    consts.GEN_AI_CONVERSATION_ITEM_LINK_KEY,  # conversation.itemLink
    consts.GEN_AI_OPERATION_NAME_KEY,  # gen_ai.operation.name
    consts.GEN_AI_AGENT_ID_KEY,  # gen_ai.agent.id
    consts.GEN_AI_AGENT_NAME_KEY,  # gen_ai.agent.name
    consts.GEN_AI_AGENT_DESCRIPTION_KEY,  # gen_ai.agent.description
    consts.GEN_AI_AGENT_USER_ID_KEY,  # gen_ai.agent.userid
    consts.GEN_AI_AGENT_UPN_KEY,  # gen_ai.agent.upn
    consts.GEN_AI_AGENT_BLUEPRINT_ID_KEY,  # gen_ai.agent.applicationid
    consts.GEN_AI_AGENT_AUID_KEY,
    consts.GEN_AI_AGENT_TYPE_KEY,
    consts.OPERATION_SOURCE_KEY,  # operation.source
    consts.SESSION_ID_KEY,
    consts.SESSION_DESCRIPTION_KEY,
    consts.HIRING_MANAGER_ID_KEY,
    consts.GEN_AI_CALLER_CLIENT_IP_KEY,  # gen_ai.caller.client.ip
    # Execution context
    consts.GEN_AI_EXECUTION_SOURCE_NAME_KEY,  # gen_ai.channel.name
    consts.GEN_AI_EXECUTION_SOURCE_DESCRIPTION_KEY,  # gen_ai.channel.link
]

# Invoke Agent–specific attributes
INVOKE_AGENT_ATTRIBUTES = [
    # Caller / Invoker attributes
    consts.GEN_AI_CALLER_ID_KEY,  # gen_ai.caller.id
    consts.GEN_AI_CALLER_NAME_KEY,  # gen_ai.caller.name
    consts.GEN_AI_CALLER_UPN_KEY,  # gen_ai.caller.upn
    consts.GEN_AI_CALLER_USER_ID_KEY,  # gen_ai.caller.userid
    consts.GEN_AI_CALLER_TENANT_ID_KEY,  # gen_ai.caller.tenantid
    # Caller Agent (A2A) attributes
    consts.GEN_AI_CALLER_AGENT_ID_KEY,  # gen_ai.caller.agent.id
    consts.GEN_AI_CALLER_AGENT_NAME_KEY,  # gen_ai.caller.agent.name
    consts.GEN_AI_CALLER_AGENT_USER_ID_KEY,  # gen_ai.caller.agent.userid
    consts.GEN_AI_CALLER_AGENT_UPN_KEY,  # gen_ai.caller.agent.upn
    consts.GEN_AI_CALLER_AGENT_TENANT_ID_KEY,  # gen_ai.caller.agent.tenantid
    consts.GEN_AI_CALLER_AGENT_APPLICATION_ID_KEY,  # gen_ai.caller.agent.applicationid
    consts.GEN_AI_EXECUTION_TYPE_KEY,  # gen_ai.execution.type
]
