import prediction from '../../../../experiments/torch-trajectory-model-v2.json';
import runtime from '../../../../experiments/tensorrt-qualification-v2.json';
import priorRuntime from '../../../../experiments/tensorrt-qualification-v1.json';
import ranker from '../../../../experiments/active-risk-qualification-v2.json';
import residual from '../../../../experiments/fp16-residual-candidate-v1.json';
import { CAMPAIGN_EVIDENCE } from './campaign-evidence';

export interface ModelStudy {
  id: string;
  title: string;
  subtitle: string;
  status: 'Measured' | 'Not promoted' | 'GPU evidence pending';
  question: string;
  conclusion: string;
  columns: readonly string[];
  rows: readonly { label: string; values: readonly string[] }[];
  context: string;
  gates: readonly { label: string; passed: boolean }[];
  report: string;
  guide: string;
  command?: string;
  requirement: string;
  artifacts?: readonly { label: string; url: string }[];
}

// Public aggregate reports, imported directly instead of copying their results.
// Pin source links to the revision containing these immutable research records.
const SOURCE =
  'https://github.com/ethanvillalovoz/planmargin/blob/6cbd5311f87063dd9556bdc63c75e47df2e0be1d/';
export const sourceLink = (path: string): string => SOURCE + path;
const meters = (value: number): string =>
  `${value.toFixed(value !== 0 && Math.abs(value) < 0.001 ? 6 : 3)} m`;
const ms = (value: number): string => `${value.toFixed(3)} ms`;
const GATE_LABELS: Record<string, string> = {
  beats_constant_velocity_ade: 'Average error below constant velocity',
  beats_constant_velocity_fde: 'Final error below constant velocity',
  byte_identical_repeat: 'Byte-identical repeat on the recorded toolchain',
  finite_training: 'Finite training and outputs',
  minimum_100_scenarios: 'At least 100 real scenarios',
  real_womd_only: 'Real WOMD training records only',
  scenario_level_holdout: 'No scenario crosses train/test boundaries',
  fp16_max_error_under_7_5e_2_m: 'FP16 maximum error < 0.075 m',
  fp16_rmse_under_1e_2_m: 'FP16 RMSE < 0.010 m',
  fp32_max_error_under_1e_4_m: 'FP32 maximum error < 0.0001 m',
  gpu_end_to_end_faster_than_cpu_at_batch_1: 'Batch-1 GPU end-to-end faster than CPU',
  at_least_9_eligible_scenarios: 'At least 9 eligible held-out scenarios',
  budget_8_advantage_at_least_0_25_m: 'Budget-8 margin advantage ≥ 0.25 m',
  budget_8_wins_at_least_7_scenarios: 'Budget-8 wins in at least 7 scenarios',
  coverage_between_0_75_and_0_98: 'Interval coverage between 0.75 and 0.98',
  mean_spearman_at_least_0_25: 'Mean rank correlation ≥ 0.25',
  minimum_500_unique_examples: 'At least 500 unique proposal outcomes',
  zero_scenario_leakage: 'No scenario leakage',
  host_composition_is_fp32: 'Host composition remains FP32',
  physical_probe_is_unchanged: 'Physical probe protocol unchanged',
};
const gates = (values: Record<string, boolean>): ModelStudy['gates'] =>
  Object.entries(values).map(([label, passed]) => ({
    label: GATE_LABELS[label] ?? label.replaceAll('_', ' '),
    passed,
  }));
const artifactRelease =
  'https://github.com/ethanvillalovoz/planmargin/releases/tag/trajectory-model-v2';
const t = runtime.engines;
const i = CAMPAIGN_EVIDENCE.interactionStudy;

