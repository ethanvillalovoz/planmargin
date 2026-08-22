# ADR 0009: Reframe active-risk qualification over eligible scenarios

- **Status:** accepted; `qualification_no_go`
- **Date:** 2026-08-21
- **Product milestone:** PlanMargin 2.0

## Context

Experiment v5 stopped before model fitting because one of its ten frozen
scenario orders had no accepted proposal with a controller-separation target.
The corpus nevertheless contains 2,097 unique eligible proposals across the
other nine scenarios. No v5 model metric, ranking curve, or threshold result was
observed.

## Decision

Experiment v6 changes exactly one design fact: its folds cover every scenario
with at least one eligible target rather than requiring all ten original
selection orders. Every other v5 data, feature, target, model, uncertainty,
baseline, budget, privacy, and claim-boundary rule remains unchanged.

The eligible selection orders are sorted before fitting. For each fold, one
order is held out, the preceding eligible order is used only for uncertainty
calibration, and every remaining order is used for fitting. This produces nine
folds with seven training scenarios, one calibration scenario, and one test
scenario. No rows from the absent order are manufactured or imputed.

The frozen gates remain:

| Gate | Threshold |
| --- | --- |
| Evidence scale | At least 500 unique examples across at least 9 eligible scenarios. |
| Scenario isolation | Zero train/calibration/test overlap in every fold. |
| Ranking signal | Mean held-out Spearman correlation at least 0.25. |
| Budget efficiency | At budget 8, mean random-minus-learned best separation at least 0.25 m. |
| Scenario consistency | Learned budget-8 ranking matches or beats random median in at least 7 scenarios. |
| Calibration | Aggregate 90% held-out interval coverage in `[0.75, 0.98]`. |
| Determinism | Two clean runs have the same logical result and byte-identical model bundle. |
| Privacy | Tracked/public output contains no scenario identifier, source location, or feature row. |

If any gate fails, v6 is `qualification_no_go` and no prospective campaign is
authorized. Passing v6 qualifies the model only for the separately frozen
prospective protocol; it does not turn the retrospective evaluation into a new
failure-discovery result.

## Result

The full nine-fold evaluation ran on 2,097 deduplicated real-WOMD/Waymax
examples with zero scenario overlap. Scale and isolation passed. The learned
ranker did not generalize sufficiently:

| Aggregate | Observed | Gate |
| --- | ---: | ---: |
| Mean held-out Spearman correlation | 0.137 | at least 0.25 |
| Mean budget-8 random-minus-learned separation | -0.475 m | at least +0.25 m |
| Budget-8 scenarios matching/beating random | 3 of 9 | at least 7 |
| Calibrated interval coverage | 54.51% | 75–98% |

The status is `qualification_no_go`. No deployment ensemble or ONNX graph was
exported and no prospective campaign was authorized. This result indicates
that the bounded v1 pre-controller features do not transfer planner-margin
behavior reliably across scenes. Later work must add real scene context or new
independent evidence; it may not tune v6 on the same held-out folds and call the
result confirmatory.
