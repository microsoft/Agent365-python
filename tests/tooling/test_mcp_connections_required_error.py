# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Unit tests for McpConnectionsRequiredError."""

from microsoft_agents_a365.tooling import McpConnectionsRequiredError


def test_exception_exposes_payload():
    err = McpConnectionsRequiredError(
        missing_connections_url="https://make.example/missing",
        all_connections_url="https://make.example/all",
        connectivity_status="Pending",
        server_names=["mcp_Salesforce", "mcp_Zendesk"],
    )
    assert err.missing_connections_url == "https://make.example/missing"
    assert err.all_connections_url == "https://make.example/all"
    assert err.connectivity_status == "Pending"
    assert err.server_names == ["mcp_Salesforce", "mcp_Zendesk"]


def test_exception_message_is_actionable():
    err = McpConnectionsRequiredError(
        missing_connections_url="https://make.example/missing",
        all_connections_url=None,
        connectivity_status="Pending",
        server_names=["mcp_Salesforce"],
    )
    message = str(err)
    assert "mcp_Salesforce" in message
    assert "https://make.example/missing" in message


def test_exception_is_exception_subclass():
    assert issubclass(McpConnectionsRequiredError, Exception)
