# Changelog

All notable changes to the `microsoft-agents-a365-tooling-extensions-agenthooks` package will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- New package: Microsoft Defender for AI real-time protection on the agent-hooks control contract (AGENT-HOOKS-0.1), using `agent-hooks-sdk`
- `A365DefenderInterceptor`: an agent-hooks interceptor, registered as `defender`, that sends each context emitted at `input`, `pre_tool_call`, `post_tool_call` and `output` to Defender's prevention endpoint and maps the verdict (`to_verdict`); other points are allowed without a call. When no verdict is obtained, including when the call resolver returns `None` (no agent identity) or raises, the verdict follows the fail mode; only an exception's type reaches the verdict, and the exception is logged. A Defender warning reason in the reserved `host_error:` namespace becomes `defender:warning`. `on_evaluated` runs on a worker thread once the verdict is decided, so it cannot change the verdict
- `A365DefenderCall`: the agent identity and token resolver for one Defender call
- `create_protection_emitter()`: an enforce-mode `parallel/strictest` emitter whose interceptor timeout leaves room for the Defender timeout
- `add_a365_defender()`: registers the Defender interceptor on an emitter
