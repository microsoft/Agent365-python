# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""agent-hooks extensions for Microsoft Agent 365 Tooling SDK.

Microsoft Defender for AI real-time protection on the agent-hooks control contract
(AGENT-HOOKS-0.1):

- A365DefenderInterceptor: an agent-hooks interceptor that sends each emitted context to
  Defender's prevention endpoint and maps the verdict
- A365DefenderCall: the agent identity and token resolver for one Defender call
- create_protection_emitter: an enforce-mode, ``parallel/strictest`` emitter
- add_a365_defender: registers the Defender interceptor on an emitter
"""

from .a365_agent_hooks import add_a365_defender, create_protection_emitter
from .a365_defender_interceptor import (
    A365DefenderCall,
    A365DefenderCallResolver,
    A365DefenderInterceptor,
)

__all__ = [
    "A365DefenderCall",
    "A365DefenderCallResolver",
    "A365DefenderInterceptor",
    "add_a365_defender",
    "create_protection_emitter",
]
