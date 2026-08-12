# ADR 0002: Freeze the version-one product checkpoint

- **Status:** Accepted
- **Date:** 2026-08-11
- **Checkpoint revision:** `6224760`

## Context

PlanMargin began as a portfolio project meant to demonstrate autonomous-driving
simulation, applied optimization, data engineering, systems work, and product
judgment in one coherent artifact. The repository now has a substantial
scientific foundation: deterministic WOMD/Waymax replay, a bounded
lead-braking mutation, tested and reference controllers, continuous interaction
metrics, versioned records, a static trajectory comparison, family validation,
and an auditable 320-proposal random-search baseline.

That foundation is necessary, but it is not yet the final product. The current
repository does not contain constrained Bayesian search, a held-out comparison,
an empirical behavioral-realism model, a queryable analytical layer, an API,
or an interactive engineer-facing debugger. Continuing to add internal test
infrastructure without periodically checking the end-to-end product would risk
optimizing the harness rather than finishing the portfolio story.

One scientific gap also needs an explicit decision. Current mutation gates
enforce route, map, continuity, speed, acceleration, and jerk constraints, but
they do not estimate behavioral likelihood from observed WOMD distributions.
The repository already states this limitation in the Stage 0 reports. Until an
empirical gate exists, the implemented experiment is kinematic- and
map-constrained, not fully behavioral-realism-constrained.

## Version-one product definition

PlanMargin version one will be a local, reproducible counterfactual
stress-testing workbench. Given a selected WOMD scenario, it will:

1. search a bounded lead-vehicle-braking space with uniform random search and
   constrained Bayesian optimization under matched budgets;
2. validate every attempted mutation and retain rejected attempts;
3. compare a tested controller with a conservative technical reference under
   the identical counterfactual;
4. persist queryable experiment metadata and aggregate results without
   exposing restricted dataset records;
5. let an engineer inspect original and mutated rollouts, controller outcomes,
   metric timelines, and search provenance in an interactive debugger; and
6. publish a reproducible training and held-out comparison with explicit
   limitations.

The final portfolio demonstration should make this flow understandable in a
few minutes without requiring a recruiter to read the complete research log.

## Checkpoint assessment

| Product responsibility | Status at `6224760` | Evidence or gap |
| --- | --- | --- |
| WOMD/Waymax simulation | Complete foundation | Deterministic replay and bounded scenario loading |
| Mutation and validation | Complete foundation | Lead-braking mutation with physical and map gates |
| Controller comparison | Complete foundation | Tested/reference reruns and four-outcome finding contract |
| Reproducible records | Strong | Versioned schemas, atomic checkpoints, provenance, and privacy boundaries |
| Random-search control | Complete | Fixed 320-proposal training baseline |
| Behavioral realism | Incomplete | No likelihood model estimated from WOMD behavior distributions |
| Bayesian search | Incomplete | No BoTorch model or acquisition policy |
| Held-out evidence | Incomplete | Current ten-scenario set is training-only |
| Analytical data layer | Incomplete | No Parquet/DuckDB experiment tables or SQL analysis |
| Product interface | Prototype only | Static SVG exists; FastAPI/Angular/Three.js debugger does not |
| Systems optimization | Not started | No measured C++ kernel migration or batch-pipeline benchmark |

The project remains aligned in direction. It has completed the experiment
engine's foundation, while the comparative research result and visible product
layers remain ahead. The main risk is sequencing, not a wrong project premise.

## Decision

The remaining work will be sequenced by product responsibility rather than by
technology count:

1. **Resolve the realism contract and freeze the matched-search protocol.**
   Before Bayesian code, decide whether version one adds a lightweight
   empirical braking-behavior gate derived from WOMD or narrows every public
   claim to kinematic/map constraints. The recommended path is the empirical
   gate, followed by a matched random baseline and Bayesian comparison under
   the same contract.
2. **Implement constrained Bayesian search.** Use PyTorch/BoTorch with the
   existing proposal budget, acceptance pipeline, checkpoint semantics, and
   physical-rollout accounting. A zero-finding result remains valid evidence.
3. **Establish development signal, then freeze held-out evaluation.** If the
   unchanged training space provides no qualifying failures for either method,
   introduce a separately versioned controller-regression benchmark rather
   than tuning the observed baseline after the fact.
4. **Build a thin interactive debugger from real experiment records.** Add the
   API and Angular/TypeScript/Three.js interface once both search methods emit
   a shared record contract. This is the first recruiter-facing product slice.
5. **Run the held-out comparison.** Freeze scenarios, seeds, budgets, metrics,
   and statistical summaries before execution.
6. **Add data and systems depth where it owns measured work.** Use
   Parquet/DuckDB for experiment analytics. Migrate one profiled geometry or
   validation hotspot to C++20/pybind11 with parity benchmarks. Add Beam only
   if bounded scenario mining or feature extraction needs a restartable batch
   pipeline.
7. **Polish the public demonstration.** Add a short architecture narrative,
   reproducible local demo path, screenshots or video, and resume-ready impact
   metrics. An AI explanation layer remains optional and downstream of
   deterministic evidence.

## Technology responsibilities

- **Python, JAX, and Waymax:** simulation, mutation orchestration, controllers,
  and deterministic evaluation.
- **PyTorch and BoTorch:** constrained Bayesian modeling and acquisition.
- **Parquet and DuckDB:** queryable experiment and aggregate analysis.
- **FastAPI, Angular, TypeScript, and Three.js:** the engineer-facing debugger.
- **C++20 and pybind11:** one measured compute-intensive kernel, not a rewrite
  for its own sake.
- **Apache Beam:** optional bounded batch extraction only when the workflow
  genuinely requires sharding and restartability.
- **Gemini or another assistant:** optional explanation of already-computed
  evidence; never metric generation or vehicle control.

## Guardrails

- No new tool is added solely so it can appear on a resume.
- No held-out scenario is inspected before its protocol is frozen.
- No failure threshold, controller, or search bound is tuned in response to an
  observed method result without a new versioned experiment.
- The debugger is not postponed until every research extension is complete.
- A negative result is documented and presented as engineering evidence.
- Restricted scenario data remains local and ignored.

## Consequences

This checkpoint adds a realism/protocol decision before Bayesian
implementation and makes the interactive debugger an explicit intermediate
deliverable. It may extend the research schedule, but it closes the largest
claim gap and protects the recruiter-facing product from being deferred behind
infrastructure work. C++, Beam, and an AI assistant remain in scope only when
they acquire a concrete, measured responsibility.
