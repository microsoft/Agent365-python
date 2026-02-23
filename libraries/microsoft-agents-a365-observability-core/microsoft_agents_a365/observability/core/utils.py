# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

import datetime
import functools
import json
import logging
import traceback
import warnings
from collections.abc import Callable, Hashable, Iterable, Iterator, Mapping
from enum import Enum
from ipaddress import AddressValueError, ip_address
from threading import RLock
from typing import Any, Generic, TypeVar, cast

from opentelemetry import context
from opentelemetry.semconv.attributes.exception_attributes import (
    EXCEPTION_MESSAGE,
    EXCEPTION_STACKTRACE,
)
from opentelemetry.trace import NonRecordingSpan, Span, SpanContext, TraceFlags, set_span_in_context
from opentelemetry.util.types import AttributeValue
from wrapt import ObjectProxy

from microsoft_agents_a365.observability.core.constants import ERROR_TYPE_KEY

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


# W3C Trace Context constants
W3C_TRACE_CONTEXT_VERSION = "00"
W3C_TRACE_ID_LENGTH = 32  # 32 hex chars = 128 bits
W3C_SPAN_ID_LENGTH = 16  # 16 hex chars = 64 bits


def validate_w3c_trace_context_version(version: str) -> bool:
    """Validate W3C Trace Context version.

    Args:
        version: The version string to validate

    Returns:
        True if valid, False otherwise
    """
    return version == W3C_TRACE_CONTEXT_VERSION


def _is_valid_hex(hex_string: str) -> bool:
    """Check if a string contains only valid hexadecimal characters.

    Args:
        hex_string: The string to validate

    Returns:
        True if all characters are valid hexadecimal (0-9, a-f, A-F), False otherwise
    """
    return all(c in "0123456789abcdefABCDEF" for c in hex_string)


def validate_trace_id(trace_id_hex: str) -> bool:
    """Validate W3C Trace Context trace_id format.

    Args:
        trace_id_hex: The trace_id hex string to validate (should be 32 hex chars)

    Returns:
        True if valid (32 hex chars), False otherwise
    """
    return len(trace_id_hex) == W3C_TRACE_ID_LENGTH and _is_valid_hex(trace_id_hex)


def validate_span_id(span_id_hex: str) -> bool:
    """Validate W3C Trace Context span_id format.

    Args:
        span_id_hex: The span_id hex string to validate (should be 16 hex chars)

    Returns:
        True if valid (16 hex chars), False otherwise
    """
    return len(span_id_hex) == W3C_SPAN_ID_LENGTH and _is_valid_hex(span_id_hex)


def parse_parent_id_to_context(parent_id: str | None) -> context.Context | None:
    """Parse a W3C trace context parent ID and return a context with the parent span.

    The parent_id format is expected to be W3C Trace Context format:
    "00-{trace_id}-{span_id}-{trace_flags}"
    Example: "00-1234567890abcdef1234567890abcdef-abcdefabcdef1234-01"

    Args:
        parent_id: The W3C Trace Context format parent ID string

    Returns:
        A context containing the parent span, or None if parent_id is invalid
    """
    if not parent_id:
        return None

    try:
        # W3C Trace Context format: "00-{trace_id}-{span_id}-{trace_flags}"
        parts = parent_id.split("-")
        if len(parts) != 4:
            logger.warning(f"Invalid parent_id format (expected 4 parts): {parent_id}")
            return None

        version, trace_id_hex, span_id_hex, trace_flags_hex = parts

        # Validate W3C Trace Context version
        if not validate_w3c_trace_context_version(version):
            logger.warning(f"Unsupported W3C Trace Context version: {version}")
            return None

        # Validate trace_id (must be 32 hex chars)
        if not validate_trace_id(trace_id_hex):
            logger.warning(
                f"Invalid trace_id (expected {W3C_TRACE_ID_LENGTH} hex chars): '{trace_id_hex}'"
            )
            return None

        # Validate span_id (must be 16 hex chars)
        if not validate_span_id(span_id_hex):
            logger.warning(
                f"Invalid span_id (expected {W3C_SPAN_ID_LENGTH} hex chars): '{span_id_hex}'"
            )
            return None

        # Parse the hex values
        trace_id = int(trace_id_hex, 16)
        span_id = int(span_id_hex, 16)
        trace_flags = TraceFlags(int(trace_flags_hex, 16))

        # Create a SpanContext from the parsed values
        parent_span_context = SpanContext(
            trace_id=trace_id,
            span_id=span_id,
            is_remote=True,
            trace_flags=trace_flags,
        )

        # Create a NonRecordingSpan with the parent context
        parent_span = NonRecordingSpan(parent_span_context)

        # Create a context with the parent span
        return set_span_in_context(parent_span)

    except (ValueError, IndexError) as e:
        logger.warning(f"Failed to parse parent_id '{parent_id}': {e}")
        return None


def safe_json_dumps(obj: Any, **kwargs: Any) -> str:
    return json.dumps(obj, default=str, ensure_ascii=False, **kwargs)


