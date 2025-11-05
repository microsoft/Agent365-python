import unittest

from microsoft_agents_a365.observability.core.constants import (
    GEN_AI_AGENT_AUID_KEY,
    GEN_AI_AGENT_DESCRIPTION_KEY,
    GEN_AI_AGENT_ID_KEY,
    GEN_AI_AGENT_NAME_KEY,
    GEN_AI_AGENT_UPN_KEY,
    GEN_AI_CALLER_ID_KEY,
    GEN_AI_CALLER_NAME_KEY,
    GEN_AI_CALLER_TENANT_ID_KEY,
    GEN_AI_CALLER_UPN_KEY,
    GEN_AI_CONVERSATION_ID_KEY,
    GEN_AI_CONVERSATION_ITEM_LINK_KEY,
    GEN_AI_EXECUTION_SOURCE_DESCRIPTION_KEY,
    GEN_AI_EXECUTION_SOURCE_ID_KEY,
    GEN_AI_EXECUTION_SOURCE_NAME_KEY,
    GEN_AI_EXECUTION_TYPE_KEY,
    TENANT_ID_KEY,
)
from microsoft_agents_a365.observability.core.execution_type import ExecutionType
from microsoft_agents_a365.observability.core.middleware import turn_context_baggage as tcb


class FakeEntity:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class FakeActivity:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class FakeTurnContext:
    def __init__(self, activity):
        self.activity = activity


