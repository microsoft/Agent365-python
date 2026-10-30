# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Unit tests for PurviewDlpOptions."""

from __future__ import annotations

import pytest
from microsoft_agents_a365.tooling.protection.purview import (
    DEFAULT_AUTHENTICATION_SCOPE,
    DEFAULT_GRAPH_BASE_URL,
    PurviewDlpClient,
    PurviewDlpOptions,
)

GRAPH_BASE_URL = "https://graph.example.test/beta"


def test_reads_options_from_the_environment() -> None:
    options = PurviewDlpOptions.from_environment({
        "ENABLE_A365_PURVIEW_DLP": "true",
        "A365_PURVIEW_DLP_GRAPH_BASE_URL": GRAPH_BASE_URL,
        "A365_PURVIEW_DLP_AUTHENTICATION_SCOPE": "https://graph.example.test/.default",
        "A365_PURVIEW_DLP_FAIL_MODE": "CLOSED",
        "A365_PURVIEW_DLP_TIMEOUT_MILLISECONDS": "1500",
        "A365_PURVIEW_DLP_MAX_CONTENT_CHARACTERS": "100",
        "A365_PURVIEW_DLP_RESPONSE_MODE": "Enforce",
    })

    assert options.enabled is True
    assert options.graph_base_url == GRAPH_BASE_URL
    assert options.authentication_scope == "https://graph.example.test/.default"
    assert options.fail_closed is True
    assert options.timeout_seconds == 1.5
    assert options.max_content_characters == 100
    assert options.response_mode == "enforce"


def test_defaults_match_the_other_agent_365_sdks() -> None:
    options = PurviewDlpOptions.from_environment({})

    assert options.enabled is False
    assert options.graph_base_url == "https://graph.microsoft.com/v1.0"
    assert options.authentication_scope == "https://graph.microsoft.com/.default"
    assert options.fail_closed is False
    assert options.timeout_seconds == 10.0
    assert options.max_content_characters == 100000
    assert options.response_mode == "audit"
    assert DEFAULT_GRAPH_BASE_URL == options.graph_base_url
    assert DEFAULT_AUTHENTICATION_SCOPE == options.authentication_scope
    assert PurviewDlpOptions() == options


def test_reads_the_process_environment_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_A365_PURVIEW_DLP", "1")
    monkeypatch.setenv("A365_PURVIEW_DLP_GRAPH_BASE_URL", f" {GRAPH_BASE_URL}/ ")
    monkeypatch.setenv("A365_PURVIEW_DLP_RESPONSE_MODE", " audit ")

    options = PurviewDlpOptions.from_environment()

    assert options.enabled is True
    assert options.graph_base_url == GRAPH_BASE_URL, "trimmed, without the trailing slash"
    assert options.response_mode == "audit"


@pytest.mark.parametrize(
    ("value", "enabled"),
    [
        ("true", True),
        ("TRUE", True),
        ("1", True),
        ("Yes", True),
        ("on", True),
        (" true ", True),
        ("false", False),
        ("0", False),
        ("no", False),
        ("OFF", False),
        ("", False),
        ("   ", False),
    ],
)
def test_parses_the_enable_flag(value: str, enabled: bool) -> None:
    options = PurviewDlpOptions.from_environment({"ENABLE_A365_PURVIEW_DLP": value})

    assert options.enabled is enabled


@pytest.mark.parametrize("value", ["tru", "enabled", "2", "y", "disable"])
def test_rejects_an_enable_flag_that_is_not_true_or_false(value: str) -> None:
    with pytest.raises(ValueError, match="ENABLE_A365_PURVIEW_DLP must be true or false"):
        PurviewDlpOptions.from_environment({"ENABLE_A365_PURVIEW_DLP": value})


@pytest.mark.parametrize(
    ("value", "fail_closed"),
    [("open", False), ("OPEN", False), ("", False), ("closed", True), (" Closed ", True)],
)
def test_reads_the_fail_mode(value: str, fail_closed: bool) -> None:
    options = PurviewDlpOptions.from_environment({"A365_PURVIEW_DLP_FAIL_MODE": value})

    assert options.fail_closed is fail_closed


@pytest.mark.parametrize("value", ["clsoed", "false", "0", "deny"])
def test_rejects_a_fail_mode_that_is_neither_open_nor_closed(value: str) -> None:
    with pytest.raises(ValueError, match='A365_PURVIEW_DLP_FAIL_MODE must be "open" or "closed"'):
        PurviewDlpOptions.from_environment({"A365_PURVIEW_DLP_FAIL_MODE": value})


