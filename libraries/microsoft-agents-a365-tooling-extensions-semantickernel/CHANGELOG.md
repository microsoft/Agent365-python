# Changelog — microsoft-agents-a365-tooling-extensions-semantickernel

All notable changes to this package will be documented in this file.

## [Unreleased]

### Security

- Require `dnspython >= 2.9.2` to address excessive memory and CPU use
  when parsing untrusted WKS records (CVE-2026-128089).

## [2.0.0] - 2026-10-20

### Security

- Raised minimum versions: `mcp >= 1.28.1`, `anyio >= 4.14.2`, and
  `python-multipart >= 0.0.30`.