class TestTurnContextBaggage(unittest.TestCase):
    def test_iter_caller_pairs_basic_and_upn_fallback(self):
        activity = FakeActivity(**{
            "from": FakeEntity(id="caller-123", name="Alice", tenant_id="tenant-xyz"),
        })
        pairs = dict(tcb._iter_caller_pairs(activity))
        self.assertEqual(pairs[GEN_AI_CALLER_ID_KEY], "caller-123")
        self.assertEqual(pairs[GEN_AI_CALLER_NAME_KEY], "Alice")
        # upn missing, should fallback to name
        self.assertEqual(pairs[GEN_AI_CALLER_UPN_KEY], "Alice")
        # user id may be absent -> None (not included if None)
        self.assertIn(GEN_AI_CALLER_TENANT_ID_KEY, pairs)
        self.assertEqual(pairs[GEN_AI_CALLER_TENANT_ID_KEY], "tenant-xyz")

    def test_iter_execution_type_agent_to_agent(self):
        activity = FakeActivity(**{
            "from": FakeEntity(role="agenticUser", agentic_user_id="u1"),
            "recipient": FakeEntity(role="agenticUser", agentic_user_id="u2"),
        })
        pairs = dict(tcb._iter_execution_type_pair(activity))
        self.assertEqual(pairs[GEN_AI_EXECUTION_TYPE_KEY], ExecutionType.AGENT_TO_AGENT.value)

    def test_iter_execution_type_human_to_agent(self):
        activity = FakeActivity(**{
            "from": FakeEntity(role="user"),
            "recipient": FakeEntity(role="agenticUser", agentic_user_id="u2"),
        })
        pairs = dict(tcb._iter_execution_type_pair(activity))
        self.assertEqual(pairs[GEN_AI_EXECUTION_TYPE_KEY], ExecutionType.HUMAN_TO_AGENT.value)

    def test_iter_target_agent_pairs_with_fallbacks(self):
        activity = FakeActivity(**{
            "recipient": FakeEntity(
                agentic_app_id="app-456",
                name="MyAgent",
                agentic_user_id="auid-789",
                role="agenticUser",
            )
        })
        pairs = dict(tcb._iter_target_agent_pairs(activity))
        self.assertEqual(pairs[GEN_AI_AGENT_ID_KEY], "app-456")
        self.assertEqual(pairs[GEN_AI_AGENT_NAME_KEY], "MyAgent")
        self.assertEqual(pairs[GEN_AI_AGENT_AUID_KEY], "auid-789")
        # upn missing -> fallback to name
        self.assertEqual(pairs[GEN_AI_AGENT_UPN_KEY], "MyAgent")
        self.assertEqual(pairs[GEN_AI_AGENT_DESCRIPTION_KEY], "agenticUser")

    def test_iter_tenant_id_pair_primary_and_channel_data_fallback(self):
        # Case 1: tenant_id present directly
        activity_direct = FakeActivity(**{
            "recipient": FakeEntity(tenant_id="t-direct"),
        })
        direct = dict(tcb._iter_tenant_id_pair(activity_direct))
        self.assertEqual(direct[TENANT_ID_KEY], "t-direct")

        # Case 2: missing recipient tenant_id but present in channel_data
        activity_fallback = FakeActivity(**{
            "recipient": FakeEntity(),  # no tenant_id
            "channel_data": {
                "tenant": {"id": "t-channel"},
            },
        })
        fallback = dict(tcb._iter_tenant_id_pair(activity_fallback))
        self.assertEqual(fallback[TENANT_ID_KEY], "t-channel")

        # Case 3: no tenant anywhere
        activity_none = FakeActivity(**{
            "recipient": FakeEntity(),
        })
        none_val = dict(tcb._iter_tenant_id_pair(activity_none))
        self.assertIsNone(none_val[TENANT_ID_KEY])

    def test_iter_source_metadata_pairs(self):
        activity = FakeActivity(**{
            "channel_id": "msteams",
            "type": "message",
        })
        pairs = dict(tcb._iter_source_metadata_pairs(activity))
        self.assertEqual(pairs[GEN_AI_EXECUTION_SOURCE_ID_KEY], "msteams")
        self.assertEqual(pairs[GEN_AI_EXECUTION_SOURCE_NAME_KEY], "msteams")
        self.assertEqual(pairs[GEN_AI_EXECUTION_SOURCE_DESCRIPTION_KEY], "message")

    def test_iter_conversation_pairs_wpxcomment(self):
        activity = FakeActivity(**{
            "channel_id": "agents",
            "entities": [
                FakeEntity(
                    type="wpxcomment",
                    documentId="doc-100",
                    parentCommentId="parent-200",
                )
            ],
            "service_url": "https://service/link",
        })
        pairs = dict(tcb._iter_conversation_pairs(activity))
        # Expect composed id doc-100_parent-200
        self.assertEqual(pairs[GEN_AI_CONVERSATION_ID_KEY], "doc-100_parent-200")
        self.assertEqual(pairs[GEN_AI_CONVERSATION_ITEM_LINK_KEY], "https://service/link")

    def test_iter_conversation_pairs_email_notification(self):
        activity = FakeActivity(**{
            "channel_id": "agents",
            "entities": [
                FakeEntity(
                    type="emailNotification",
                    conversationId="email-conv-123",
                )
            ],
            "service_url": "http://service/url",
        })
        pairs = dict(tcb._iter_conversation_pairs(activity))
        self.assertEqual(pairs[GEN_AI_CONVERSATION_ID_KEY], "email-conv-123")
        self.assertEqual(pairs[GEN_AI_CONVERSATION_ITEM_LINK_KEY], "http://service/url")

    def test_iter_conversation_pairs_fallback_conversation(self):
        activity = FakeActivity(**{
            "channel_id": "msteams",
            "conversation": FakeEntity(id="conv-777"),
            "service_url": "svc",
        })
        pairs = dict(tcb._iter_conversation_pairs(activity))
        self.assertEqual(pairs[GEN_AI_CONVERSATION_ID_KEY], "conv-777")
        self.assertEqual(pairs[GEN_AI_CONVERSATION_ITEM_LINK_KEY], "svc")

    def test_from_turn_context_aggregates_all(self):
        activity = FakeActivity(**{
            "from": FakeEntity(id="caller", name="CallerName"),
            "recipient": FakeEntity(
                agentic_app_id="app-id",
                name="AgentName",
                agentic_user_id="auid-1",
                tenant_id="t-1",
                role="agenticUser",
            ),
            "channel_id": "agents",
            "type": "message",
            "entities": [
                FakeEntity(
                    type="emailNotification",
                    conversationId="email-conv-123",
                )
            ],
            "service_url": "svc-url",
        })
        ctx = FakeTurnContext(activity)
        result = tcb.from_turn_context(ctx)

        # Caller fields
        self.assertEqual(result[GEN_AI_CALLER_ID_KEY], "caller")
        self.assertEqual(result[GEN_AI_CALLER_NAME_KEY], "CallerName")
        # Agent fields
        self.assertEqual(result[GEN_AI_AGENT_ID_KEY], "app-id")
        self.assertEqual(result[GEN_AI_AGENT_NAME_KEY], "AgentName")
        self.assertEqual(result[GEN_AI_AGENT_AUID_KEY], "auid-1")
        # Tenant
        self.assertEqual(result[TENANT_ID_KEY], "t-1")
        # Execution type (agent-to-agent)
        self.assertEqual(result[GEN_AI_EXECUTION_TYPE_KEY], ExecutionType.HUMAN_TO_AGENT.value)
        # Conversation
        self.assertEqual(result[GEN_AI_CONVERSATION_ID_KEY], "email-conv-123")
        self.assertEqual(result[GEN_AI_CONVERSATION_ITEM_LINK_KEY], "svc-url")
        # Source metadata
        self.assertEqual(result[GEN_AI_EXECUTION_SOURCE_ID_KEY], "agents")
        self.assertEqual(result[GEN_AI_EXECUTION_SOURCE_NAME_KEY], "agents")
        self.assertEqual(result[GEN_AI_EXECUTION_SOURCE_DESCRIPTION_KEY], "message")

    def test_from_turn_context_missing_activity(self):
        ctx = FakeTurnContext(activity=None)
        result = tcb.from_turn_context(ctx)
        self.assertEqual(result, {}, "Expected empty dict when activity missing")


if __name__ == "__main__":
    unittest.main()
