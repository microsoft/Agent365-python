# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

# Span Attribute Types
from microsoft_agents_a365.observability.core.constants import (
    EXECUTE_TOOL_OPERATION_NAME,
    INVOKE_AGENT_OPERATION_NAME,
)
from microsoft_agents_a365.observability.core.inference_operation_type import InferenceOperationType

GEN_AI_SPAN_KIND_AGENT_KEY = INVOKE_AGENT_OPERATION_NAME
GEN_AI_SPAN_KIND_TOOL_KEY = EXECUTE_TOOL_OPERATION_NAME
GEN_AI_SPAN_KIND_CHAIN_KEY = "chain"
GEN_AI_SPAN_KIND_LLM_KEY = InferenceOperationType.CHAT.value.lower()
GEN_AI_SPAN_KIND_RETRIEVER_KEY = "retriever"
GEN_AI_SPAN_KIND_EMBEDDING_KEY = "embedding"
GEN_AI_SPAN_KIND_RERANKER_KEY = "reranker"
GEN_AI_SPAN_KIND_GUARDRAIL_KEY = "guardrail"
GEN_AI_SPAN_KIND_EVALUATOR_KEY = "evaluator"
GEN_AI_SPAN_KIND_UNKNOWN_KEY = "unknown"

# PREFIXES
GEN_AI_MESSAGE_ROLE = "message_role"
GEN_AI_MESSAGE_CONTENT = "message_content"
GEN_AI_MESSAGE_CONTENTS = "message_contents"
GEN_AI_MESSAGE_CONTENT_TYPE = "content_type"
GEN_AI_MESSAGE_TOOL_CALLS = "message_tool_calls"
GEN_AI_MESSAGE_TOOL_CALL_ID = "message_tool_id"
GEN_AI_MESSAGE_TOOL_CALL_NAME = "message_tool_name"
GEN_AI_TOOL_JSON_SCHEMA = "tool_json_schema"
GEN_AI_LLM_TOKEN_COUNT_TOTAL = "llm_token_count_total"
GEN_AI_LLM_TOKEN_COUNT_PROMPT_DETAILS_CACHED_READ = "llm_token_count_prompt_details_cached_read"
GEN_AI_LLM_TOKEN_COUNT_COMPLETION_DETAILS_REASONING = "llm_token_count_completion_details_reasoning"
GEN_AI_GRAPH_NODE_ID = "graph_node_id"
GEN_AI_GRAPH_NODE_PARENT_ID = "graph_node_parent_id"
