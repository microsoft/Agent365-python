# Changelog — microsoft-agents-a365-observability-extensions-semantickernel

All notable changes to this package will be documented in this file.

## [2.0.0] - 2026-10-20

### Security

- Raised minimum versions: `mcp >= 1.28.1`, `anyio >= 4.14.2`, and
  `python-multipart >= 0.0.30`.

## [1.0.0] - 2026-05-01

### Changed

- Removed `ExecutionType` and `INVOKE_AGENT_OPERATION_NAME` usage from `SpanProcessor`. Removed dead code block for invoke agent spans.
