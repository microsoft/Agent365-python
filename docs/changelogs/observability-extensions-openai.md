# Changelog — microsoft-agents-a365-observability-extensions-openai

All notable changes to this package will be documented in this file.

## [2.0.0] - 2026-10-20

### Added

- Response spans now emit `gen_ai.usage.cache_read.input_tokens` from
  `usage.input_tokens_details.cached_tokens`.

### Changed

- **Response model is emitted as `gen_ai.response.model`** — the model reported
  on the OpenAI `Response` object was previously emitted as
  `gen_ai.request.model`. Update dashboards and queries accordingly.

### Security

- Raised minimum versions: `mcp >= 1.28.1`, `anyio >= 4.14.2`, and
  `python-multipart >= 0.0.30`.

## [1.0.0] - 2026-05-01

### Changed

- Removed `ExecutionType` usage from `OpenAIAgentsTraceProcessor`. Spans no longer set `gen_ai.execution.type`.
