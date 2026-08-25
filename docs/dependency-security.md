# Dependency security policy

PlanMargin audits the complete locked Python environment in CI with
`pip-audit==2.10.1`. A newly reported advisory fails the build unless it is an
explicitly reviewed exception in `.github/workflows/ci.yml` and this document.
JavaScript production and development dependencies are audited separately with
`npm audit --audit-level=moderate`.

## Temporary Apache Beam exceptions

Reviewed August 25, 2026:

| Package        | Advisory              | Fixed version | Why the exception exists                       |
| -------------- | --------------------- | ------------- | ---------------------------------------------- |
| `cryptography` | `PYSEC-2026-3552`     | 50.0.0        | Apache Beam 2.75.0 requires `cryptography<48`. |
| `cryptography` | `PYSEC-2026-3553`     | 49.0.0        | Apache Beam 2.75.0 requires `cryptography<48`. |
| `cryptography` | `PYSEC-2026-3554`     | 49.0.0        | Apache Beam 2.75.0 requires `cryptography<48`. |
| `cryptography` | `GHSA-537c-gmf6-5ccf` | 48.0.1        | Apache Beam 2.75.0 requires `cryptography<48`. |
| `httplib2`     | `PYSEC-2026-3444`     | 0.32.0        | Apache Beam 2.75.0 requires `httplib2<0.32`.   |

These are constrained upstream dependencies, not silent suppressions. The
Beam path runs only through the local `DirectRunner`, consumes trusted
operator-selected WOD-derived inputs, writes under the ignored `artifacts/`
boundary, and is not imported by the loopback evidence service or Angular
application. PlanMargin does not expose Beam, `httplib2`, certificate parsing,
PKCS#7 decryption, or ONNX parsing to remote users.

The exceptions must be removed when an Apache Beam release permits the fixed
dependency versions. Any change that makes the dataflow network-facing,
accepts untrusted records, or imports it into the evidence-service process must
remove the exception first or receive a new documented security review.

## Operator boundary

Model-loading commands accept only project-generated or hash-pinned ONNX
artifacts. Dataset and model files obtained outside the documented pinned
sources are untrusted and must not be opened with PlanMargin tooling.
