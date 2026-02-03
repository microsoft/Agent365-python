# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Wraps the OpenAI Agents SDK tracer to integrate with the Microsoft Agent 365 Telemetry Solution.
"""

from .trace_instrumentor import OpenAIAgentsTraceInstrumentor

__all__ = ["OpenAIAgentsTraceInstrumentor"]
