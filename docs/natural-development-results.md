# Natural matched-search development results

PlanMargin completed its frozen natural-track development comparison on the
ten-scenario WOMD training set. This note reports only campaign-level
aggregates. Scenario identifiers, per-scenario outcomes, proposal records,
feature vectors, support scores, and trajectories remain in ignored private
artifacts.

## Experimental design

The comparison used the protocol frozen before the campaign began:

| Dimension | Value |
| --- | ---: |
| Search methods | uniform random, constrained Bayesian |
| Training scenarios | 10 |
| Seeds per scenario and method | 5 |
| Cells per method | 50 |
| Proposal budget per cell | 32 |
| Proposal budget per method | 1,600 |
| Total cells | 100 |
| Total proposals | 3,200 |

Both methods used the same mutation bounds, controllers, empirical-support
model, finding classifier, proposal budget, and physical-cost accounting. The
campaign evaluated only the `natural` track because the separately frozen
headway-regression original-eligibility gate returned `no_go`.

## Aggregate results

| Metric | Random | Bayesian | Bayesian - random |
| --- | ---: | ---: | ---: |
| Cells with a qualifying finding | 0 / 50 | 0 / 50 | 0 |
| Qualifying findings | 0 | 0 | 0 |
| Pipeline-valid proposals | 944 / 1,600 | 1,245 / 1,600 | +301 |
| Support-and-pipeline-valid proposals | 873 / 1,600 | 1,110 / 1,600 | +237 |
| Support-and-pipeline-valid rate | 54.5625% | 69.3750% | +14.8125 pp |
| Mean final feasible hypervolume | 0.227223 | 0.258250 | +0.031027 |
| Physical rollouts executed | 6,152 | 7,958 | +1,806 |

The complete campaign executed 14,110 physical rollouts, representing
1,128,800 Waymax rollout steps. No proposal met the full qualifying-finding
contract under the frozen 32-proposal cell budget.

## Hypothesis decisions

- **H1 — efficiency: untestable.** Neither method found a qualifying failure,
  so the campaign cannot compare proposals or physical rollouts to a first
  finding. Budget-censored values are not treated as observed discovery costs.
- **H2 — minimality: untestable.** There are no paired cells in which both
  methods found a qualifying failure, so minimum qualifying mutation distances
  cannot be compared.
- **H3 — validity: supported.** The Bayesian support-and-pipeline-valid rate
  exceeded the random rate by 14.8125 percentage points. This clears the
  predeclared noninferiority threshold of -5 percentage points.

The result therefore supports the narrower claim that the constrained
Bayesian proposer preserved—and in this development run increased—the yield
of eligible proposals. It does **not** establish superior failure discovery or
smaller failure-inducing mutations.

## Integrity and reconstruction

All 100 cells passed the sealed-record integrity gates. The final aggregate
report confirmed:

- exact cell and method counts;
- equal proposal budgets;
- unique cell identities;
- one consistent empirical-support model;
- natural-track-only execution; and
- successful reconstruction of every completed cell.

A separate zero-new-cell resume independently replayed the Bayesian decision
chains, revalidated the sealed cell records, and reconstructed the same 100
cells, 3,200 proposals, 14,110 physical rollouts, and hypothesis decisions.
The repository remained clean because all restricted run artifacts are ignored.

## Interpretation and limits

This is a development result across ten selected training scenarios and five
seeds, not a broad statistical generalization. The frozen gates also censored
parts of the proposal space heavily, and some scenarios admitted few or no
eligible mutations. Those outcomes were retained; no thresholds, mutation
bounds, or finding rules were relaxed after observing the data.

The campaign tests an independent methodology using Waymax and WOMD. It does
not evaluate the production Waymo Driver and makes no claim about its safety or
performance. No official held-out WOMD comparative evaluation was run, so this
development result is not a held-out confirmation. A legacy compatibility
smoke had accessed one validation record; it supplied no search result.

The implementation and frozen reporting definitions are documented in the
[natural campaign protocol](matched-search-campaign.md) and the underlying
[empirical-support and matched-search protocol](behavioral-realism-and-matched-search.md).
