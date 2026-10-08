# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Fakes for the Defender prevention endpoint, the token endpoint, and the agent's token."""

from __future__ import annotations

import base64
import inspect
import json
import re
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import datetime

AGENT_ID = "11111111-1111-1111-1111-111111111111"
TENANT_ID = "22222222-2222-2222-2222-222222222222"
ENDPOINT = "https://prevention.example.test/v1/protection/evaluate"

JsonObject = dict[str, object]

_FRAMEWORK = re.compile(r"[a-z0-9_-]+")
_EXTENSION_KEY = re.compile(r"[a-z][a-z0-9_]*")


@dataclass
class FakeResponse:
    """The parts of an ``aiohttp.ClientResponse`` the client reads."""

    status: int
    body: bytes
    exited: bool = False

    async def read(self) -> bytes:
        return self.body

    async def __aenter__(self) -> FakeResponse:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        self.exited = True


def json_response(body: object, status: int = 200) -> FakeResponse:
    """A JSON response."""
    return FakeResponse(status, json.dumps(body).encode())


def text_response(text: str, status: int = 200) -> FakeResponse:
    """A plain-text response."""
    return FakeResponse(status, text.encode())


Responder = Callable[[JsonObject], FakeResponse | Awaitable[FakeResponse]]


@dataclass(frozen=True)
class RecordedCall:
    """One request the fake prevention endpoint received."""

    url: str
    authorization: str | None
    correlation_id: str | None
    content_type: str | None
    body: JsonObject


class _PendingRequest:
    def __init__(self, respond: Callable[[], Awaitable[FakeResponse]]) -> None:
        self._respond = respond
        self.response: FakeResponse | None = None

    async def __aenter__(self) -> FakeResponse:
        self.response = await self._respond()
        return self.response

    async def __aexit__(self, *_exc: object) -> None:
        if self.response is not None:
            self.response.exited = True


class FakeDefenderSession:
    """Stands in for the ``aiohttp.ClientSession`` the client posts with.

    Records each request and answers with ``respond(body)``, like a fake HTTP handler.
    """

    def __init__(self, respond: Responder) -> None:
        self.respond = respond
        self.calls: list[RecordedCall] = []
        self.closed = False

    @property
    def bodies(self) -> list[JsonObject]:
        """The request bodies, in order."""
        return [call.body for call in self.calls]

    def post(self, url: str, *, data: bytes, headers: Mapping[str, str]) -> _PendingRequest:
        async def respond() -> FakeResponse:
            body = json.loads(data)
            self.calls.append(
                RecordedCall(
                    url=url,
                    authorization=headers.get("Authorization"),
                    correlation_id=headers.get("x-ms-correlation-id"),
                    content_type=headers.get("Content-Type"),
                    body=body,
                )
            )
            response = self.respond(body)
            return await response if inspect.isawaitable(response) else response

        return _PendingRequest(respond)


class FakeTokenSession:
    """Stands in for the ``aiohttp.ClientSession`` the token resolver posts the exchange with."""

    def __init__(
        self, respond: Callable[[], FakeResponse | Awaitable[FakeResponse]] | None = None
    ) -> None:
        self.respond = respond or (
            lambda: json_response({"token_type": "Bearer", "access_token": "defender-token"})
        )
        self.requests: list[tuple[str, dict[str, str]]] = []
        self.pending: list[_PendingRequest] = []
        self.closed = False

    def post(self, url: str, *, data: Mapping[str, str]) -> _PendingRequest:
        async def respond() -> FakeResponse:
            self.requests.append((url, dict(data)))
            response = self.respond()
            return await response if inspect.isawaitable(response) else response

        pending = _PendingRequest(respond)
        self.pending.append(pending)
        return pending


def create_token(lifetime_seconds: float = 3600, **claims: object) -> str:
    """An unsigned JWT that expires after ``lifetime_seconds``."""

    def encode(value: JsonObject) -> str:
        return base64.urlsafe_b64encode(json.dumps(value).encode()).rstrip(b"=").decode()

    payload: JsonObject = {"exp": int(time.time() + lifetime_seconds), **claims}
    return f"{encode({'alg': 'none'})}.{encode(payload)}.signature"


