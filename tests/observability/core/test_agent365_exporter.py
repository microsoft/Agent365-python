# Copyright (c) Microsoft. All rights reserved.

import json
import os
import unittest
from unittest.mock import Mock, patch

from microsoft_agents_a365.observability.core.constants import GEN_AI_AGENT_ID_KEY, TENANT_ID_KEY
from microsoft_agents_a365.observability.core.exporters.agent365_exporter import (
    _Agent365Exporter,
)
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExportResult
from opentelemetry.trace import StatusCode
from opentelemetry.util.types import Attributes


class TestAgent365Exporter(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures."""
        self.mock_token_resolver = Mock()
        self.mock_token_resolver.return_value = "test_token_123"

        # Store original environment variable values for cleanup
        self._original_domain_override = os.environ.get("A365_OBSERVABILITY_DOMAIN_OVERRIDE")

        # Ensure no override is set by default for most tests
        os.environ.pop("A365_OBSERVABILITY_DOMAIN_OVERRIDE", None)

        # Create default exporter for tests that don't need special setup
        self.exporter = _Agent365Exporter(
            token_resolver=self.mock_token_resolver, cluster_category="test"
        )

    def tearDown(self):
        """Clean up test environment."""
        # Restore original environment variable value
        if self._original_domain_override is None:
            os.environ.pop("A365_OBSERVABILITY_DOMAIN_OVERRIDE", None)
        else:
            os.environ["A365_OBSERVABILITY_DOMAIN_OVERRIDE"] = self._original_domain_override

    def _create_mock_span(
        self,
        name: str = "test_span",
        trace_id: int = 12345,
        span_id: int = 67890,
        parent_id: int | None = None,
        status_code: StatusCode = StatusCode.OK,
        attributes: Attributes | None = None,
        scope_name: str = "test.scope",
        scope_version: str = "1.0.0",
        tenant_id: str = "test-tenant-123",
        agent_id: str = "test-agent-456",
    ) -> ReadableSpan:
        """Create a mock ReadableSpan for testing."""
        mock_span = Mock(spec=ReadableSpan)
        mock_span.name = name

        # Mock the context properly
        mock_context = Mock()
        mock_context.trace_id = trace_id
        mock_context.span_id = span_id
        mock_span.context = mock_context

        mock_span.parent = Mock() if parent_id else None
        if parent_id:
            mock_span.parent.span_id = parent_id
        mock_span.start_time = 1640995200000000000  # 2022-01-01 00:00:00 UTC in nanoseconds
        mock_span.end_time = 1640995260000000000  # 2022-01-01 00:01:00 UTC in nanoseconds
        mock_span.status = Mock()
        mock_span.status.status_code = status_code
        mock_span.status.description = ""

        # Add kind attribute that kind_name() can process
        mock_span.kind = Mock()
        mock_span.kind.name = "INTERNAL"

        # Add identity attributes for partition_by_identity to work
        span_attributes = attributes or {}
        if tenant_id and agent_id:
            span_attributes.update({
                TENANT_ID_KEY: tenant_id,
                GEN_AI_AGENT_ID_KEY: agent_id,
            })

        mock_span.attributes = span_attributes
        mock_span.events = []
        mock_span.links = []

        # Mock instrumentation scope
        mock_span.instrumentation_scope = Mock()
        mock_span.instrumentation_scope.name = scope_name
        mock_span.instrumentation_scope.version = scope_version

        # Mock resource for _build_export_request
        mock_span.resource = Mock()
        mock_span.resource.attributes = {"service.name": "test-service"}

        return mock_span

    def test_export_success(self):
        """Test 1: Test successful export of spans."""
        # Arrange
        spans = [
            self._create_mock_span("span1", trace_id=111, span_id=222),
            self._create_mock_span("span2", trace_id=111, span_id=333, parent_id=222),
        ]

        # Mock the PowerPlatformApiDiscovery class that gets created inside export()
        with patch(
            "microsoft_agents_a365.observability.core.exporters.agent365_exporter.PowerPlatformApiDiscovery"
        ) as mock_discovery_class:
            mock_discovery = Mock()
            mock_discovery.get_tenant_island_cluster_endpoint.return_value = "test-endpoint.com"
            mock_discovery_class.return_value = mock_discovery

            # Mock the _post_with_retries method
            with patch.object(self.exporter, "_post_with_retries", return_value=True) as mock_post:
                # Act
                result = self.exporter.export(spans)

                # Assert
                self.assertEqual(result, SpanExportResult.SUCCESS)
                mock_post.assert_called_once()

                # Verify the call arguments
                args, kwargs = mock_post.call_args
                url, body, headers = args

                self.assertIn("test-endpoint.com", url)
                self.assertIn("/maven/agent365/agents/test-agent-456/traces", url)
                self.assertEqual(headers["authorization"], "Bearer test_token_123")
                self.assertEqual(headers["content-type"], "application/json")

            # Verify JSON structure
            request_data = json.loads(body)
            self.assertIn("resourceSpans", request_data)
            self.assertEqual(len(request_data["resourceSpans"]), 1)  # One resource group
            self.assertEqual(len(request_data["resourceSpans"][0]["scopeSpans"]), 1)  # One scope
            self.assertEqual(
                len(request_data["resourceSpans"][0]["scopeSpans"][0]["spans"]), 2
            )  # Two spans

    def test_export_failure_with_retries(self):
        """Test 2: Test export failure and retry mechanism."""
        # Arrange
        spans = [self._create_mock_span("failed_span")]

        # Mock the PowerPlatformApiDiscovery class
        with patch(
            "microsoft_agents_a365.observability.core.exporters.agent365_exporter.PowerPlatformApiDiscovery"
        ) as mock_discovery_class:
            mock_discovery = Mock()
            mock_discovery.get_tenant_island_cluster_endpoint.return_value = "test-endpoint.com"
            mock_discovery_class.return_value = mock_discovery

            # Mock the _post_with_retries method to return False (failure)
            with patch.object(self.exporter, "_post_with_retries", return_value=False) as mock_post:
                # Act
                result = self.exporter.export(spans)

                # Assert
                self.assertEqual(result, SpanExportResult.FAILURE)
                mock_post.assert_called_once()

    def test_partitioning_by_scope(self):
        """Test 3: Test that spans are properly partitioned by instrumentation scope."""
        # Arrange - Create spans with different scopes but same tenant/agent
        spans = [
            self._create_mock_span(
                "span1", trace_id=111, span_id=222, scope_name="scope.a", scope_version="1.0"
            ),
            self._create_mock_span(
                "span2", trace_id=111, span_id=333, scope_name="scope.a", scope_version="1.0"
            ),
            self._create_mock_span(
                "span3", trace_id=222, span_id=444, scope_name="scope.b", scope_version="2.0"
            ),
            self._create_mock_span(
                "span4", trace_id=222, span_id=555, scope_name="scope.c", scope_version="1.5"
            ),
        ]

        # Mock the PowerPlatformApiDiscovery class
        with patch(
            "microsoft_agents_a365.observability.core.exporters.agent365_exporter.PowerPlatformApiDiscovery"
        ) as mock_discovery_class:
            mock_discovery = Mock()
            mock_discovery.get_tenant_island_cluster_endpoint.return_value = "test-endpoint.com"
            mock_discovery_class.return_value = mock_discovery

            # Mock the _post_with_retries method
            with patch.object(self.exporter, "_post_with_retries", return_value=True) as mock_post:
                # Act
                result = self.exporter.export(spans)

                # Assert
                self.assertEqual(result, SpanExportResult.SUCCESS)
                mock_post.assert_called_once()

                # Get the request body and parse it
                args, kwargs = mock_post.call_args
                url, body, headers = args
                request_data = json.loads(body)

            # Should have 1 resource span (all spans share same resource and identity)
            self.assertEqual(len(request_data["resourceSpans"]), 1)

            # Should have 3 scope spans (3 different scopes)
            scope_spans = request_data["resourceSpans"][0]["scopeSpans"]
            self.assertEqual(len(scope_spans), 3)

            # Verify each scope has correct spans
            scope_names = []
            span_counts = []

            for scope_span in scope_spans:
                scope_info = scope_span["scope"]
                scope_names.append(scope_info["name"])
                span_counts.append(len(scope_span["spans"]))

            # Sort for consistent testing
            scope_data = list(zip(scope_names, span_counts, strict=False))
            scope_data.sort()

            # scope.a should have 2 spans, scope.b and scope.c should have 1 each
            expected_scopes = [("scope.a", 2), ("scope.b", 1), ("scope.c", 1)]
            self.assertEqual(scope_data, expected_scopes)

    def test_s2s_endpoint_path_when_enabled(self):
        """Test 4: Test that S2S endpoint path is used when use_s2s_endpoint is True."""
        # Arrange - Create exporter with S2S endpoint enabled
        s2s_exporter = _Agent365Exporter(
            token_resolver=self.mock_token_resolver, cluster_category="test", use_s2s_endpoint=True
        )

        spans = [self._create_mock_span("s2s_span")]

        # Mock the PowerPlatformApiDiscovery class
        with patch(
            "microsoft_agents_a365.observability.core.exporters.agent365_exporter.PowerPlatformApiDiscovery"
        ) as mock_discovery_class:
            mock_discovery = Mock()
            mock_discovery.get_tenant_island_cluster_endpoint.return_value = "test-endpoint.com"
            mock_discovery_class.return_value = mock_discovery

            # Mock the _post_with_retries method
            with patch.object(s2s_exporter, "_post_with_retries", return_value=True) as mock_post:
                # Act
                result = s2s_exporter.export(spans)

                # Assert
                self.assertEqual(result, SpanExportResult.SUCCESS)
                mock_post.assert_called_once()

                # Verify the call arguments - should use S2S path
                args, kwargs = mock_post.call_args
                url, body, headers = args

                self.assertIn("test-endpoint.com", url)
                self.assertIn("/maven/agent365/service/agents/test-agent-456/traces", url)
                self.assertNotIn("/maven/agent365/agents/test-agent-456/traces", url)
                self.assertEqual(headers["authorization"], "Bearer test_token_123")
                self.assertEqual(headers["content-type"], "application/json")

    def test_default_endpoint_path_when_s2s_disabled(self):
        """Test 5: Test that default endpoint path is used when use_s2s_endpoint is False."""
        # Arrange - Create exporter with S2S endpoint disabled (default behavior)
        default_exporter = _Agent365Exporter(
            token_resolver=self.mock_token_resolver, cluster_category="test", use_s2s_endpoint=False
        )

        spans = [self._create_mock_span("default_span")]

        # Mock the PowerPlatformApiDiscovery class
        with patch(
            "microsoft_agents_a365.observability.core.exporters.agent365_exporter.PowerPlatformApiDiscovery"
        ) as mock_discovery_class:
            mock_discovery = Mock()
            mock_discovery.get_tenant_island_cluster_endpoint.return_value = "test-endpoint.com"
            mock_discovery_class.return_value = mock_discovery

            # Mock the _post_with_retries method
            with patch.object(
                default_exporter, "_post_with_retries", return_value=True
            ) as mock_post:
                # Act
                result = default_exporter.export(spans)

                # Assert
                self.assertEqual(result, SpanExportResult.SUCCESS)
                mock_post.assert_called_once()

                # Verify the call arguments - should use default path
                args, kwargs = mock_post.call_args
                url, body, headers = args

                self.assertIn("test-endpoint.com", url)
                self.assertIn("/maven/agent365/agents/test-agent-456/traces", url)
                self.assertNotIn("/maven/agent365/service/agents/test-agent-456/traces", url)
                self.assertEqual(headers["authorization"], "Bearer test_token_123")
                self.assertEqual(headers["content-type"], "application/json")

    @patch("microsoft_agents_a365.observability.core.exporters.agent365_exporter.logger")
    @patch(
        "microsoft_agents_a365.observability.core.exporters.agent365_exporter.PowerPlatformApiDiscovery"
    )
    def test_export_logging(self, mock_discovery, mock_logger):
        """Test that the exporter logs appropriate messages during export."""
        # Mock the discovery service
        mock_discovery_instance = Mock()
        mock_discovery_instance.get_tenant_island_cluster_endpoint.return_value = (
            "test-endpoint.com"
        )
        mock_discovery.return_value = mock_discovery_instance

        # Mock successful HTTP response
        with patch("requests.Session.post") as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = "success"
            mock_response.headers = {"x-ms-correlation-id": "test-correlation-123"}
            mock_post.return_value = mock_response

            # Create test spans
            spans = [
                self._create_mock_span(
                    name="test_span_1",
                    attributes={
                        TENANT_ID_KEY: "test-tenant-123",
                        GEN_AI_AGENT_ID_KEY: "test-agent-456",
                    },
                ),
                self._create_mock_span(
                    name="test_span_2",
                    attributes={
                        TENANT_ID_KEY: "test-tenant-123",
                        GEN_AI_AGENT_ID_KEY: "test-agent-456",
                    },
                ),
            ]

            # Export spans
            result = self.exporter.export(spans)

            # Verify export succeeded
            self.assertEqual(result, SpanExportResult.SUCCESS)

            # Verify logging calls
            expected_log_calls = [
                # Should log groups found
                unittest.mock.call.info("Found 1 identity groups with 2 total spans to export"),
                # Should log endpoint being used
                unittest.mock.call.info(
                    "Exporting 2 spans to endpoint: https://test-endpoint.com/maven/agent365/agents/test-agent-456/traces?api-version=1 "
                    "(tenant: test-tenant-123, agent: test-agent-456)"
                ),
                # Should log token resolution success
                unittest.mock.call.info("Token resolved successfully for agent test-agent-456"),
                # Should log HTTP success
                unittest.mock.call.info(
                    "HTTP 200 success on attempt 1. Correlation ID: test-correlation-123. Response: success"
                ),
            ]

            # Check that all expected info calls were made
            for expected_call in expected_log_calls:
                self.assertIn(expected_call, mock_logger.info.call_args_list)

    @patch("microsoft_agents_a365.observability.core.exporters.agent365_exporter.logger")
    def test_export_error_logging(self, mock_logger):
        """Test that the exporter logs errors appropriately."""
        # Create spans without tenant/agent identity - explicitly pass None values
        spans = [
            self._create_mock_span(name="test_span", attributes={}, tenant_id=None, agent_id=None)
        ]

        # Export spans (should succeed but log no identity)
        result = self.exporter.export(spans)

        # Verify export succeeded (no identity spans are treated as success)
        self.assertEqual(result, SpanExportResult.SUCCESS)

        # Verify info log for no identity
        mock_logger.info.assert_called_with(
            "No spans with tenant/agent identity found; nothing exported."
        )

    def test_exporter_is_internal(self):
        """Test that _Agent365Exporter is marked as internal/private.

        The underscore prefix convention indicates this class is internal to the SDK
        and should not be instantiated directly by developers.
        """

        self.assertTrue(
            _Agent365Exporter.__name__.startswith("_"),
            "Exporter class should be prefixed with underscore to indicate it's private/internal",
        )

    def test_export_uses_domain_override_when_env_var_set(self):
        """Test that domain override is used when A365_OBSERVABILITY_DOMAIN_OVERRIDE is set."""
        # Arrange
        override_domain = "override.example.com"
        os.environ["A365_OBSERVABILITY_DOMAIN_OVERRIDE"] = override_domain

        # Create exporter after setting environment variable so it reads the override
        exporter = _Agent365Exporter(
            token_resolver=self.mock_token_resolver, cluster_category="test"
        )

        spans = [self._create_mock_span("override_test_span")]

        # Mock the PowerPlatformApiDiscovery class (should not be called when override is set)
        with patch(
            "microsoft_agents_a365.observability.core.exporters.agent365_exporter.PowerPlatformApiDiscovery"
        ) as mock_discovery_class:
            # Mock the _post_with_retries method
            with patch.object(exporter, "_post_with_retries", return_value=True) as mock_post:
                # Act
                result = exporter.export(spans)

                # Assert
                self.assertEqual(result, SpanExportResult.SUCCESS)
                mock_post.assert_called_once()

                # Verify the call arguments - should use override domain with complete URL
                args, kwargs = mock_post.call_args
                url, body, headers = args

                expected_url = f"https://{override_domain}/maven/agent365/agents/test-agent-456/traces?api-version=1"
                self.assertEqual(url, expected_url)

                # Verify PowerPlatformApiDiscovery was not instantiated
                mock_discovery_class.assert_not_called()

    def test_export_uses_default_domain_when_no_override(self):
        """Test that default domain resolution is used when no override is set."""
        # Arrange
        # Ensure override is not set
        os.environ.pop("A365_OBSERVABILITY_DOMAIN_OVERRIDE", None)

        # Create exporter after clearing environment variable
        exporter = _Agent365Exporter(
            token_resolver=self.mock_token_resolver, cluster_category="test"
        )

        spans = [self._create_mock_span("default_domain_span")]

        # Mock the PowerPlatformApiDiscovery class
        with patch(
            "microsoft_agents_a365.observability.core.exporters.agent365_exporter.PowerPlatformApiDiscovery"
        ) as mock_discovery_class:
            mock_discovery = Mock()
            mock_discovery.get_tenant_island_cluster_endpoint.return_value = "default-endpoint.com"
            mock_discovery_class.return_value = mock_discovery

            # Mock the _post_with_retries method
            with patch.object(exporter, "_post_with_retries", return_value=True) as mock_post:
                # Act
                result = exporter.export(spans)

                # Assert
                self.assertEqual(result, SpanExportResult.SUCCESS)
                mock_post.assert_called_once()

                # Verify the call arguments - should use default domain
                args, kwargs = mock_post.call_args
                url, body, headers = args

                self.assertIn("default-endpoint.com", url)
                self.assertIn("/maven/agent365/agents/test-agent-456/traces", url)

                # Verify PowerPlatformApiDiscovery was called
                mock_discovery_class.assert_called_once_with("test")
                mock_discovery.get_tenant_island_cluster_endpoint.assert_called_once_with(
                    "test-tenant-123"
                )

    def test_export_ignores_empty_domain_override(self):
        """Test that empty or whitespace-only domain override is ignored."""
        # Arrange
        os.environ["A365_OBSERVABILITY_DOMAIN_OVERRIDE"] = "   "  # whitespace only

        # Create exporter after setting environment variable
        exporter = _Agent365Exporter(
            token_resolver=self.mock_token_resolver, cluster_category="test"
        )

        spans = [self._create_mock_span("test_span")]

        # Mock the PowerPlatformApiDiscovery class (should be called since override is invalid)
        with patch(
            "microsoft_agents_a365.observability.core.exporters.agent365_exporter.PowerPlatformApiDiscovery"
        ) as mock_discovery_class:
            mock_discovery = Mock()
            mock_discovery.get_tenant_island_cluster_endpoint.return_value = "default-endpoint.com"
            mock_discovery_class.return_value = mock_discovery

            with patch.object(exporter, "_post_with_retries", return_value=True):
                # Act
                result = exporter.export(spans)

                # Assert
                self.assertEqual(result, SpanExportResult.SUCCESS)
                # Verify PowerPlatformApiDiscovery was called (override was ignored)
                mock_discovery_class.assert_called_once_with("test")

    def test_export_uses_valid_url_override_with_https(self):
        """Test that domain override with https:// protocol is accepted and used correctly."""
        # Arrange
        os.environ["A365_OBSERVABILITY_DOMAIN_OVERRIDE"] = "https://override.example.com"

        # Create exporter after setting environment variable
        exporter = _Agent365Exporter(
            token_resolver=self.mock_token_resolver, cluster_category="test"
        )

        spans = [self._create_mock_span("test_span")]

        # Mock the PowerPlatformApiDiscovery class (should NOT be called since override is valid)
        with patch(
            "microsoft_agents_a365.observability.core.exporters.agent365_exporter.PowerPlatformApiDiscovery"
        ) as mock_discovery_class:
            # Mock the _post_with_retries method
            with patch.object(exporter, "_post_with_retries", return_value=True) as mock_post:
                # Act
                result = exporter.export(spans)

                # Assert
                self.assertEqual(result, SpanExportResult.SUCCESS)
                mock_post.assert_called_once()

                # Verify the call arguments - should use override URL without duplicating protocol
                args, kwargs = mock_post.call_args
                url, body, headers = args

                expected_url = "https://override.example.com/maven/agent365/agents/test-agent-456/traces?api-version=1"
                self.assertEqual(url, expected_url)

                # Verify PowerPlatformApiDiscovery was not called
                mock_discovery_class.assert_not_called()

    def test_export_uses_valid_url_override_with_http(self):
        """Test that domain override with http:// protocol is accepted and used correctly."""
        # Arrange
        os.environ["A365_OBSERVABILITY_DOMAIN_OVERRIDE"] = "http://localhost:8080"

        # Create exporter after setting environment variable
        exporter = _Agent365Exporter(
            token_resolver=self.mock_token_resolver, cluster_category="test"
        )

        spans = [self._create_mock_span("test_span")]

        # Mock the PowerPlatformApiDiscovery class (should NOT be called since override is valid)
        with patch(
            "microsoft_agents_a365.observability.core.exporters.agent365_exporter.PowerPlatformApiDiscovery"
        ) as mock_discovery_class:
            # Mock the _post_with_retries method
            with patch.object(exporter, "_post_with_retries", return_value=True) as mock_post:
                # Act
                result = exporter.export(spans)

                # Assert
                self.assertEqual(result, SpanExportResult.SUCCESS)
                mock_post.assert_called_once()

                # Verify the call arguments - should use override URL with http protocol
                args, kwargs = mock_post.call_args
                url, body, headers = args

                expected_url = "http://localhost:8080/maven/agent365/agents/test-agent-456/traces?api-version=1"
                self.assertEqual(url, expected_url)

                # Verify PowerPlatformApiDiscovery was not called
                mock_discovery_class.assert_not_called()

    def test_export_uses_valid_domain_override_with_port(self):
        """Test that domain override with port (no protocol) is accepted and https:// is prepended."""
        # Arrange
        os.environ["A365_OBSERVABILITY_DOMAIN_OVERRIDE"] = "example.com:8080"

        # Create exporter after setting environment variable
        exporter = _Agent365Exporter(
            token_resolver=self.mock_token_resolver, cluster_category="test"
        )

        spans = [self._create_mock_span("test_span")]

        # Mock the PowerPlatformApiDiscovery class (should NOT be called since override is valid)
        with patch(
            "microsoft_agents_a365.observability.core.exporters.agent365_exporter.PowerPlatformApiDiscovery"
        ) as mock_discovery_class:
            # Mock the _post_with_retries method
            with patch.object(exporter, "_post_with_retries", return_value=True) as mock_post:
                # Act
                result = exporter.export(spans)

                # Assert
                self.assertEqual(result, SpanExportResult.SUCCESS)
                mock_post.assert_called_once()

                # Verify the call arguments - should prepend https:// to domain with port
                args, kwargs = mock_post.call_args
                url, body, headers = args

                expected_url = "https://example.com:8080/maven/agent365/agents/test-agent-456/traces?api-version=1"
                self.assertEqual(url, expected_url)

                # Verify PowerPlatformApiDiscovery was not called
                mock_discovery_class.assert_not_called()

    def test_export_ignores_invalid_domain_with_protocol(self):
        """Test that domain override with invalid protocol is ignored."""
        # Arrange
        os.environ["A365_OBSERVABILITY_DOMAIN_OVERRIDE"] = "ftp://invalid.example.com"

        # Create exporter after setting environment variable
        exporter = _Agent365Exporter(
            token_resolver=self.mock_token_resolver, cluster_category="test"
        )

        spans = [self._create_mock_span("test_span")]

        # Mock the PowerPlatformApiDiscovery class (should be called since override is invalid)
        with patch(
            "microsoft_agents_a365.observability.core.exporters.agent365_exporter.PowerPlatformApiDiscovery"
        ) as mock_discovery_class:
            mock_discovery = Mock()
            mock_discovery.get_tenant_island_cluster_endpoint.return_value = "default-endpoint.com"
            mock_discovery_class.return_value = mock_discovery

            with patch.object(exporter, "_post_with_retries", return_value=True):
                # Act
                result = exporter.export(spans)

                # Assert
                self.assertEqual(result, SpanExportResult.SUCCESS)
                # Verify PowerPlatformApiDiscovery was called (override was ignored)
                mock_discovery_class.assert_called_once_with("test")

    def test_export_ignores_invalid_domain_with_path(self):
        """Test that domain override containing path separator is ignored."""
        # Arrange
        os.environ["A365_OBSERVABILITY_DOMAIN_OVERRIDE"] = "invalid.example.com/path"

        # Create exporter after setting environment variable
        exporter = _Agent365Exporter(
            token_resolver=self.mock_token_resolver, cluster_category="test"
        )

        spans = [self._create_mock_span("test_span")]

        # Mock the PowerPlatformApiDiscovery class (should be called since override is invalid)
        with patch(
            "microsoft_agents_a365.observability.core.exporters.agent365_exporter.PowerPlatformApiDiscovery"
        ) as mock_discovery_class:
            mock_discovery = Mock()
            mock_discovery.get_tenant_island_cluster_endpoint.return_value = "default-endpoint.com"
            mock_discovery_class.return_value = mock_discovery

            with patch.object(exporter, "_post_with_retries", return_value=True):
                # Act
                result = exporter.export(spans)

                # Assert
                self.assertEqual(result, SpanExportResult.SUCCESS)
                # Verify PowerPlatformApiDiscovery was called (override was ignored)
                mock_discovery_class.assert_called_once_with("test")


if __name__ == "__main__":
    unittest.main()
