# microsoft-agents-a365-observability-extensions-agentframework

## Overview

This package provides Agent365 SDK observability extensions for the agent framework.

## Features

- Seamless integration with the Agent Framework
- Supports OpenTelemetry (OTEL) for distributed tracing
- Optional capture of sensitive data for deeper diagnostics
- Easy configuration via environment variables

To allow the A365 observability SDK to capture input and output messages, please enable the flags in environment:
ENABLE_OTEL=true
ENABLE_SENSITIVE_DATA=true