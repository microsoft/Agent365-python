# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""agent-hooks extensions for Microsoft Agent 365 Tooling SDK.

Microsoft Defender for AI real-time protection and Microsoft Purview data loss prevention (DLP)
on the agent-hooks control contract (AGENT-HOOKS-0.1):

- A365DefenderInterceptor: an agent-hooks interceptor that sends each emitted context to
  Defender's prevention endpoint and maps the verdict
- A365DefenderCall: the agent identity and token resolver for one Defender call
- A365PurviewInterceptor: an agent-hooks interceptor that sends the user's message (and the
  agent's reply, audited or enforced) to Purview DLP and maps the decision
- A365PurviewCall: the agent and token resolver for one Purview call
- create_protection_emitter: an enforce-mode, ``parallel/strictest`` emitter
- add_a365_defender, add_a365_purview: register the interceptors on an emitter
"""

from .a365_agent_hooks import add_a365_defender, add_a365_purview, create_protection_emitter
from .a365_defender_interceptor import (
    A365DefenderCall,
    A365DefenderCallResolver,
    A365DefenderInterceptor,
)
from .a365_purview_interceptor import (
    A365PurviewCall,
    A365PurviewCallResolver,
    A365PurviewInterceptor,
)

__all__ = [
    "A365DefenderCall",
    "A365DefenderCallResolver",
    "A365DefenderInterceptor",
    "A365PurviewCall",
    "A365PurviewCallResolver",
    "A365PurviewInterceptor",
    "add_a365_defender",
    "add_a365_purview",
    "create_protection_emitter",
]
