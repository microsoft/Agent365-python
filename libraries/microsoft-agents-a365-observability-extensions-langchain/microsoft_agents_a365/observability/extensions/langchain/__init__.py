# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
Wraps the Langchain Agents SDK tracer to integrate with our Telemetry Solution.
"""

from .tracer_instrumentor import CustomLangChainInstrumentor

__all__ = ["CustomLangChainInstrumentor"]

# This is a namespace package
__path__ = __import__("pkgutil").extend_path(__path__, __name__)