export const MODEL_STUDIES: readonly ModelStudy[] = [
  {
    id: 'prediction',
    title: 'Trajectory prediction',
    subtitle: '1,024 real WOMD scenarios',
    status: 'Measured',
    question: 'Does ego history predict a better path than constant velocity?',
    conclusion:
      'The predictor beats constant velocity on the held-out scenarios. It is a research predictor, not the planner used in the campaign.',
    columns: ['Metric · lower is better', 'Predictor', 'Constant velocity'],
    rows: [
      {
        label: 'ADE · average path error',
        values: [
          meters(prediction.test_metrics.ade_m),
          meters(prediction.test_metrics.constant_velocity_ade_m),
        ],
      },
      {
        label: 'FDE · final position error',
        values: [
          meters(prediction.test_metrics.fde_m),
          meters(prediction.test_metrics.constant_velocity_fde_m),
        ],
      },
    ],
    context: `${prediction.split.train_scenarios} training / ${prediction.split.validation_scenarios} validation / ${prediction.split.test_scenarios} test scenarios. ${prediction.test_metrics.windows.toLocaleString()} test windows; whole scenarios stay in one split.`,
    gates: gates(prediction.gates),
    report: 'experiments/torch-trajectory-model-v2.json',
    guide: 'docs/real-womd-scale-study.md',
    command:
      'uv run --frozen --extra nvidia planmargin-train-torch-trajectory --scenario-count 1024 --shard-count 16 --max-windows-per-scenario 128 --epochs 24 --batch-size 512 --device mps --cache artifacts/experiment-v7/womd-window-cache.npz --output artifacts/experiment-v7/torch-trajectory-model --refresh-cache',
    requirement:
      'Training requires authorized WOMD access and local compute. The published model-only release contains weights, ONNX, and aggregate metrics—not licensed scenes.',
    artifacts: [{ label: 'Weights, ONNX & training report', url: artifactRelease }],
  },
  {
    id: 'runtime',
    title: 'TensorRT deployment',
    subtitle: 'Scaled model · Tesla T4',
    status: 'Not promoted',
    question: 'Can the scaled predictor run efficiently without unacceptable numerical drift?',
    conclusion:
      'FP32 is measured. FP16 is not promoted: 0.101 m maximum drift exceeds the frozen 0.075 m limit. More throughput does not override that gate.',
    columns: ['Measurement', 'FP32', 'FP16'],
    rows: [
      {
        label: 'Batch 1 · end-to-end p50',
        values: [
          ms(t.fp32.batches['1'].end_to_end_latency_ms.p50),
          ms(t.fp16.batches['1'].end_to_end_latency_ms.p50),
        ],
      },
      {
        label: 'Batch 256 · end-to-end p50',
        values: [
          ms(t.fp32.batches['256'].end_to_end_latency_ms.p50),
          ms(t.fp16.batches['256'].end_to_end_latency_ms.p50),
        ],
      },
      {
        label: 'Batch 256 · maximum drift',
        values: [
          meters(t.fp32.pytorch_fp32_parity['256'].max_absolute_error_m),
          meters(t.fp16.pytorch_fp32_parity['256'].max_absolute_error_m),
        ],
      },
    ],
    context:
      '500 measured iterations after 50 warmups. End-to-end includes pinned-host transfers and synchronization. Physical probes measure timing/parity only; prediction quality uses the separate WOMD holdout.',
    gates: gates(runtime.gates),
    report: 'experiments/tensorrt-qualification-v2.json',
    guide: 'notebooks/planmargin_tensorrt_colab.ipynb',
    requirement:
      'NVIDIA CUDA/TensorRT required. The notebook requests a free T4 runtime; availability is not guaranteed. Engines are rebuilt for the actual GPU. No paid fallback.',
    artifacts: [
      { label: 'Model-only release', url: artifactRelease },
      {
        label: 'Independent C++17 benchmark',
        url: sourceLink('experiments/tensorrt-cpp-benchmark-v2.json'),
      },
      { label: 'C++ runner & build instructions', url: sourceLink('cpp/tensorrt/README.md') },
    ],
  },
  {
    id: 'reference-runtime',
    title: 'Earlier deployment reference',
    subtitle: '128-scenario model · separate study',
    status: 'Measured',
    question: 'What passed before the corpus was scaled?',
    conclusion:
      'The earlier model passed its own TensorRT gates. Its timing and quality are not substituted for the 1,024-scenario model.',
    columns: ['Measurement', 'FP32', 'FP16'],
    rows: [
      {
        label: 'Batch 1 · device-only p50',
        values: [
          ms(CAMPAIGN_EVIDENCE.inference.fp32Batch1P50Ms),
          ms(CAMPAIGN_EVIDENCE.inference.fp16Batch1P50Ms),
        ],
      },
    ],
    context:
      'Device-only timing excludes host transfers. Do not compare these values to the scaled study’s end-to-end timing as if the measurement boundaries were the same.',
    gates: gates(priorRuntime.gates),
    report: 'experiments/tensorrt-qualification-v1.json',
    guide: 'cpp/tensorrt/README.md',
    requirement:
      'Historical reference. Use the scaled study’s notebook for the current reproducible deployment protocol.',
  },
  {
    id: 'ranker',
    title: 'Proposal ranking',
    subtitle: '2,097 real proposal outcomes',
    status: 'Not promoted',
    question: 'Can a learned ranker find lower-margin candidates within a small test budget?',
    conclusion:
      'The ranker did not generalize across held-out scenarios. Deterministic search remains in use; no learned selector was promoted.',
    columns: ['Held-out evidence', 'Observed', 'Required'],
    rows: [
      {
        label: 'Mean Spearman rank correlation',
        values: [ranker.aggregate.mean_spearman.toFixed(3), '≥ 0.25'],
      },
      {
        label: 'Budget-8 wins over random',
        values: [
          `${ranker.aggregate.budget_8_win_count} / ${ranker.scenario_count}`,
          '≥ 7 scenarios',
        ],
      },
      {
        label: 'Prediction interval coverage',
        values: [ranker.aggregate.interval_coverage.toFixed(3), '0.75–0.98'],
      },
      {
        label: 'Budget-8 margin advantage',
        values: [meters(ranker.aggregate.mean_budget_8_random_minus_learned_m), '≥ 0.25 m'],
      },
    ],
    context:
      'Retrospective scenario-held-out qualification on the frozen campaign. This is not new failure-discovery evidence.',
    gates: gates(ranker.gates),
    report: 'experiments/active-risk-qualification-v2.json',
    guide: 'docs/decisions/0008-experiment-v5-active-mining.md',
    command: 'uv run --frozen planmargin-qualify-active-risk-v6 --help',
    requirement:
      'Reproduction needs the licensed local campaign outputs. Open the command options before choosing the input paths; no model artifact was promoted.',
  },
  {
    id: 'interaction',
    title: 'Neighbor-context ablation',
    subtitle: 'Same-split architecture comparison',
    status: 'Not promoted',
    question: 'Does adding the eight nearest actors improve on ego history alone?',
    conclusion:
      'Nearest-actor pooling worsened both errors. The same-data ego-only model remains the stronger baseline for this study.',
    columns: ['Metric · lower is better', 'With neighbors', 'Ego-only'],
    rows: [
      {
        label: 'ADE · average path error',
        values: [meters(i.interactionAdeMeters), meters(i.egoOnlyAdeMeters)],
      },
      {
        label: 'FDE · final position error',
        values: [meters(i.interactionFdeMeters), meters(i.egoOnlyFdeMeters)],
      },
    ],
    context:
      'Same 820 / 102 / 102 scenario split, training budget, and optimizer for both models. This ablation is separate from the scaled predictor above.',
    gates: [
      { label: 'ADE improves by at least 1%', passed: false },
      { label: 'FDE improves by at least 1%', passed: false },
    ],
    report: 'docs/interaction-model-study.md',
    guide: 'src/planmargin/interaction_trajectory_model.py',
    command: 'uv run --frozen --extra nvidia planmargin-train-interaction-trajectory --help',
    requirement:
      'Training requires authorized WOMD access. This no-go model remains a local research artifact, not a runtime planner or public model release.',
  },
  {
    id: 'residual',
    title: 'Residual FP16 candidate',
    subtitle: 'Apple MPS proxy · not TensorRT',
    status: 'GPU evidence pending',
    question: 'Could FP32 host composition reduce reduced-precision error?',
    conclusion:
      'The local numerical proxy passed. NVIDIA TensorRT has not been measured for this candidate, so deployment promotion remains blocked.',
    columns: ['Proxy measurement', 'Observed', 'Limit'],
    rows: [
      {
        label: 'Maximum absolute error',
        values: [meters(residual.parity.max_absolute_error_m), '0.075 m'],
      },
      { label: 'RMSE', values: [meters(residual.parity.rmse_m), '0.010 m'] },
    ],
    context:
      '256 unchanged deterministic physical probes on Apple MPS. Not an additional real-scene quality evaluation or a CUDA performance result.',
    gates: [
      ...gates(residual.gates),
      { label: 'Independent TensorRT measurement available', passed: residual.tensorrt_measured },
    ],
    report: 'experiments/fp16-residual-candidate-v1.json',
    guide: 'src/planmargin/fp16_residual_candidate.py',
    command: 'uv run --frozen --extra nvidia planmargin-qualify-fp16-residual --help',
    requirement:
      'The local proxy can be reproduced on MPS. An NVIDIA measurement is still required before any FP16 promotion claim.',
  },
];
