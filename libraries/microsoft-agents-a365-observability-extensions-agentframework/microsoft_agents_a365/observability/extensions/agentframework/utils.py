# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Utility functions for Agent Framework observability extensions."""

from __future__ import annotations

import json


def extract_content_as_string_list(messages_json: str, role_filter: str | None = None) -> str:
    """Extract content values from messages JSON and return as JSON string list."""
    try:
        messages = json.loads(messages_json)
        if isinstance(messages, list):
            contents = []
            for msg in messages:
                if isinstance(msg, dict):
                    role = msg.get("role", "")

                    # Filter by role if specified
                    if role_filter and role != role_filter:
                        continue

                    # Handle Agent Framework format with "parts"
                    parts = msg.get("parts")
                    if parts and isinstance(parts, list):
                        for part in parts:
                            if isinstance(part, dict):
                                part_type = part.get("type", "")
                                # Only extract text content, not tool_call or tool_call_response
                                if part_type == "text" and "content" in part:
                                    contents.append(part["content"])
            return json.dumps(contents)
        return messages_json
    except (json.JSONDecodeError, TypeError):
        # If parsing fails, return as-is
        return messages_json


def extract_input_content(messages_json: str) -> str:
    """Extract text content from user messages only."""
    return extract_content_as_string_list(messages_json, role_filter="user")


def extract_output_content(messages_json: str) -> str:
    """Extract only assistant text content from output messages."""
    return extract_content_as_string_list(messages_json, role_filter="assistant")
