# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Unit tests for DefenderRtpOptions."""

from __future__ import annotations

import pytest
from microsoft_agents_a365.tooling.protection.defender import (
    DEFAULT_AUTHENTICATION_SCOPE,
    DEFENDER_API_APP_ID,
    DefenderRtpClient,
    DefenderRtpOptions,
)

ENDPOINT = "https://prevention.example.test/v1/protection/evaluate"


def test_reads_options_from_the_environment() -> None:
    options = DefenderRtpOptions.from_environment({
        "ENABLE_A365_DEFENDER_RTP": "true",
        "A365_DEFENDER_RTP_ENDPOINT": ENDPOINT,
        "A365_DEFENDER_RTP_FAIL_MODE": "CLOSED",
        "A365_DEFENDER_RTP_TIMEOUT_MILLISECONDS": "1500",
        "A365_DEFENDER_RTP_MAX_CONTENT_CHARACTERS": "100",
    })

    assert options.enabled is True
    assert options.endpoint == ENDPOINT
    assert options.fail_closed is True
    assert options.timeout_seconds == 1.5
    assert options.max_content_characters == 100
    assert options.authentication_scope == DEFAULT_AUTHENTICATION_SCOPE


def test_defaults_match_the_other_agent_365_sdks() -> None:
    options = DefenderRtpOptions.from_environment({})

    assert options.enabled is False
    assert options.endpoint is None
    assert options.fail_closed is False
    assert options.timeout_seconds == 10.0
    assert options.max_content_characters == 20000
    assert options.authentication_scope == f"api://{DEFENDER_API_APP_ID}/.default"
    assert DEFENDER_API_APP_ID == "86a21212-634e-4553-b3d6-e477e4c9d9ec"
    assert DefenderRtpOptions() == options


def test_reads_the_process_environment_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_A365_DEFENDER_RTP", "1")
    monkeypatch.setenv("A365_DEFENDER_RTP_ENDPOINT", ENDPOINT)
    monkeypatch.setenv("A365_DEFENDER_RTP_AUTHENTICATION_SCOPE", " api://custom/.default ")

    options = DefenderRtpOptions.from_environment()

    assert options.enabled is True
    assert options.endpoint == ENDPOINT
    assert options.authentication_scope == "api://custom/.default"


@pytest.mark.parametrize(
    ("value", "enabled"),
    [
        ("true", True),
        ("TRUE", True),
        ("1", True),
        ("Yes", True),
        (" true ", True),
        ("false", False),
        ("0", False),
        ("on", False),
        ("", False),
    ],
)
def test_parses_the_enable_flag(value: str, enabled: bool) -> None:
    options = DefenderRtpOptions.from_environment({"ENABLE_A365_DEFENDER_RTP": value})

    assert options.enabled is enabled


@pytest.mark.parametrize(
    ("value", "fail_closed"),
    [
        ("open", False),
        ("OPEN", False),
        (" Open ", False),
        ("", False),
        ("   ", False),
        ("closed", True),
        ("CLOSED", True),
        (" Closed ", True),
    ],
)
def test_reads_the_fail_mode(value: str, fail_closed: bool) -> None:
    options = DefenderRtpOptions.from_environment({"A365_DEFENDER_RTP_FAIL_MODE": value})

    assert options.fail_closed is fail_closed


@pytest.mark.parametrize("value", ["clsoed", "anything-else", "false", "0", "deny"])
def test_rejects_a_fail_mode_that_is_neither_open_nor_closed(value: str) -> None:
    with pytest.raises(ValueError, match='A365_DEFENDER_RTP_FAIL_MODE must be "open" or "closed"'):
        DefenderRtpOptions.from_environment({"A365_DEFENDER_RTP_FAIL_MODE": value})


@pytest.mark.parametrize(
    "name", ["A365_DEFENDER_RTP_TIMEOUT_MILLISECONDS", "A365_DEFENDER_RTP_MAX_CONTENT_CHARACTERS"]
)
@pytest.mark.parametrize(
    "value", ["0", "-5", "ten", "1.5", "nan", "inf", "2147483648", "99999999999999999999"]
)
def test_rejects_a_value_that_is_not_a_positive_integer(name: str, value: str) -> None:
    with pytest.raises(ValueError, match=name):
        DefenderRtpOptions.from_environment({name: value})


def test_accepts_the_largest_integer_the_other_sdks_read() -> None:
    options = DefenderRtpOptions.from_environment({
        "A365_DEFENDER_RTP_TIMEOUT_MILLISECONDS": "2147483647",
        "A365_DEFENDER_RTP_MAX_CONTENT_CHARACTERS": "2147483647",
    })

    assert options.timeout_seconds == 2147483.647
    assert options.max_content_characters == 2147483647
    DefenderRtpClient(options)


@pytest.mark.parametrize(
    "value",
    [
        "not a url",
        "/v1/protection/evaluate",
        "ftp://prevention.example.test/v1/protection/evaluate",
        "http://prevention.example.test/v1/protection/evaluate",
    ],
)
def test_rejects_an_endpoint_that_is_not_an_absolute_https_url(value: str) -> None:
    with pytest.raises(ValueError, match="A365_DEFENDER_RTP_ENDPOINT must be an absolute HTTPS"):
        DefenderRtpOptions.from_environment({"A365_DEFENDER_RTP_ENDPOINT": value})


def test_requires_an_endpoint_when_enabled() -> None:
    with pytest.raises(ValueError, match="A365_DEFENDER_RTP_ENDPOINT"):
        DefenderRtpClient(DefenderRtpOptions(enabled=True))


@pytest.mark.parametrize(
    ("options", "message"),
    [
        (DefenderRtpOptions(endpoint="relative/path"), "absolute HTTPS URL"),
        (
            DefenderRtpOptions(endpoint="http://prevention.example.test/evaluate"),
            "absolute HTTPS URL",
        ),
        (DefenderRtpOptions(timeout_seconds=0), "timeout_seconds"),
        (DefenderRtpOptions(timeout_seconds=-1.0), "timeout_seconds"),
        (DefenderRtpOptions(timeout_seconds=float("nan")), "timeout_seconds"),
        (DefenderRtpOptions(timeout_seconds=float("inf")), "timeout_seconds"),
        (DefenderRtpOptions(timeout_seconds=2147483.648), "timeout_seconds"),
        (DefenderRtpOptions(timeout_seconds=True), "timeout_seconds"),
        (DefenderRtpOptions(max_content_characters=0), "max_content_characters"),
        (DefenderRtpOptions(max_content_characters=1.5), "max_content_characters"),  # type: ignore[arg-type]
        (DefenderRtpOptions(max_content_characters=float("nan")), "max_content_characters"),  # type: ignore[arg-type]
        (DefenderRtpOptions(max_content_characters=2**31), "max_content_characters"),
        (DefenderRtpOptions(max_content_characters=True), "max_content_characters"),
        (DefenderRtpOptions(authentication_scope=" "), "authentication_scope"),
    ],
)
def test_validates_the_options_a_client_uses(options: DefenderRtpOptions, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        DefenderRtpClient(options)


def test_a_disabled_client_needs_no_endpoint() -> None:
    client = DefenderRtpClient(DefenderRtpOptions())

    assert client.options.enabled is False
