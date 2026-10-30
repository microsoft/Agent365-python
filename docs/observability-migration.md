# Retiring Agent365 Observability: migration and package-owner actions

The Python observability implementations have moved out of this repository.
New builds contain only Notifications, Runtime, Tooling, and the five Tooling
extensions. Previously published observability releases are not deleted or
yanked by this change. Removing source does not uninstall deployed applications,
update their installed code, or change PyPI project settings.

Use the **[Microsoft OpenTelemetry Distro repository](https://github.com/microsoft/opentelemetry-distro-python)**
and **[`microsoft-opentelemetry` on PyPI](https://pypi.org/project/microsoft-opentelemetry/)**.
The onboarding import is:

```python
from microsoft.opentelemetry import use_microsoft_opentelemetry
```

This is **not a drop-in replacement**. Review the official
[Python Agent365 migration guide](https://github.com/microsoft/opentelemetry-distro-python/blob/main/MIGRATION_A365.md),
[Agent365 API/configuration documentation](https://github.com/microsoft/opentelemetry-distro-python/blob/main/A365_DOCUMENTATION.md),
and [Microsoft Learn onboarding](https://learn.microsoft.com/microsoft-agent-365/developer/microsoft-opentelemetry?tabs=python).
The [archived SDK documentation](https://learn.microsoft.com/microsoft-agent-365/developer/archive/observability-sdk)
describes the old SDK, not the current onboarding path.

## What was removed

Distribution names below are taken from the removed package manifests, not
inferred from directory names. In particular, `agent-framework` and
`semantic-kernel` contain extra hyphens in the **distribution** names.

All source paths were under `libraries/`; all dedicated test paths under `tests/`.

| Retired distribution | Former source directory | Dedicated tests | Former internal dependencies |
|---|---|---|---|
| `microsoft-agents-a365-observability-core` | `microsoft-agents-a365-observability-core` | `observability/core` | Runtime |
| `microsoft-agents-a365-observability-hosting` | `microsoft-agents-a365-observability-hosting` | `observability/hosting` | Core, Runtime |
| `microsoft-agents-a365-observability-extensions-agent-framework` | `microsoft-agents-a365-observability-extensions-agentframework` | `observability/extensions/agentframework` | Core |
| `microsoft-agents-a365-observability-extensions-langchain` | `microsoft-agents-a365-observability-extensions-langchain` | `observability/extensions/langchain` | Core |
| `microsoft-agents-a365-observability-extensions-openai` | `microsoft-agents-a365-observability-extensions-openai` | `observability/extensions/openai` | Core |
| `microsoft-agents-a365-observability-extensions-semantic-kernel` | `microsoft-agents-a365-observability-extensions-semantickernel` | `observability/extensions/semantickernel` | Core |

These packages shared workspace versioning; published internal dependencies were
pinned to the build version. All six workspace entries, manifests, sources,
dedicated tests, and the observability-only usage example are removed.
The retired suite contained all live integration tests in this checkout; its
otherwise-empty CI/tox integration job and credential example are removed too.
Remaining mocked Tooling end-to-end tests continue to run.
Existing changelog entries are preserved unchanged in
[`docs/changelogs`](changelogs/). Historical PRDs describe the design at the time,
not the current package inventory.

Runtime's `get_observability_authentication_scope()`,
`PROD_OBSERVABILITY_SCOPE`, and `PROD_OBSERVABILITY_CLUSTER_CATEGORY` are removed.
Generic environment detection, JWT/identity utilities, operation results, and
Power Platform endpoint discovery remain. No remaining library imports the
removed namespace. Notifications and Tooling behavior, including MCP chat-history
submission, is not replaced by telemetry or removed.

Only exclusive dependencies are removed: LangChain development/instrumentation
dependencies, `wrapt`, the OTLP exporter umbrella/gRPC exporter, OTel
instrumentation, and Azure Monitor exporter/ingestion dependencies. OTel API/SDK
and HTTP/GCP exporters can still appear transitively through retained AI
frameworks; their presence does not mean Agent365 observability is still shipped.

## Consumer installation

Inventory imports and direct/transitive requirements first. Test in an isolated
environment and retain your previous lockfile for rollback. Remove the six
requirements from your manifests, extras, constraints, containers, and deployment
scripts; regenerate your own lockfile with your package manager.

```powershell
python -m pip uninstall -y microsoft-agents-a365-observability-core microsoft-agents-a365-observability-hosting microsoft-agents-a365-observability-extensions-agent-framework microsoft-agents-a365-observability-extensions-langchain microsoft-agents-a365-observability-extensions-openai microsoft-agents-a365-observability-extensions-semantic-kernel
python -m pip install microsoft-opentelemetry
# If you use Microsoft Agents SDK hosting middleware, install its optional extra:
python -m pip install "microsoft-opentelemetry[hosting]"
python -m pip check
```

Do **not** uninstall Runtime, Notifications, Tooling, or shared OpenTelemetry and
framework packages just because observability used them. Keep those needed by
your application. Choose and lock a tested distro version rather than assuming
the latest source API is available in every historical PyPI release.

**Override upstream migration Step 1 for applications using Tooling,
Notifications, or Runtime directly:** keep `microsoft-agents-a365-runtime` and
its generic imports; do not follow the upstream Runtime uninstall/import rewrite
for those usages. The distro's Runtime utilities are not a replacement for the
Runtime dependency of the retained Agent365 packages.

## Imports, APIs, and initialization

| Old surface | Migration |
|---|---|
| `microsoft_agents_a365.observability.core` models, scopes, `BaggageBuilder` | Import supported equivalents from `microsoft.opentelemetry.a365.core`; check signatures in the official migration guide. |
| `configure(service_name, service_namespace, ...)` | Replace startup configuration with `use_microsoft_opentelemetry(enable_a365=True, ...)`; parameters are not positionally compatible. Set service resource attributes using the distro's documented configuration. |
| `token_resolver`, `exporter_options` | Use documented `a365_*` options, such as `a365_token_resolver`; old options objects are not accepted. |
| `microsoft_agents_a365.observability.hosting` | Use `microsoft.opentelemetry.a365.hosting` with the `[hosting]` extra; explicitly configure middleware. |
| Manual framework instrumentors and `.instrument()` calls | Remove retired instrumentor imports and use distro auto-instrumentation; see framework notes below. |
| Runtime observability scope helper | Use `microsoft.opentelemetry.a365.runtime.get_observability_authentication_scope()` only for the matching delegated route; its default differs from the removed app-only helper. See authentication below. |
| `extract_context_from_headers`, `get_traceparent` | Use standard OTel propagation APIs, preserving the required trust boundary and baggage policy. |
| `is_configured()`, exporter options, old enricher registry/processor APIs | No compatible public substitute is promised. Redesign using documented distro options and supported OTel processors. |

Initialize once, before creating framework clients or handling requests. For an
application retaining the old SDK's **app-only S2S** export route, the following
startup function accepts your own synchronous, production token resolver:

```python
import os
from collections.abc import Callable

from microsoft.opentelemetry import use_microsoft_opentelemetry


def initialize_telemetry(token_resolver: Callable[[str, str], str]) -> None:
    os.environ["ENABLE_OBSERVABILITY"] = "true"
    os.environ["ENABLE_A365_OBSERVABILITY_EXPORTER"] = "true"
    use_microsoft_opentelemetry(
        enable_a365=True,
        a365_use_s2s_endpoint=True,
        a365_token_resolver=token_resolver,
    )
```

Supply a resolver that acquires and refreshes the correct app-only token for
`(agent_id, tenant_id)`; a cached token string is not a permanent credential.
Do not log tokens. The `ENABLE_OBSERVABILITY` gate controls scope emission;
enabling Agent365 integration alone is not sufficient. The exporter flag controls
Agent365 delivery separately from enrichment for other exporters.
Do not initialize another competing global tracer provider afterward. Follow the
distro's startup, exporter, flushing, and shutdown guidance when combining Azure
Monitor, OTLP, and Agent365.

### Authentication is route-specific

The removed SDK used `/observabilityService` with an app-only OBS-resource
`/.default` token; its `use_s2s_endpoint` option was deprecated and ignored.
**The distro's similarly named `a365_use_s2s_endpoint` is meaningful**: set it
explicitly when retaining S2S, and supply the matching resolver. It selects a
route, not an automatic S2S authentication implementation. The official
[S2S resolver sample](https://github.com/microsoft/opentelemetry-distro-python/blob/main/samples/a365/s2s/token_resolver.py)
uses `api://9b975845-388f-4429-889e-eab1ef63949c/.default`.

The replacement helper is
`microsoft.opentelemetry.a365.runtime.get_observability_authentication_scope()`.
Without an environment override, it returns a `list[str]` containing
`api://9b975845-388f-4429-889e-eab1ef63949c/Agent365.Observability.OtelWrite`
for the default delegated/agentic route. **Do not use that default as-is in an
app-only S2S resolver.** Acquire the app-only `/.default` scope shown above instead.
An explicit `a365_observability_scope_override` must match that route; a custom
resolver must use the matching scope itself. The helper reads
`A365_OBSERVABILITY_SCOPE_OVERRIDE`, not the initialization keyword argument.

By contrast, the verified distro default FIC resolver requests
`api://9b975845-388f-4429-889e-eab1ef63949c/Agent365.Observability.OtelWrite`
through a delegated `user_fic` exchange, requiring service-connection
configuration, agent instance identity, and agentic-user identity. It is not
equivalent to the old SDK's app-only scope. Consult the official documentation
for required `CONNECTIONS__SERVICE_CONNECTION__SETTINGS__*`,
`A365_AGENT_APP_INSTANCE_ID`, and `A365_AGENTIC_USER_ID` configuration and consent.
When no explicit token resolver is supplied, the distro selects FIC when its
required environment variables are present; otherwise it falls back to
`DefaultAzureCredential`. It does not retry failed FIC exchanges through that
credential chain. The fallback uses the identity selected by the chain, not
necessarily the intended agent identity. Use an explicit, route-appropriate
resolver in production rather than relying on implicit credential selection.
This selection and the scope helper were verified against upstream
[`utils.py`](https://github.com/microsoft/opentelemetry-distro-python/blob/22d129d379060aa38ca7b54f91582a860c4eb0cf/src/microsoft/opentelemetry/a365/core/exporters/utils.py)
and
[`environment_utils.py`](https://github.com/microsoft/opentelemetry-distro-python/blob/22d129d379060aa38ca7b54f91582a860c4eb0cf/src/microsoft/opentelemetry/a365/runtime/environment_utils.py).

The distro also supports `a365_contextual_token_resolver` with a
`TokenResolverContext`; it takes precedence over the simple resolver.
`a365_observability_scope_override` / `A365_OBSERVABILITY_SCOPE_OVERRIDE` must
match the selected identity, cloud, resource, and route. Validate tenant isolation,
permissions, token renewal, endpoint routing, and actual ingestion in a test tenant.
An HTTP success or local console span alone is not proof of Agent365 behavior.

### Context and hosting

Use the distro's supported `BaggageBuilder` context manager:

```python
from microsoft.opentelemetry.a365.core import BaggageBuilder


def handle_request(tenant_id: str, agent_id: str) -> None:
    with BaggageBuilder().tenant_id(tenant_id).agent_id(agent_id).build():
        # Run instrumented agent work within this context.
        pass
```

Supply tenant and agent identity per request, not in mutable process-global state.
The Agent365 exporter requires both for routing and can drop spans without them.
Check agentic-user versus human-user identity semantics when populating baggage.
For inbound/outbound HTTP, use `opentelemetry.propagate.extract` / `inject` and
attach/detach the extracted OTel context with `try/finally`. Validate allowed
baggage at ingress; do not trust unvalidated tenant/agent IDs from callers.
Verify propagation across async work, background tasks, tools, and service hops.
Custom baggage intended as span attributes requires the distro's explicit custom
attribute opt-in; arbitrary `set_pairs()` entries are not automatically copied.

For hosting middleware, import `ObservabilityHostingManager` and
`ObservabilityHostingOptions` from `microsoft.opentelemetry.a365.hosting`, then call
`ObservabilityHostingManager.configure(adapter.middleware_set, options)` once.
Set `ObservabilityHostingOptions(enable_baggage=True, enable_output_logging=True)`
only for the features you need: **both default to false**. Merely changing imports
does not enable baggage or output-message spans. The first singleton configuration
wins. Review privacy/content recording and request identity population explicitly.

### Framework instrumentation and unsupported surfaces

The distro discovers Agent Framework, LangChain, Semantic Kernel, and OpenAI
Agents instrumentation automatically. Framework packages must be installed and
versions must meet upstream support requirements; the distro is not the framework
runtime. Remove the old wrapper/trace-instrumentor setup to avoid duplicate spans.
The A365-specific OpenAI Agents instrumentor and the general OpenAI Agents
instrumentor are selected mutually exclusively. Review `instrumentation_options`
for opt-outs. For Agent365-only mode, general HTTP/web/database instrumentation
is disabled by default; enable required libraries explicitly.

Do not assume the former custom span enrichers, `SpanProcessor`,
`EnrichedReadableSpan`, `Agent365ExporterOptions`, or `SpectraExporterOptions`
have compatible public APIs. Spectra sidecar integration requires a deliberate
move to the distro's standard OTLP configuration, not an options-class rename.
Generic OTLP export **does not preserve** Agent365 authentication, tenant/agent
routing, enrichment, content capture, output logging, or portal ingestion by itself.
Review manual invoke/inference/tool/guardrail/output scopes and their models one
by one against the official migration guide. Validate span relationships,
attributes, message serialization, token usage, sampling, filtering, retries,
offline storage, shutdown delivery, and sensitive-data policy in your application.
Unsupported or undocumented custom behavior needs application changes or an
upstream support decision; this repository supplies no compatibility shim.

## Owner-operated PyPI retirement checklist

These are **manual project-owner actions**, not performed by this repository change.
Apply them to each of the six exact distribution names above; audit any historical
aliases separately rather than assuming directory names are published aliases.

- [ ] Confirm owners, published versions, dependents, support/security policy, and
  the public migration URL. Coordinate documentation, samples, internal feeds,
  enterprise catalogs, and customer announcements.
- [ ] Decide whether a final, separately approved maintenance release is needed
  to update the PyPI long description and project URLs with the notice below.
  Published files/metadata cannot be overwritten by editing this checkout.
  Do not publish empty tombstone packages or force-install the replacement as a
  dependency: neither provides API compatibility.
- [ ] If desired, include a visible, carefully scoped runtime warning in that
  final release. Python `DeprecationWarning` is normally filtered; `FutureWarning`
  is normally visible. Test your warning policy. Already-installed older versions
  do not gain warnings, and users pinned to them may never fetch a new release.
  Announce retirement through release notes, documentation, and direct channels too.
- [ ] After any approved final release, use PyPI **project archival** for each
  project to mark it unmaintained and block further uploads. Existing releases
  remain installable; archival is reversible and does not migrate dependents.
- [ ] Do not delete published releases or yank them by default. Yanking is for a
  specific broken/security-affected release and changes resolver selection; exact
  pins can still install it. Record a reason and assess consumers before any yank.
- [ ] Remove or restrict retired-project upload credentials/trusted publishers,
  including external pipelines and old branches, while preserving publishing for
  the eight active distributions. Verify the retirement on each PyPI project page.

PyPI provides [project archival](https://docs.pypi.org/project-management/archiving-projects/)
and [release yanking](https://docs.pypi.org/project-management/yanking/).
It does **not** provide NuGet-style structured replacement-package recommendations,
automatic install redirection, or a guaranteed pip warning to existing consumers.
An archival banner and a release description linking the migration are supported
ways to discourage new use; neither uninstalls or rewrites consumers' environments.
See also [PyPI's archival announcement](https://blog.pypi.org/posts/2025-01-30-archival/).

### Ready-to-paste retirement notice

> **Retired: Microsoft Agent365 Observability SDK for Python**
>
> This observability distribution is retired and is no longer built or released
> from Agent365-python. For new development, use Microsoft OpenTelemetry Distro:
> https://github.com/microsoft/opentelemetry-distro-python
> and install `microsoft-opentelemetry`:
> https://pypi.org/project/microsoft-opentelemetry/.
>
> Existing applications must review the migration guide before changing packages:
> https://github.com/microsoft/Agent365-python/blob/main/docs/observability-migration.md
> and the official Python API migration:
> https://github.com/microsoft/opentelemetry-distro-python/blob/main/MIGRATION_A365.md.
> This is not a drop-in replacement. Authentication, initialization, propagation,
> and framework instrumentation require review. Previously published versions
> remain available for existing consumers. Notifications, Runtime, and Tooling
> continue in Agent365-python.

Publish this link only after the migration guide is available on the target
branch. Do not promise support timelines without the package owners' approval.

## Release controls and external actions

The checked-in CI builds into a fresh per-job directory, validates the exact
workspace wheel set, version, wheel metadata, dependencies (including extras),
and payload, then copies/uploads only those wheels. The sole publishing job waits
for both Python matrix jobs to succeed and downloads their verified Python 3.11
artifact into a fresh directory. The verifier runs again
immediately before publication and rejects stale versions, extra files, retired
distributions, retired dependencies, and bundled retired source. Upload failures
are no longer ignored. The build remains wheel-only; no sdist upload path is added.
Use `scripts/verify_release_artifacts.py DIRECTORY --version VERSION` for manual
wheel builds too. Never upload an old checkout's `dist/*` or replay old artifacts.

**Repository edits cannot enforce retirement outside this revision.** Owners must:

- [ ] Backport the removal/guard to every maintained `release/*` branch, or disable
  publishing from those branches. Old tags/checkouts and reruns of old workflow
  commits still contain the old build and upload logic.
- [ ] Audit GitHub Actions environments, repository/organization secrets and trusted
  publishers, branch restrictions, queued jobs, manual workflows, and reusable
  workflows outside this repository. Cancel obsolete publishing runs and prevent
  historical workflow reruns from using live retired-project credentials.
  Remove unused observability integration-test credentials and
  `RUN_INTEGRATION_TESTS` configuration after checking other workflows' needs.
- [ ] Before enabling release uploads, set the repository variable
  `AGENT365_PACKAGE_REPOSITORY_URL` to the approved package-upload endpoint and
  configure the `AZURE_DEVOPS_TOKEN` secret with the appropriate feed permissions.
  The workflow passes this URL directly to Twine and fails explicitly if it is
  missing; no `.pypirc` is required and there is no default public PyPI target.
- [ ] Audit external Azure DevOps/release definitions, approvals, service connections,
  artifact promotion/retention, and package-feed-to-PyPI mirroring. A configured
  upload endpoint is not proof of direct public PyPI publishing. The external
  configuration and downstream promotions are not defined here.
- [ ] Remove retired artifacts from pending release inputs/caches/staging drops
  without deleting public releases or unrelated artifacts. Require the active
  distribution allowlist at every external upload/promotion boundary.

The current workflow publishes on SDK-changing pushes to `release/*`, including
development versions; a tag is not required by its publish condition. Restrict
external permissions accordingly rather than relying on tag policy alone.

## Verification sources

Upstream APIs and documentation were checked on 2026-10-28 against
[`microsoft/opentelemetry-distro-python` commit `81ba38b6`](https://github.com/microsoft/opentelemetry-distro-python/tree/81ba38b6da60f4a126266640a9192591e5833e35)
(`README.md`, `MIGRATION_A365.md`, `A365_DOCUMENTATION.md`, and the A365 source
and S2S sample). PyPI listed
[`microsoft-opentelemetry` 1.5.0](https://pypi.org/project/microsoft-opentelemetry/1.5.0/).
Main-branch APIs and released versions can diverge; verify your selected version
against its own release documentation. PyPI lifecycle guidance above is based
on the linked official PyPI documentation, not another registry's capabilities.
