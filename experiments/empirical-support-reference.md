# WOMD empirical-support reference model

## Question

Does the exact, predeclared 16-shard WOMD training sample contain at least 160
qualifying lead-braking events, and can those events produce the frozen,
reconstructable split-conformal support gate without changing the event filter
or opening the official validation split?

## Configuration

- WOMD Motion Dataset `1.3.1`, training split;
- the 16 complete training shards frozen in the
  [empirical-support protocol](../docs/behavioral-realism-and-matched-search.md);
- training shard `00000` excluded because it contains the development
  scenarios;
- official WOMD validation untouched;
- the unchanged Stage-0 lead-braking selector, retaining one best qualifying
  lead per scenario with no controller or baseline-validation filter;
- one shared float64 eight-feature extractor over current state through six
  seconds;
- SHA-256 ordering of private scenario identifiers and a deterministic 70/30
  reference/calibration split; and
- robust median/IQR scaling, mean distance to five nearest reference vectors,
  and tie-inclusive split-conformal support at `p_support >= 0.05`.

## Result

The clean run at Git revision `00c3727` produced a
**support-gate-ready** decision. All seven integrity gates passed: all fixed
shards completed, the 160-event minimum was exceeded, event keys were unique,
feature vectors were finite, the model validated, the official validation
split remained untouched, and neither controller nor baseline outcome entered
event selection.

| Measure | Observed |
| --- | ---: |
| Complete fixed shards | 16 of 16 |
| WOMD records streamed | 7,796 |
| Source bytes streamed | 20,993,672,895 |
| Included lead-braking events | 265 |
| Reference events | 185 |
| Calibration events | 80 |
| Parse rejections | 0 |
| Shared-feature rejections after selection | 0 |
| Recorded scan work | 606.886 s (10.11 min) |
| Peak process RSS | 663,879,680 bytes (0.62 GiB) |
| `p_support >= 0.05` nonconformity boundary | 1.553154 |

The permitted aggregate feature distribution is:

| Frozen feature | Minimum | Q25 | Median | Q75 | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| Current longitudinal gap (m) | 7.500 | 20.183 | 27.939 | 34.570 | 59.969 |
| Current closing speed (m/s) | -5.262 | -0.255 | 0.590 | 1.746 | 6.098 |
| Current lead speed (m/s) | 1.455 | 6.738 | 9.652 | 12.624 | 23.315 |
| Peak deceleration (m/s²) | 2.340 | 4.137 | 5.074 | 5.857 | 9.353 |
| Maximum cumulative speed drop (m/s) | 2.049 | 3.498 | 5.179 | 8.119 | 15.350 |
| Maximum one-second speed drop (m/s) | 1.004 | 1.500 | 1.888 | 2.333 | 4.626 |
| Braking nonincrease fraction | 0.683 | 0.900 | 0.950 | 0.983 | 1.000 |
| `log1p` maximum absolute jerk | 3.329 | 4.059 | 4.299 | 4.449 | 4.611 |

The coordinator wrote 16 sealed shard checkpoints, one sealed model, and one
sealed aggregate report. A separate audit-only process reconstructed the model
and report exactly from the checkpoints. All 19 private JSON records also
validated against their checked-in schemas. Git ignore and tracked-file checks
confirmed that none of those records entered the repository.

## Interpretation

The empirical sample-size feasibility question is resolved positively. The
project may now use the frozen gate to test whether a lead-braking
counterfactual has support under this bounded WOMD reference sample. The next
milestone is the method-neutral version-two random/Bayesian development
comparison defined in the frozen protocol.

This result does not estimate a naturalistic behavior density, certify human
driving, or establish real-world safety. The gate depends on the bounded event
filter, the exchangeability assumption behind split conformal inference, and
WOMD's unlabeled mixture of manual and autonomous trajectories.

## Private evidence

The run manifest, per-shard events, private scenario identifiers, event keys,
feature vectors, robust-scaling parameters, reference matrix, calibration
scores, fingerprints, and complete report remain only under the ignored
`artifacts/realism/lead-braking-support-v1/` path.
