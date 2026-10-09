# Changelog

All notable changes to the `microsoft-agents-a365-tooling-extensions-agenthooks` package will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- New package: Microsoft Defender for AI real-time protection and Microsoft Purview data loss prevention (DLP) on the agent-hooks control contract (AGENT-HOOKS-0.1), using `agent-hooks-sdk`
- `A365DefenderInterceptor`: an agent-hooks interceptor, registered as `defender`, that sends each context emitted at `input`, `pre_tool_call`, `post_tool_call` and `output` to Defender's prevention endpoint and maps the verdict (`to_verdict`); other points are allowed without a call. When no verdict is obtained, including when the call resolver returns `None` (no agent identity) or raises, the verdict follows the fail mode; only an exception's type reaches the verdict, and the exception is logged. A Defender warning reason in the reserved `host_error:` namespace becomes `defender:warning`. `on_evaluated` runs on a worker thread once the verdict is decided, so it cannot change the verdict
- `A365DefenderCall`: the agent identity and token resolver for one Defender call
- `create_protection_emitter()`: an enforce-mode `parallel/strictest` emitter whose interceptor timeout leaves room for the Defender timeout
- `add_a365_defender()`: registers the Defender interceptor on an emitter
- `A365PurviewInterceptor`: an agent-hooks interceptor, registered as `purview`, for Microsoft Purview data loss prevention (DLP). At `input` it sends the user's message to Microsoft Graph `processContent` as `uploadText` and denies (`purview:block`, "The request was blocked by a Microsoft Purview data loss prevention policy.", evidence `urn:a365:purview:<client-request-id>`) when a DLP policy blocks it. At `output` it sends the reply as `downloadText`: in the `audit` response mode (default) as a background task that never holds or blocks the reply (kept by a strong reference, bounded by the client timeout, not cancelled by the emitter, its failures contained and reported through `on_evaluated`; `wait_for_pending_audits()` waits for it), and in `enforce` awaited and mapped like `input` ("The response was blocked ..."). Structured content is sent as its string and number values, one per line; content whose text read so far is blank but goes on past the limit follows the fail mode instead of being skipped. Other points and content without text are allowed without a call. When no decision is obtained, including when the call resolver returns `None` or raises, the verdict follows the fail mode (`purview:unverified` warning or `runtime_error:purview_unverified`)
- `A365PurviewCall`: the agent and Graph token resolver for one Purview call
- `add_a365_purview()`: registers the Purview interceptor on an emitter
- `create_protection_emitter()` accepts `purview` options; when they are enabled, the default interceptor timeout is the slower of the Defender and Purview timeouts plus two seconds, so Defender and Purview compose on one emitter. A Defender-only emitter is unchanged
