# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Utility functions for Semantic Kernel observability extensions."""

from __future__ import annotations

import json


def extract_content_as_string_list(messages_json: str) -> str:
    """Extract content values from messages JSON and return as JSON string list.

    Transforms from: [{"role": "user", "content": "Hello"}]
    To: ["Hello"]

    Args:
        messages_json: JSON string like '[{"role": "user", "content": "Hello"}]'

    Returns:
        JSON string containing only the content values as an array,
        or the original string if parsing fails.
    """
    try:
        messages = json.loads(messages_json)
        if isinstance(messages, list):
            contents = []
            for msg in messages:
                if isinstance(msg, dict) and "content" in msg:
                    contents.append(msg["content"])
                elif isinstance(msg, str):
                    contents.append(msg)
            return json.dumps(contents)
        return messages_json
    except (json.JSONDecodeError, TypeError):
        # If parsing fails, return as-is
        return messages_json
