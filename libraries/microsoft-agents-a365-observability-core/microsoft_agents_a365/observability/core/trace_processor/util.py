# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from .. import constants as consts

# Generic / common tracing attributes
COMMON_ATTRIBUTES = [
    consts.TENANT_ID_KEY,
    consts.CUSTOM_PARENT_SPAN_ID_KEY,  # custom.parent.span.id
    consts.CUSTOM_SPAN_NAME_KEY,  # custom.span.name
    consts.GEN_AI_CONVERSATION_ID_KEY,  # gen_ai.conversation.id
    consts.GEN_AI_CONVERSATION_ITEM_LINK_KEY,  # microsoft.conversation.item.link
    consts.GEN_AI_OPERATION_NAME_KEY,  # gen_ai.operation.name
    consts.GEN_AI_AGENT_ID_KEY,  # gen_ai.agent.id
    consts.GEN_AI_AGENT_NAME_KEY,  # gen_ai.agent.name
    consts.GEN_AI_AGENT_DESCRIPTION_KEY,  # gen_ai.agent.description
    consts.GEN_AI_AGENT_VERSION_KEY,  # gen_ai.agent.version
    consts.GEN_AI_AGENT_EMAIL_KEY,  # microsoft.agent.user.email
    consts.GEN_AI_AGENT_BLUEPRINT_ID_KEY,  # microsoft.a365.agent.blueprint.id
    consts.GEN_AI_AGENT_AUID_KEY,  # microsoft.agent.user.id
    consts.GEN_AI_AGENT_PLATFORM_ID_KEY,  # microsoft.a365.agent.platform.id
    consts.SESSION_ID_KEY,  # microsoft.session.id
    consts.SESSION_DESCRIPTION_KEY,  # microsoft.session.description
    consts.GEN_AI_CALLER_CLIENT_IP_KEY,  # client.address
    # Channel dimensions
    consts.CHANNEL_NAME_KEY,  # microsoft.channel.name
    consts.CHANNEL_LINK_KEY,  # microsoft.channel.link
    # User / Caller attributes
    consts.USER_ID_KEY,  # user.id
    consts.USER_NAME_KEY,  # user.name
    consts.USER_EMAIL_KEY,  # user.email
    # Service attributes
    consts.SERVICE_NAME_KEY,  # service.name
]

# Invoke Agent–specific attributes
INVOKE_AGENT_ATTRIBUTES = [
    # Caller Agent (A2A) attributes
    consts.GEN_AI_CALLER_AGENT_ID_KEY,  # microsoft.a365.caller.agent.id
    consts.GEN_AI_CALLER_AGENT_NAME_KEY,  # microsoft.a365.caller.agent.name
    consts.GEN_AI_CALLER_AGENT_USER_ID_KEY,  # microsoft.a365.caller.agent.user.id
    consts.GEN_AI_CALLER_AGENT_EMAIL_KEY,  # microsoft.a365.caller.agent.user.email
    consts.GEN_AI_CALLER_AGENT_APPLICATION_ID_KEY,  # microsoft.a365.caller.agent.blueprint.id
    consts.GEN_AI_CALLER_AGENT_PLATFORM_ID_KEY,  # microsoft.a365.caller.agent.platform.id
    consts.GEN_AI_CALLER_AGENT_VERSION_KEY,  # microsoft.a365.caller.agent.version
    # Server address/port for invoke agent target
    consts.SERVER_ADDRESS_KEY,  # server.address
    consts.SERVER_PORT_KEY,  # server.port
]
