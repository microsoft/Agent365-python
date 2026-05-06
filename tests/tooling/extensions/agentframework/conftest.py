# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Conftest for Agent Framework tooling extension unit tests.

Ensures that ``agent_framework`` exports required by the production module are
available in the test environment.  In some CI configurations the package is
importable but its internal initialisation leaves certain names absent from the
top-level namespace (e.g. a partial circular-import during collection).  We
patch the stubs in at conftest *module load* time — which pytest guarantees
happens before it imports any test file in this directory tree.
"""

from __future__ import annotations

from unittest.mock import MagicMock

# fmt: off
import agent_framework as _af  # noqa: E402

_REQUIRED = ("RawAgent", "MCPStreamableHTTPTool", "Message", "HistoryProvider")
for _name in _REQUIRED:
    if not hasattr(_af, _name):
        setattr(_af, _name, MagicMock(name=f"agent_framework.{_name}"))
# fmt: on
