# Changelog — microsoft-agents-a365-observability-extensions-langchain

All notable changes to this package will be documented in this file.

## [2.0.0] - 2026-10-20

### Added

- **Cache token attributes** are now captured from the generated message's normalized
  `usage_metadata` (`gen_ai.usage.cache_read.input_tokens` /
  `gen_ai.usage.cache_write.input_tokens`) or provider-specific `llm_output`
  usage payloads. The released package did not emit cache-token attributes.

### Changed

- **Request and response model identity are now separate** - the served model
  from `llm_output.model_name` or `llm_output.model` moves from
  `gen_ai.request.model` to `gen_ai.response.model`. The request model now
  comes from `metadata.ls_model_name` or `invocation_params`; it remains absent
  when neither source supplies it. Update dashboards that previously treated
  the served model as the request model.
- **Input-token counts use normalized message usage when available** - for
  ChatAnthropic prompt caching, `gen_ai.usage.input_tokens` includes uncached
  input, cache reads, and cache creation rather than only the raw Anthropic
  input count. For example, 100 uncached + 40 cache-read + 10 cache-creation
  tokens reports 150 instead of 100. Do not add cache-token counts to this
  normalized total again. Batched generations retain aggregate `llm_output`
  usage rather than replacing it with a single message's usage.
- **Depends on `langchain-core` instead of the `langchain` meta-package** — the
  package no longer installs `langchain`. Install it separately if your
  application needs it.

### Security

- Raised minimum versions: `langchain-core >= 1.3.3`, `langsmith >= 0.8.18`,
  and `anyio >= 4.14.2`.

## [1.0.0] - 2026-05-01

### Changed

- Removed `set_execution_type()` function and all `ExecutionType` / `GEN_AI_EXECUTION_TYPE_KEY` usage.
