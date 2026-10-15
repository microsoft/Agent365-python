# Changelog — microsoft-agents-a365-observability-extensions-langchain

All notable changes to this package will be documented in this file.

## [Unreleased]

### Fixed

- **Cache token counts now read the generated message's normalized
  `usage_metadata`** (`gen_ai.usage.cache_read_input_tokens` /
  `gen_ai.usage.cache_write_input_tokens`), falling back to the
  provider-specific `llm_output` usage payload. Previously only
  `llm_output.token_usage`/`llm_output.usage` were checked, which missed
  providers (e.g. ChatAnthropic) that normalize cache details onto the
  generated `AIMessage` instead.

### Changed

- Removed `set_execution_type()` function and all `ExecutionType` / `GEN_AI_EXECUTION_TYPE_KEY` usage.
