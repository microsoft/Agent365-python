# Integrating with existing OpenTelemetry

**The Agent365 observability SDK formerly documented here is retired from this
repository.** Its `configure()` API, exporter options, and framework instrumentors
are no longer shipped. Do not follow historical setup-order examples as current
instructions.

Use [Microsoft OpenTelemetry Distro](https://github.com/microsoft/opentelemetry-distro-python)
([`microsoft-opentelemetry` on PyPI](https://pypi.org/project/microsoft-opentelemetry/))
and its `microsoft.opentelemetry.use_microsoft_opentelemetry` initializer.
Start with the [repository migration guide](observability-migration.md), then
follow the distro's [official Python migration](https://github.com/microsoft/opentelemetry-distro-python/blob/main/MIGRATION_A365.md)
and [Agent365 configuration documentation](https://github.com/microsoft/opentelemetry-distro-python/blob/main/A365_DOCUMENTATION.md)
for your selected release.

Review tracer-provider initialization, exporter combinations, identity and
authentication, baggage propagation, instrumentation, and shutdown explicitly.
Do not configure competing global providers or duplicate framework instrumentors.
Generic OTLP delivery alone does not preserve Agent365 routing, enrichment,
authentication, or portal behavior. No drop-in compatibility is promised.