@pytest.mark.parametrize(
    ("value", "mode"),
    [
        ("audit", "audit"),
        ("AUDIT", "audit"),
        ("", "audit"),
        ("enforce", "enforce"),
        (" ENFORCE ", "enforce"),
    ],
)
def test_reads_the_response_mode(value: str, mode: str) -> None:
    options = PurviewDlpOptions.from_environment({"A365_PURVIEW_DLP_RESPONSE_MODE": value})

    assert options.response_mode == mode


@pytest.mark.parametrize("value", ["block", "enforced", "true", "off"])
def test_rejects_a_response_mode_that_is_neither_audit_nor_enforce(value: str) -> None:
    with pytest.raises(
        ValueError, match='A365_PURVIEW_DLP_RESPONSE_MODE must be "audit" or "enforce"'
    ):
        PurviewDlpOptions.from_environment({"A365_PURVIEW_DLP_RESPONSE_MODE": value})


@pytest.mark.parametrize(
    "name", ["A365_PURVIEW_DLP_TIMEOUT_MILLISECONDS", "A365_PURVIEW_DLP_MAX_CONTENT_CHARACTERS"]
)
@pytest.mark.parametrize(
    "value", ["0", "-5", "ten", "1.5", "nan", "inf", "2147483648", "99999999999999999999"]
)
def test_rejects_a_value_that_is_not_a_positive_integer(name: str, value: str) -> None:
    with pytest.raises(ValueError, match=name):
        PurviewDlpOptions.from_environment({name: value})


def test_accepts_the_largest_integer_the_other_sdks_read() -> None:
    options = PurviewDlpOptions.from_environment({
        "A365_PURVIEW_DLP_TIMEOUT_MILLISECONDS": "2147483647",
        "A365_PURVIEW_DLP_MAX_CONTENT_CHARACTERS": "2147483647",
    })

    assert options.timeout_seconds == 2147483.647
    assert options.max_content_characters == 2147483647
    PurviewDlpClient(options)


@pytest.mark.parametrize(
    "value",
    [
        "not a url",
        "/v1.0",
        "graph.example.test/v1.0",
        "http://graph.example.test/v1.0",
        "ftp://graph.example.test/v1.0",
        "https://graph.example.test/v1.0?x=1",
        "https://graph.example.test/v1.0?",
        "https://graph.example.test/v1.0#me",
    ],
)
def test_rejects_a_graph_base_url_that_is_not_an_absolute_https_url(value: str) -> None:
    with pytest.raises(ValueError, match="A365_PURVIEW_DLP_GRAPH_BASE_URL must be an absolute"):
        PurviewDlpOptions.from_environment({"A365_PURVIEW_DLP_GRAPH_BASE_URL": value})


@pytest.mark.parametrize(
    ("options", "message"),
    [
        (PurviewDlpOptions(graph_base_url="relative/path"), "graph_base_url"),
        (PurviewDlpOptions(graph_base_url="http://graph.example.test/v1.0"), "graph_base_url"),
        (PurviewDlpOptions(graph_base_url="https://graph.example.test/?a=b"), "graph_base_url"),
        (PurviewDlpOptions(timeout_seconds=0), "timeout_seconds"),
        (PurviewDlpOptions(timeout_seconds=-1.0), "timeout_seconds"),
        (PurviewDlpOptions(timeout_seconds=float("nan")), "timeout_seconds"),
        (PurviewDlpOptions(timeout_seconds=float("inf")), "timeout_seconds"),
        (PurviewDlpOptions(timeout_seconds=2147483.648), "timeout_seconds"),
        (PurviewDlpOptions(timeout_seconds=True), "timeout_seconds"),
        (PurviewDlpOptions(max_content_characters=0), "max_content_characters"),
        (PurviewDlpOptions(max_content_characters=1.5), "max_content_characters"),  # type: ignore[arg-type]
        (PurviewDlpOptions(max_content_characters=2**31), "max_content_characters"),
        (PurviewDlpOptions(max_content_characters=True), "max_content_characters"),
        (PurviewDlpOptions(authentication_scope=" "), "authentication_scope"),
        (PurviewDlpOptions(response_mode="Enforce"), "response_mode"),  # type: ignore[arg-type]
    ],
)
def test_validates_the_options_a_client_uses(options: PurviewDlpOptions, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        PurviewDlpClient(options)


def test_the_client_keeps_a_private_copy_of_its_options() -> None:
    options = PurviewDlpOptions(enabled=True, graph_base_url=GRAPH_BASE_URL)
    client = PurviewDlpClient(options)

    options.graph_base_url = "http://graph.example.test/v1.0"
    copy = client.options
    copy.enabled = False

    assert client.options.graph_base_url == GRAPH_BASE_URL
    assert client.options.enabled is True
