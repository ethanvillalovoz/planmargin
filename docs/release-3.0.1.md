# PlanMargin 3.0.1

PlanMargin 3.0.1 is the repository-hardening patch for the Version 3 product
release. It does not change experiment results, licensed evidence, planner
behavior, the public distribution boundary, or the hosted-application policy.

## Dependency and CI hardening

- Apache Beam advances to 2.75.0, ONNX to 1.22.0, and pytest to 9.1.1.
- CI now audits the complete locked Python environment with the pinned
  `pip-audit==2.10.1` tool.
- Five Apache Beam transitive advisory IDs are explicit, versioned exceptions.
  Their local-only reachability boundary and mandatory removal conditions are
  recorded in the [dependency security policy](dependency-security.md).
- The existing JavaScript dependency audit remains mandatory and reports zero
  known vulnerabilities at the configured severity threshold.

## Clone and documentation polish

- The public quickstart now states the tested Node and npm versions and uses
  the repository's `.nvmrc` before dependency installation.
- README tables are formatting-clean, and the setup guide names the current
  Apache Beam runtime while preserving the original experiment provenance.

The full Python, Angular/Vitest, Playwright, build, evidence-bundle, and
dependency-audit suites passed before release. See the
[release-readiness audit](final-program-audit.md) for the complete verification
boundary.