def as_utc_nano(dt: datetime.datetime) -> int:
    return int(dt.astimezone(datetime.UTC).timestamp() * 1_000_000_000)


KeyType = TypeVar("KeyType")
ValueType = TypeVar("ValueType")


def get_first_value(
    mapping: Mapping[KeyType, ValueType], keys: Iterable[KeyType]
) -> ValueType | None:
    """
    Returns the first non-null value corresponding to an input key, or None if
    no non-null value is found.
    """
    if not hasattr(mapping, "get"):
        return None
    return next(
        (value for key in keys if (value := mapping.get(key)) is not None),
        None,
    )


def stop_on_exception(
    wrapped: Callable[..., Iterator[tuple[str, Any]]],
) -> Callable[..., Iterator[tuple[str, Any]]]:
    def wrapper(*args: Any, **kwargs: Any) -> Iterator[tuple[str, Any]]:
        try:
            yield from wrapped(*args, **kwargs)
        except Exception:
            logger.exception("Failed to get attribute.")

    return wrapper


def record_exception(span: Span, error: BaseException) -> None:
    if isinstance(error, Exception):
        span.record_exception(error)
        return
    exception_type = error.__class__.__name__
    exception_message = str(error)
    if not exception_message:
        exception_message = repr(error)
    attributes: dict[str, AttributeValue] = {
        ERROR_TYPE_KEY: exception_type,
        EXCEPTION_MESSAGE: exception_message,
    }
    try:
        attributes[EXCEPTION_STACKTRACE] = traceback.format_exc()
    except Exception:
        logger.exception("Failed to record exception stacktrace.")
    span.add_event(name="exception", attributes=attributes)


@stop_on_exception
def flatten(key_values: Iterable[tuple[str, Any]]) -> Iterator[tuple[str, AttributeValue]]:
    for key, value in key_values:
        if value is None:
            continue
        if isinstance(value, Mapping):
            for sub_key, sub_value in flatten(value.items()):
                yield f"{key}.{sub_key}", sub_value
        elif isinstance(value, list) and any(isinstance(item, Mapping) for item in value):
            for index, sub_mapping in enumerate(value):
                for sub_key, sub_value in flatten(sub_mapping.items()):
                    yield f"{key}.{index}.{sub_key}", sub_value
        else:
            if isinstance(value, Enum):
                value = value.value
            yield key, value


K = TypeVar("K", bound=Hashable)
V = TypeVar("V")


class DictWithLock(ObjectProxy, Generic[K, V]):  # type: ignore
    """
    A wrapped dictionary with lock
    """

    def __init__(self, wrapped: dict[str, V] | None = None) -> None:
        super().__init__(wrapped or {})
        self._self_lock = RLock()

    def get(self, key: K) -> V | None:
        with self._self_lock:
            return cast(V | None, self.__wrapped__.get(key))

    def pop(self, key: K, *args: Any) -> V | None:
        with self._self_lock:
            return cast(V | None, self.__wrapped__.pop(key, *args))

    def __getitem__(self, key: K) -> V:
        with self._self_lock:
            return cast(V, super().__getitem__(key))

    def __setitem__(self, key: K, value: V) -> None:
        with self._self_lock:
            super().__setitem__(key, value)

    def __delitem__(self, key: K) -> None:
        with self._self_lock:
            super().__delitem__(key)


def extract_model_name(span_name: str) -> str | None:
    """
    Extract model name from span names like:
    - 'chat.completions gpt-4o-mini' -> 'gpt-4o-mini'
    - 'chat.completions gpt-3.5-turbo' -> 'gpt-3.5-turbo'
    - 'chat.completions' -> None
    """
    parts = span_name.split(" ")

    if len(parts) == 2:
        return parts[1]
    # If we have more than 2 parts, the model name starts from the 3rd part
    # Format: "chat.completions model-name" or "chat.completions model-name-with-dashes"
    elif len(parts) >= 3:
        # Join everything after "chat.completions" to handle model names with spaces/dashes
        model_name = " ".join(parts[2:])
        return model_name.strip()

    return None


def deprecated(reason: str):
    """Decorator to mark functions as deprecated."""

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            warnings.warn(
                f"{func.__name__}() is deprecated. {reason}",
                category=DeprecationWarning,
                stacklevel=2,
            )
            return func(*args, **kwargs)

        return wrapper

    return decorator


def validate_and_normalize_ip(ip_string: str | None) -> str | None:
    """Validate and normalize an IP address string.

    Args:
        ip_string: The IP address string to validate (IPv4 or IPv6)

    Returns:
        The normalized IP address string if valid, None if invalid or None input

    Logs:
        Error message if the IP address is invalid
    """
    if ip_string is None:
        return None

    try:
        # Validate and normalize IP address
        ip_obj = ip_address(ip_string)
        return str(ip_obj)
    except (ValueError, AddressValueError):
        logger.error(f"Invalid IP address: '{ip_string}'")
        return None