class TokenSource:
    """Resolves a JWT with an hour of lifetime and records each request."""

    def __init__(self, token: str | None = None) -> None:
        self.token = token or create_token(roles=["RealtimeProtection.Evaluate.All"])
        self.requests: list[str] = []

    async def resolve(self, agent_id: str, tenant_id: str, scopes: list[str]) -> str | None:
        self.requests.append(f"{agent_id}|{tenant_id}|{' '.join(scopes)}")
        return self.token


def input_context(text: str) -> JsonObject:
    """An agent-hooks ``input`` context as a host emits it."""
    return {
        "spec": "agent-hooks/0.1",
        "interception_point": "input",
        "timestamp": "2026-10-07T10:00:00.000Z",
        "sequence": 3,
        "agent": {"id": AGENT_ID, "framework": "agent365", "name": "SampleAgent"},
        "session": {"id": "conversation:activity"},
        "target": {"content": text, "role": "user"},
        "input": {"content": text, "role": "user"},
    }


def contract_errors(context: JsonObject) -> list[str]:
    """Mirror the Defender prevention endpoint's request validation.

    Every body the client sends is checked against what the service would reject with a 400
    (required envelope fields, field formats, and tool models without extra members).
    """
    errors: list[str] = []

    def text(node: object) -> str | None:
        return node if isinstance(node, str) else None

    def get(node: object, key: str) -> object:
        return node.get(key) if isinstance(node, dict) else None

    if text(context.get("spec")) != "agent-hooks/0.1":
        errors.append("spec")

    timestamp = text(context.get("timestamp"))
    if timestamp is None or not timestamp.endswith("Z") or not _is_datetime(timestamp):
        errors.append("timestamp")

    sequence = context.get("sequence")
    if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 0:
        errors.append("sequence")

    if not text(get(context.get("agent"), "id")):
        errors.append("agent.id")

    framework = text(get(context.get("agent"), "framework"))
    if framework is None or _FRAMEWORK.fullmatch(framework) is None:
        errors.append("agent.framework")

    if not text(get(context.get("session"), "id")):
        errors.append("session.id")

    if "target" not in context:
        errors.append("target")

    extensions = context.get("extensions")
    if isinstance(extensions, dict) and any(
        _EXTENSION_KEY.fullmatch(key) is None for key in extensions
    ):
        errors.append("extensions")

    if "model" in context and not text(get(context["model"], "id")):
        errors.append("model.id")

    if "tools" in context:
        tools = context["tools"]
        if not isinstance(tools, list) or any(
            not text(get(tool, "name"))
            or (get(tool, "schema") is not None and not isinstance(get(tool, "schema"), dict))
            for tool in tools
        ):
            errors.append("tools")

    kind = get(context.get("actor"), "kind")
    if kind is not None and text(kind) not in ("human", "service", "agent"):
        errors.append("actor.kind")

    tool_call = context.get("tool_call")
    if isinstance(tool_call, dict) and any(
        key not in ("id", "name", "args", "content_hash") for key in tool_call
    ):
        errors.append("tool_call members")

    tool_result = context.get("tool_result")
    if isinstance(tool_result, dict) and any(
        key not in ("value", "is_error", "duration_ms") for key in tool_result
    ):
        errors.append("tool_result members")

    point = text(context.get("interception_point"))
    if point == "input":
        if text(get(context.get("input"), "role")) not in ("user", "system", "external"):
            errors.append("input.role")
        if context.get("target") != context.get("input"):
            errors.append("target != input")
    elif point == "output":
        if context.get("target") != context.get("output"):
            errors.append("target != output")
    elif point in ("pre_tool_call", "post_tool_call"):
        if not text(get(tool_call, "id")) or not text(get(tool_call, "name")):
            errors.append("tool_call")
        if not isinstance(get(tool_call, "args"), dict):
            errors.append("tool_call.args")
        if point == "pre_tool_call":
            if context.get("target") != get(tool_call, "args"):
                errors.append("target != tool_call.args")
        else:
            if not isinstance(get(tool_result, "is_error"), bool):
                errors.append("tool_result.is_error")
            if not isinstance(tool_result, dict) or "value" not in tool_result:
                errors.append("tool_result.value")
            elif context.get("target") != tool_result["value"]:
                errors.append("target != tool_result.value")
    else:
        errors.append("not an evaluated point")

    return errors


def _is_datetime(value: str) -> bool:
    try:
        datetime.fromisoformat(value)
    except ValueError:
        return False
    return True
