"""Serve privacy-reduced PlanMargin evidence on the local loopback interface."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import secrets
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import duckdb
import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request, Response, Security, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, ConfigDict
from starlette.middleware.trustedhost import TrustedHostMiddleware

from planmargin import analytics
from planmargin import evidence_assistant
from planmargin import experiment_jobs
from planmargin import interaction_metrics
from planmargin import matched_campaign
from planmargin import matched_coordinator
from planmargin import matched_search
from planmargin import proposal_replay
from planmargin import random_search
from planmargin import rollout_record
from planmargin import speed_mutation
from planmargin import test_operations

API_VERSION = "1.1.0"
DEFAULT_ANALYTICS = Path("artifacts/analytics/natural-development-v1")
DEFAULT_CAMPAIGN = Path("artifacts/search-comparison/natural-development-v1")
DEFAULT_ROLLOUTS = Path("artifacts/stage-0/rollout-records.json")
DEFAULT_GAUSSIAN = Path("artifacts/gaussian-field/feasibility")
DEFAULT_SENSOR_SCENE = Path("artifacts/sensor-scene/waymo-front")
DEFAULT_PROPOSAL_REPLAYS = Path("artifacts/proposal-replays/natural-development-v1")
DEFAULT_TEST_OPERATIONS = Path("web/debugger/public/data/test-operations-v2.json")
DEFAULT_ORIGINS = ("http://127.0.0.1:4200", "http://localhost:4200")
SESSION_COOKIE_NAME = "planmargin_local_session"
MAX_JSON_BYTES = 128 * 1024 * 1024
GAUSSIAN_LINKAGE_GATE = 0.90
ASSISTANT_QUESTIONS = {
    "test_health": "Are the release-critical simulation tests healthy?",
    "behavior_coverage": "Which off-nominal behaviors are covered?",
    "campaign_overview": "What happened in the development campaign?",
    "method_comparison": "How did Bayesian compare with random search?",
    "hypothesis_decisions": "What happened to H1, H2, and H3?",
    "claim_boundary": "What is the defensible claim and limitation?",
    "beam_pipeline": "What did the Beam feature pipeline process?",
    "model_performance": "How did the real-WOMD trajectory model perform?",
    "inference_qualification": "What passed and failed in TensorRT qualification?",
    "workbench_provenance": "Which evidence has exact replay and sensor provenance?",
}


class EvidenceModel(BaseModel):
    """Closed response object used to generate the authenticated OpenAPI contract."""

    model_config = ConfigDict(extra="forbid")


class HealthEvidence(EvidenceModel):
    status: Literal["ready"]
    evidence_mode: Literal["real_local_redacted"]
    campaign_ready: bool = True


class CampaignEvidence(EvidenceModel):
    api_version: Literal["1.1.0"]
    evidence_mode: Literal["real_local_redacted"]
    experiment: Literal["v1_immutable"]
    campaign_label: str
    status: str
    decision: str
    recorded_work_seconds: float
    total_physical_rollouts: int
    waymax_rollout_steps: int
    privacy_scope: str
    integrity: Literal["verified"]
    held_out_comparison_run: Literal[False]


class TestOperationSloEvidence(EvidenceModel):
    id: str
    name: str
    indicator: str
    target: str
    observed: str
    objective: float
    observed_value: float
    error_budget_remaining_percent: float
    status: Literal["pass", "fail"]
    owner: str


class TestOperationStageEvidence(EvidenceModel):
    id: str
    name: str
    status: Literal["healthy", "degraded"]
    observed: str
    detail: str


class TestOperationIssueEvidence(EvidenceModel):
    id: str
    severity: Literal["high", "medium", "low"]
    state: Literal["active", "blocked", "stopped", "pending_evidence"]
    component: str
    title: str
    evidence: str
    failed_gates: list[str]
    next_action: str
    source: str
    diagnostic: dict[str, Any]


class TestOperationsEvidence(EvidenceModel):
    schema_version: Literal["2.0.0"]
    record_type: Literal["planmargin.test_operations_report"]
    evidence_mode: Literal["published_aggregate"]
    claim_boundary: str
    campaign: dict[str, Any]
    slo_summary: dict[str, Any]
    slos: list[TestOperationSloEvidence]
    test_inventory: dict[str, Any]
    pipeline_stages: list[TestOperationStageEvidence]
    coverage: dict[str, Any]
    issues: list[TestOperationIssueEvidence]
    source_seals: dict[str, str]
    report_sha256: str


class MethodEvidence(EvidenceModel):
    method: str
    cell_count: int
    proposal_count: int
    finding_cell_count: int
    qualifying_failure_count: int
    support_and_pipeline_valid_rate: float
    mean_final_feasible_hypervolume: float
    total_physical_rollouts: int
    waymax_rollout_steps: int


class HypothesisEvidence(EvidenceModel):
    hypothesis: str
    status: str
    paired_cell_count: int | None
    median_bayesian_minus_random_mutation_distance: float | None
    bayesian_minus_random_valid_rate: float | None
    noninferiority_margin: float | None
    bayesian_finding_count_at_least_random: bool | None
    bayesian_lower_restricted_mean_proposals: bool | None
    bayesian_lower_restricted_mean_physical_rollouts: bool | None


class CellEvidence(EvidenceModel):
    cell_id: str
    method: str
    track: str
    seed: int
    selection_order: int
    decision: str
    proposal_count: int
    pipeline_valid_count: int
    support_and_pipeline_valid_count: int
    qualifying_failure_count: int
    minimum_failure_mutation_distance: float | None
    pipeline_valid_rate: float
    support_and_pipeline_valid_rate: float
    duplicate_proposal_count: int
    final_feasible_hypervolume: float
    total_physical_rollouts: int
    waymax_rollout_steps: int


class ProposalEvidence(EvidenceModel):
    proposal_number: int
    attempt_status: str
    normalized_mutation_distance: float
    mutation_parameters: dict[str, float]
    duplicate_of_proposal_numbers: list[int]
    empirical_support_probability: float | None
    support_passes: bool | None
    objective_available: bool
    objectives: list[float]
    constraints: list[float]
    pipeline_reproducible: bool | None
    policy_specific_avoidable_failure: bool | None
    tested_mutated_failure: bool | None
    reference_mutated_success: bool | None
    physical_rollouts: int
    trajectory_available: bool
    replay_run_id: str | None


class InvestigationProposalEvidence(ProposalEvidence):
    cell_id: str
    method: Literal["random", "bayesian"]
    seed: int
    selection_order: int
    decisive_gate: str


class InvestigationFunnelEvidence(EvidenceModel):
    proposed: int
    mutation_valid: int
    scenario_valid: int
    pipeline_valid: int
    support_valid: int
    reference_passes: int
    tested_fails: int
    qualifying_findings: int


class CampaignInvestigationEvidence(EvidenceModel):
    evidence_mode: Literal["real_local_redacted"]
    integrity: Literal["verified"]
    cell_count: int
    proposal_count: int
    funnel: InvestigationFunnelEvidence
    closest_margin: list[InvestigationProposalEvidence]
    smallest_mutation: list[InvestigationProposalEvidence]
    highest_support: list[InvestigationProposalEvidence]


class ProposalAnalysisFactEvidence(EvidenceModel):
    label: str
    value: str


class ProposalAnalysisEvidence(EvidenceModel):
    evidence_mode: Literal["real_local_redacted"]
    analysis_mode: Literal["deterministic_proposal_specific"]
    cell_id: str
    proposal_number: int
    decision: str
    decisive_gate: str
    explanation: str
    facts: list[ProposalAnalysisFactEvidence]
    record_sha256: str
    trajectory_available: bool
    replay_run_id: str | None


class RunSummaryEvidence(EvidenceModel):
    run_id: str
    label: str
    evidence_mode: Literal["real_local_redacted"]
    collection_status: Literal["complete"]
    record_count: int
    policy_specific_avoidable_failure: bool


class PointEvidence(EvidenceModel):
    x: float
    y: float


class MetricEvidence(EvidenceModel):
    time_seconds: float
    signed_separation_meters: float
    longitudinal_ttc_seconds: float | None


class MutationTargetEvidence(EvidenceModel):
    original: list[PointEvidence]
    counterfactual: list[PointEvidence]


class ControllerOutcomeEvidence(EvidenceModel):
    tested: Literal["fails", "succeeds"]
    reference: Literal["fails", "succeeds"]


class TrajectoryEvidence(EvidenceModel):
    tested: list[PointEvidence]
    reference: list[PointEvidence]
    recorded: list[PointEvidence]


class ReplayHypothesisEvidence(EvidenceModel):
    id: str
    label: str
    mutation_type: str
    mutation_parameters: dict[str, float]
    onset_seconds: float
    target_initial_speed_meters_per_second: float
    supported: bool
    deterministic: bool
    validation_checks: list[str]
    controller_outcome: ControllerOutcomeEvidence
    trajectories: TrajectoryEvidence
    metrics: list[MetricEvidence]


class PrivacyEvidence(EvidenceModel):
    scenario_identifier_exposed: Literal[False]
    source_shard_exposed: Literal[False]
    record_index_exposed: Literal[False]
    raw_provenance_exposed: Literal[False]


class RunEvidence(EvidenceModel):
    schema_version: Literal["planmargin.local-evidence.v1"]
    run_id: str
    scenario_label: str
    evidence_mode: Literal["real_local_redacted"]
    synthetic: Literal[False]
    step_seconds: float
    road_centerlines: list[list[PointEvidence]]
    mutation_target: MutationTargetEvidence
    hypothesis: ReplayHypothesisEvidence
    privacy: PrivacyEvidence


class AssistantQuestionEvidence(EvidenceModel):
    query_id: str
    label: str
    question: str


class AssistantStatusEvidence(EvidenceModel):
    provider_id: Literal["offline_deterministic", "gemini_public_aggregate"]
    model: str | None
    source_mode: Literal["real_local_redacted", "public_aggregate"]
    gemini_configured: bool
    explanation_only: Literal[True]


class AssistantFactEvidence(EvidenceModel):
    fact_id: str
    statement: str
    value: str | int | float | bool | None
    unit: str | None
    citation_id: str


class AssistantCitationEvidence(EvidenceModel):
    citation_id: str
    title: str
    repository_path: str
    sha256: str


class AssistantToolResultEvidence(EvidenceModel):
    query_id: str
    title: str
    source_mode: Literal["real_local_redacted", "public_aggregate"]
    facts: list[AssistantFactEvidence]
    citations: list[AssistantCitationEvidence]


class AssistantExplanationEvidence(EvidenceModel):
    summary: str
    interpretation: str
    cited_fact_ids: list[str]
    limitation: str
    citation_ids: list[str]


class AssistantProviderEvidence(EvidenceModel):
    id: Literal["offline_deterministic", "gemini_public_aggregate"]
    model: str | None
    role: Literal["explanation_only"]


class AssistantQuestionResultEvidence(EvidenceModel):
    sha256: str
    query_id: str
    query_label: str


class AssistantPrivacyEvidence(EvidenceModel):
    raw_question_persisted: Literal[False]
    raw_question_sent_to_provider: Literal[False]
    private_data_sent_to_provider: Literal[False]
    provider_input_scope: Literal["none", "public_aggregate_tool_result_only"]


class AssistantResponseEvidence(EvidenceModel):
    record_type: Literal["planmargin.evidence_assistant_response"]
    schema_version: Literal["1.0.0"]
    status: Literal["answered"]
    question: AssistantQuestionResultEvidence
    provider: AssistantProviderEvidence
    tool_result: AssistantToolResultEvidence
    explanation: AssistantExplanationEvidence
    privacy: AssistantPrivacyEvidence
    limitations: list[str]


class GaussianGeometryEvidence(EvidenceModel):
    median_nearest_mean_distance_m: float
    p90_nearest_mean_distance_m: float
    coverage_within_0_50_m: float


class GaussianFieldEvidence(EvidenceModel):
    schema_version: Literal["1.0.0"]
    evidence_mode: Literal["real_local_redacted"]
    decision: Literal["no_go", "go"]
    representation: Literal["deterministic_lidar_gaussian_field"]
    primitive_count: int
    field_bytes: int
    runtime_seconds: float
    trajectory_linkage_fraction: float
    trajectory_linkage_gate: float
    geometry: GaussianGeometryEvidence
    gates: dict[str, bool]
    claim_boundary: str
    unrestricted_export: Literal[False]


class SensorAssetEvidence(EvidenceModel):
    representation: str
    source_frame_index: int
    primitive_count: int
    bytes: int


class SensorTrajectoryAssetEvidence(EvidenceModel):
    representation: Literal["calibrated_recorded_and_jax_predicted_ego_paths"]
    source_frame_index: int
    bytes: int
    future_steps: int
    step_seconds: float
    model_status: Literal["visualization_qualified"]


class SensorAnnotationEvidence(EvidenceModel):
    representation: Literal["native_tracked_camera_boxes"]
    frame_count: int
    box_count: int
    bytes: int


class SensorSceneEvidence(EvidenceModel):
    schema_version: Literal["1.0.0"]
    evidence_mode: Literal["real_local_sensor"]
    source: Literal["Waymo Open Dataset v2 Perception"]
    segment_id: str
    camera_name: Literal["FRONT"]
    frame_count: int
    frame_rate_hz: int
    annotations: SensorAnnotationEvidence
    reconstruction: SensorAssetEvidence
    reconstruction_reference: SensorAssetEvidence | None = None
    reconstruction_context: SensorAssetEvidence | None = None
    lidar: SensorAssetEvidence
    trajectory: SensorTrajectoryAssetEvidence | None = None


@dataclass(frozen=True)
class EvidencePaths:
    """Fixed artifact locations beneath one repository root."""

    root: Path
    analytics: Path
    campaign: Path
    rollouts: Path
    test_operations: Path | None = None

    @classmethod
    def from_root(cls, root: Path) -> "EvidencePaths":
        resolved = root.resolve(strict=True)
        return cls(
            root=resolved,
            analytics=resolved / DEFAULT_ANALYTICS,
            campaign=resolved / DEFAULT_CAMPAIGN,
            rollouts=resolved / DEFAULT_ROLLOUTS,
            test_operations=resolved / DEFAULT_TEST_OPERATIONS,
        )


def _opaque_id(prefix: str, *parts: object) -> str:
    payload = json.dumps(parts, separators=(",", ":"), ensure_ascii=True)
    digest = hashlib.sha256(payload.encode()).hexdigest()[:20]
    return f"{prefix}_{digest}"


def _json_object(path: Path) -> dict[str, Any]:
    if path.stat().st_size > MAX_JSON_BYTES:
        raise ValueError(f"Evidence file exceeds the local API size limit: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Evidence file is not a JSON object: {path}")
    return value


def _confine_artifact(path: Path, root: Path) -> None:
    artifacts = (root / "artifacts").resolve(strict=True)
    if not path.is_relative_to(artifacts):
        raise ValueError("Evidence path escapes the repository artifact root")


def _rows(connection: duckdb.DuckDBPyConnection, sql: str) -> list[dict[str, Any]]:
    cursor = connection.execute(sql)
    names = [item[0] for item in cursor.description]
    return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]


class EvidenceRepository:
    """Validate private artifacts and expose only allowlisted projections."""

    def __init__(self, paths: EvidencePaths) -> None:
        self.paths = paths
        self.analytics_manifest: dict[str, Any] | None = None
        self.campaign_manifest: dict[str, Any] | None = None
        self.campaign_report: dict[str, Any] | None = None
        self.collection: dict[str, Any] | None = None
        self._cell_by_id: dict[str, tuple[str, int, int]] = {}
        self._run_id: str | None = None
        self._proposal_replays: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
        self._proposal_run_by_identity: dict[tuple[str, int, int, int], str] = {}
        self._investigation_cache: dict[str, Any] | None = None

    @property
    def proposal_replay_count(self) -> int:
        """Return the number of fully validated exact proposal replays."""
        return len(self._proposal_replays)

    def open(self) -> None:
        """Verify every source before accepting requests."""
        artifacts_path = self.paths.root / "artifacts"
        if artifacts_path.is_symlink():
            raise ValueError("Evidence API does not follow artifact symlinks")
        artifacts = artifacts_path.resolve()
        for path in (
            self.paths.analytics,
            self.paths.campaign,
            self.paths.rollouts,
        ):
            resolved = path.resolve(strict=True)
            if not resolved.is_relative_to(artifacts):
                raise ValueError("Evidence path escapes the repository artifact root")
            relative = path.relative_to(self.paths.root)
            if any(
                (self.paths.root / Path(*relative.parts[:index])).is_symlink()
                for index in range(1, len(relative.parts) + 1)
            ):
                raise ValueError("Evidence API does not follow artifact symlinks")

        self.analytics_manifest = self._verify_analytics()
        self.campaign_manifest, self.campaign_report = self._load_campaign_headers()
        if (
            self.analytics_manifest["campaign_manifest_sha256"]
            != self.campaign_manifest["manifest_sha256"]
            or self.analytics_manifest["campaign_report_sha256"]
            != self.campaign_report["report_sha256"]
        ):
            raise ValueError("Analytics do not identify the validated campaign")
        self.collection = _json_object(self.paths.rollouts)
        errors = rollout_record.validate_collection(self.collection)
        if errors:
            raise ValueError("Invalid rollout collection: " + "; ".join(errors))
        if self.collection.get("collection_status") != "complete":
            raise ValueError("The local API requires a complete rollout collection")

        self._run_id = _opaque_id(
            "run",
            self.collection["comparison_key"],
            self.collection["scene_context_sha256"],
        )
        self._cell_by_id = {
            _opaque_id("cell", row["method"], row["seed"], row["selection_order"]): (
                row["method"],
                row["seed"],
                row["selection_order"],
            )
            for row in self._query(
                "SELECT method, seed, selection_order FROM cells "
                "ORDER BY selection_order, seed, method"
            )
        }
        self._load_proposal_replays()

    def _load_proposal_replays(self) -> None:
        """Load optional, separately versioned, proposal-linked replay packages."""
        root = self.paths.root / DEFAULT_PROPOSAL_REPLAYS
        self._proposal_replays = {}
        self._proposal_run_by_identity = {}
        if not root.exists():
            return
        if root.is_symlink() or not root.is_dir():
            raise ValueError("Proposal replay root must be a regular local directory")
        _confine_artifact(root.resolve(), self.paths.root)
        for manifest_path in sorted(root.glob("*/*/*/*/manifest.json")):
            if manifest_path.is_symlink() or not manifest_path.is_file():
                raise ValueError(
                    "Proposal replay manifest must be a regular local file"
                )
            _confine_artifact(manifest_path.resolve(), self.paths.root)
            manifest = _json_object(manifest_path)
            expected = {
                "$schema": proposal_replay.MANIFEST_SCHEMA_URI,
                "schema_version": proposal_replay.SCHEMA_VERSION,
                "record_type": proposal_replay.MANIFEST_TYPE,
                "collection_file": "collection.json",
                "campaign_id": matched_campaign.CAMPAIGN_ID,
            }
            if any(manifest.get(key) != value for key, value in expected.items()):
                raise ValueError("Proposal replay manifest contract is invalid")
            random_search._validate_seal(
                manifest, "manifest_sha256", path=manifest_path
            )
            if manifest.get("privacy") != {
                "contains_restricted_scenario_derivatives": True,
                "unrestricted_export": False,
            }:
                raise ValueError("Proposal replay privacy contract is invalid")
            identity = manifest.get("identity")
            if not isinstance(identity, dict) or identity.get("track") != "natural":
                raise ValueError("Proposal replay identity is invalid")
            try:
                method = identity["method"]
                seed = identity["seed"]
                selection_order = identity["selection_order"]
                proposal_number = identity["proposal_number"]
                cell = matched_coordinator.CellConfig(
                    method, "natural", seed, selection_order
                )
            except (KeyError, TypeError, ValueError) as error:
                raise ValueError("Proposal replay identity is invalid") from error
            if not isinstance(proposal_number, int) or not 1 <= proposal_number <= 32:
                raise ValueError("Proposal replay number is invalid")
            expected_directory = proposal_replay.replay_directory(
                root,
                method=method,
                seed=seed,
                selection_order=selection_order,
                proposal_number=proposal_number,
            )
            if manifest_path.parent.resolve() != expected_directory.resolve():
                raise ValueError("Proposal replay path does not match its identity")
            collection_path = manifest_path.parent / "collection.json"
            if collection_path.is_symlink() or not collection_path.is_file():
                raise ValueError(
                    "Proposal replay collection must be a regular local file"
                )
            if random_search._file_sha256(collection_path) != manifest.get(
                "collection_sha256"
            ):
                raise ValueError("Proposal replay collection hash mismatch")
            collection = _json_object(collection_path)
            errors = rollout_record.validate_collection(collection)
            if errors or collection.get("collection_status") != "complete":
                raise ValueError(
                    "Invalid proposal replay collection: " + "; ".join(errors)
                )
            campaign_directory = matched_campaign.cell_output_dir(
                self.paths.campaign, cell
            )
            run_manifest_path = campaign_directory / "run-manifest.json"
            run_manifest_raw = _json_object(run_manifest_path)
            fingerprint = run_manifest_raw.get("configuration_fingerprint")
            if not isinstance(fingerprint, str) or len(fingerprint) != 64:
                raise ValueError("Proposal replay cell fingerprint is invalid")
            matched_coordinator._load_sealed_record(
                run_manifest_path,
                record_type=matched_coordinator.MANIFEST_TYPE,
                seal_field="manifest_sha256",
                fingerprint=fingerprint,
                cell=cell,
                proposal_index=None,
            )
            if manifest.get("cell_configuration_fingerprint") != fingerprint:
                raise ValueError("Proposal replay identifies a different campaign cell")
            proposal_path = (
                campaign_directory
                / "proposals"
                / f"proposal-{proposal_number - 1:04d}.json"
            )
            proposal = matched_coordinator._load_sealed_record(
                proposal_path,
                record_type=matched_coordinator.PROPOSAL_TYPE,
                seal_field="record_sha256",
                fingerprint=fingerprint,
                cell=cell,
                proposal_index=proposal_number - 1,
            )
            if proposal["attempt"]["status"] != "accepted":
                raise ValueError("Proposal replay links to a rejected proposal")
            if proposal.get("record_sha256") != manifest.get("proposal_record_sha256"):
                raise ValueError("Proposal replay does not link to its sealed proposal")
            original = matched_coordinator._load_sealed_record(
                campaign_directory / "original.json",
                record_type=matched_coordinator.ORIGINAL_TYPE,
                seal_field="checkpoint_sha256",
                fingerprint=fingerprint,
                cell=cell,
                proposal_index=None,
            )
            proposal_replay.validate_retained_collection(
                manifest=manifest,
                collection=collection,
                original_checkpoint=original,
                proposal=proposal,
            )
            key = (method, seed, selection_order, proposal_number)
            if key in self._proposal_run_by_identity:
                raise ValueError("Duplicate proposal replay identity")
            run_id = _opaque_id(
                "run", manifest["proposal_record_sha256"], collection["comparison_key"]
            )
            self._proposal_replays[run_id] = (manifest, collection)
            self._proposal_run_by_identity[key] = run_id

    def _load_campaign_headers(self) -> tuple[dict[str, Any], dict[str, Any]]:
        """Validate the sealed campaign identity linked by the analytics build."""
        manifest = matched_campaign._load_sealed_record(
            self.paths.campaign / "run-manifest.json",
            record_type=matched_campaign.MANIFEST_TYPE,
            schema_uri=matched_campaign.MANIFEST_SCHEMA_URI,
            seal_field="manifest_sha256",
        )
        report = matched_campaign._load_sealed_record(
            self.paths.campaign / "report.json",
            record_type=matched_campaign.REPORT_TYPE,
            schema_uri=matched_campaign.REPORT_SCHEMA_URI,
            seal_field="report_sha256",
        )
        if report.get("campaign_id") != manifest.get("campaign_id"):
            raise ValueError("Campaign report and manifest identities differ")
        if report.get("configuration_fingerprint") != manifest.get(
            "configuration_fingerprint"
        ):
            raise ValueError("Campaign report and manifest configurations differ")
        if report.get("status") != "completed" or report.get("decision") != (
            "campaign_complete"
        ):
            raise ValueError("Evidence API requires a completed campaign")
        return manifest, report

    def _verify_analytics(self) -> dict[str, Any]:
        manifest_path = self.paths.analytics / "manifest.json"
        manifest = _json_object(manifest_path)
        random_search._validate_seal(manifest, "manifest_sha256", path=manifest_path)
        expected = {
            "record_type": analytics.MANIFEST_TYPE,
            "$schema": analytics.MANIFEST_SCHEMA_URI,
            "schema_version": analytics.SCHEMA_VERSION,
            "sql_aggregate_verification": "passed",
        }
        if any(manifest.get(key) != value for key, value in expected.items()):
            raise ValueError("Analytics manifest contract is invalid")

        metadata = manifest.get("database", {})
        if metadata.get("file") != analytics.DATABASE_NAME:
            raise ValueError("Analytics manifest names an unexpected database")
        database = self.paths.analytics / analytics.DATABASE_NAME
        if database.is_symlink() or not database.is_file():
            raise ValueError("Analytics database must be a regular local file")
        if database.stat().st_size != metadata.get("bytes"):
            raise ValueError("Analytics database size does not match its manifest")
        if random_search._file_sha256(database) != metadata.get("sha256"):
            raise ValueError("Analytics database hash does not match its manifest")

        connection = duckdb.connect(str(database), read_only=True)
        try:
            actual_tables = {
                row[0]
                for row in connection.execute(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'main'"
                ).fetchall()
            }
            if actual_tables != set(analytics.TABLE_NAMES):
                raise ValueError("Analytics database table allowlist mismatch")
            counts = {
                table: int(
                    connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                )
                for table in analytics.TABLE_NAMES
            }
            parquet_counts = {}
            parquet_manifest = manifest.get("parquet")
            if not isinstance(parquet_manifest, dict) or set(parquet_manifest) != set(
                analytics.TABLE_NAMES
            ):
                raise ValueError("Analytics Parquet allowlist mismatch")
            for table in analytics.TABLE_NAMES:
                metadata = parquet_manifest[table]
                expected_name = f"{table}.parquet"
                if not isinstance(metadata, dict) or metadata.get("file") != (
                    expected_name
                ):
                    raise ValueError("Analytics manifest names unexpected Parquet")
                parquet = self.paths.analytics / expected_name
                if parquet.is_symlink() or not parquet.is_file():
                    raise ValueError("Analytics Parquet must be a regular local file")
                if parquet.stat().st_size != metadata.get("bytes"):
                    raise ValueError(
                        "Analytics Parquet size does not match its manifest"
                    )
                if random_search._file_sha256(parquet) != metadata.get("sha256"):
                    raise ValueError(
                        "Analytics Parquet hash does not match its manifest"
                    )
                parquet_counts[table] = int(
                    connection.execute(
                        "SELECT count(*) FROM read_parquet(?)", [str(parquet)]
                    ).fetchone()[0]
                )
                if parquet_counts[table] != metadata.get("row_count"):
                    raise ValueError(
                        "Analytics Parquet row count does not match its manifest"
                    )
        finally:
            connection.close()
        if counts != manifest.get("table_row_counts"):
            raise ValueError("Analytics row counts do not match their manifest")
        if parquet_counts != counts:
            raise ValueError("Analytics Parquet row counts do not match DuckDB")
        return manifest

    def _query(self, sql: str) -> list[dict[str, Any]]:
        """Run one source-controlled query against a new read-only connection."""
        database = self.paths.analytics / analytics.DATABASE_NAME
        connection = duckdb.connect(str(database), read_only=True)
        try:
            return _rows(connection, sql)
        finally:
            connection.close()

    def campaign(self) -> dict[str, Any]:
        manifest = self._require(self.analytics_manifest)
        report = self._require(self.campaign_report)
        row = self._query(
            "SELECT status, decision, recorded_work_seconds, "
            "total_physical_rollouts, waymax_rollout_steps FROM campaign"
        )[0]
        return {
            "api_version": API_VERSION,
            "evidence_mode": "real_local_redacted",
            "experiment": "v1_immutable",
            "campaign_label": report["campaign_id"],
            "status": row["status"],
            "decision": row["decision"],
            "recorded_work_seconds": row["recorded_work_seconds"],
            "total_physical_rollouts": row["total_physical_rollouts"],
            "waymax_rollout_steps": row["waymax_rollout_steps"],
            "privacy_scope": manifest["privacy_scope"],
            "integrity": "verified",
            "held_out_comparison_run": False,
        }

    def test_operations(self) -> dict[str, Any]:
        """Return the sealed aggregate operations contract used by the UI."""

        path = self.paths.test_operations or self.paths.root / DEFAULT_TEST_OPERATIONS
        report = test_operations.load_report(path)
        public = dict(report)
        public.pop("$schema", None)
        return public

    def methods(self) -> list[dict[str, Any]]:
        return self._query(
            "SELECT method, cell_count, proposal_count, finding_cell_count, "
            "qualifying_failure_count, support_and_pipeline_valid_rate, "
            "mean_final_feasible_hypervolume, total_physical_rollouts, "
            "waymax_rollout_steps FROM methods ORDER BY method"
        )

    def hypotheses(self) -> list[dict[str, Any]]:
        return self._query(
            "SELECT hypothesis, status, paired_cell_count, "
            "median_bayesian_minus_random_mutation_distance, "
            "bayesian_minus_random_valid_rate, noninferiority_margin, "
            "bayesian_finding_count_at_least_random, "
            "bayesian_lower_restricted_mean_proposals, "
            "bayesian_lower_restricted_mean_physical_rollouts "
            "FROM hypotheses ORDER BY hypothesis"
        )

    def cells(self) -> list[dict[str, Any]]:
        rows = self._query(
            "SELECT method, track, seed, selection_order, decision, "
            "proposal_count, pipeline_valid_count, "
            "support_and_pipeline_valid_count, qualifying_failure_count, "
            "minimum_failure_mutation_distance, pipeline_valid_rate, "
            "support_and_pipeline_valid_rate, duplicate_proposal_count, "
            "final_feasible_hypervolume, total_physical_rollouts, "
            "waymax_rollout_steps FROM cells "
            "ORDER BY selection_order, seed, method"
        )
        for row in rows:
            row["cell_id"] = _opaque_id(
                "cell", row.pop("method"), row["seed"], row["selection_order"]
            )
            method, seed, selection_order = self._cell_by_id[row["cell_id"]]
            row["method"] = method
            if (seed, selection_order) != (row["seed"], row["selection_order"]):
                raise RuntimeError("Opaque cell identity mismatch")
        return rows

    def proposals(self, cell_id: str) -> list[dict[str, Any]]:
        identity = self._cell_by_id.get(cell_id)
        if identity is None:
            raise KeyError(cell_id)
        method, seed, selection_order = identity
        cell = matched_coordinator.CellConfig(method, "natural", seed, selection_order)
        directory = matched_campaign.cell_output_dir(self.paths.campaign, cell)
        campaign_manifest = self._require(self.campaign_manifest)
        report = _json_object(directory / "report.json")
        matched_campaign._validate_cell_report(
            report,
            cell=cell,
            support_model_fingerprint=campaign_manifest["configuration"]["support"][
                "model_fingerprint"
            ],
        )
        if report["metrics"]["proposal_count"] != matched_search.PROPOSAL_BUDGET:
            raise ValueError("Completed cell does not contain the proposal budget")
        run_manifest = matched_coordinator._load_sealed_record(
            directory / "run-manifest.json",
            record_type=matched_coordinator.MANIFEST_TYPE,
            seal_field="manifest_sha256",
            fingerprint=_json_object(directory / "run-manifest.json")[
                "configuration_fingerprint"
            ],
            cell=cell,
            proposal_index=None,
        )
        fingerprint = run_manifest["configuration_fingerprint"]
        result = []
        for index in range(matched_search.PROPOSAL_BUDGET):
            path = directory / "proposals" / f"proposal-{index:04d}.json"
            record = matched_coordinator._load_sealed_record(
                path,
                record_type=matched_coordinator.PROPOSAL_TYPE,
                seal_field="record_sha256",
                fingerprint=fingerprint,
                cell=cell,
                proposal_index=index,
            )
            projection = self._proposal_projection(record, index + 1)
            replay_run_id = self._proposal_run_by_identity.get(
                (method, seed, selection_order, index + 1)
            )
            projection["trajectory_available"] = replay_run_id is not None
            projection["replay_run_id"] = replay_run_id
            result.append(projection)
        return result

    @staticmethod
    def _decisive_gate(proposal: dict[str, Any]) -> str:
        status = proposal["attempt_status"]
        if status == "mutation_rejected":
            return "mutation_geometry"
        if status == "scenario_rejected":
            return "scenario_validity"
        if proposal["pipeline_reproducible"] is not True:
            return "pipeline_reproducibility"
        if proposal["support_passes"] is not True:
            return "empirical_support"
        if proposal["reference_mutated_success"] is not True:
            return "reference_controller"
        if proposal["tested_mutated_failure"] is not True:
            return "tested_controller_failure"
        if proposal["policy_specific_avoidable_failure"] is not True:
            return "finding_contract"
        return "qualifying_finding"

    @staticmethod
    def _proximity_label(value: float) -> str:
        if value <= 0:
            return "minimum clearance unavailable"
        clearance_m = max(1.0 / value - 1.0, 0.0)
        if clearance_m < 0.005:
            return "contact boundary reached"
        return f"{clearance_m:.2f} m minimum clearance"

    @staticmethod
    def _change_size_label(value: float) -> str:
        bounded_edit_percent = min(max((1.0 - value) * 100.0, 0.0), 100.0)
        if bounded_edit_percent <= 20.0:
            size = "small"
        elif bounded_edit_percent <= 50.0:
            size = "moderate"
        else:
            size = "large"
        return f"{size} edit · {bounded_edit_percent:.0f}% of bounded range"

    @staticmethod
    def _proposal_projection(record: dict[str, Any], number: int) -> dict[str, Any]:
        finding = record["finding"]
        support = record["support"]
        return {
            "proposal_number": number,
            "attempt_status": record["attempt"]["status"],
            "normalized_mutation_distance": record["proposal"][
                "normalized_mutation_distance"
            ],
            "mutation_parameters": record["proposal"]["parameters"],
            "duplicate_of_proposal_numbers": [
                prior + 1
                for prior in record["proposal"]["duplicate_of_proposal_indices"]
            ],
            "empirical_support_probability": (
                support["p_support"] if support is not None else None
            ),
            "support_passes": support["passes"] if support is not None else None,
            "objective_available": record["outcome"]["objective_available"],
            "objectives": record["outcome"]["objectives"],
            "constraints": record["outcome"]["constraints"],
            "pipeline_reproducible": (
                finding["pipeline_reproducible"] if finding is not None else None
            ),
            "policy_specific_avoidable_failure": (
                finding["policy_specific_avoidable_failure"]
                if finding is not None
                else None
            ),
            "tested_mutated_failure": (
                finding["tested_mutated_failure"] if finding is not None else None
            ),
            "reference_mutated_success": (
                finding["reference_mutated_success"] if finding is not None else None
            ),
            "physical_rollouts": record["cost"]["total_physical_rollouts"],
        }

    def investigation(self) -> dict[str, Any]:
        """Build and cache a verified campaign-wide proposal index."""
        if self._investigation_cache is not None:
            return self._investigation_cache
        rows: list[dict[str, Any]] = []
        for cell_id, (method, seed, selection_order) in self._cell_by_id.items():
            for proposal in self.proposals(cell_id):
                enriched = {
                    **proposal,
                    "cell_id": cell_id,
                    "method": method,
                    "seed": seed,
                    "selection_order": selection_order,
                }
                enriched["decisive_gate"] = self._decisive_gate(enriched)
                rows.append(enriched)

        objective_rows = [row for row in rows if row["objective_available"]]
        support_rows = [
            row for row in rows if row["empirical_support_probability"] is not None
        ]
        result = {
            "evidence_mode": "real_local_redacted",
            "integrity": "verified",
            "cell_count": len(self._cell_by_id),
            "proposal_count": len(rows),
            "funnel": {
                "proposed": len(rows),
                "mutation_valid": sum(
                    row["attempt_status"] != "mutation_rejected" for row in rows
                ),
                "scenario_valid": sum(
                    row["attempt_status"] == "accepted" for row in rows
                ),
                "pipeline_valid": sum(
                    row["pipeline_reproducible"] is True for row in rows
                ),
                "support_valid": sum(row["support_passes"] is True for row in rows),
                "reference_passes": sum(
                    row["pipeline_reproducible"] is True
                    and row["support_passes"] is True
                    and row["reference_mutated_success"] is True
                    for row in rows
                ),
                "tested_fails": sum(
                    row["pipeline_reproducible"] is True
                    and row["support_passes"] is True
                    and row["reference_mutated_success"] is True
                    and row["tested_mutated_failure"] is True
                    for row in rows
                ),
                "qualifying_findings": sum(
                    row["policy_specific_avoidable_failure"] is True for row in rows
                ),
            },
            "closest_margin": sorted(
                objective_rows,
                key=lambda row: (
                    -row["objectives"][0],
                    -row["objectives"][1],
                    row["cell_id"],
                    row["proposal_number"],
                ),
            )[:20],
            "smallest_mutation": sorted(
                objective_rows,
                key=lambda row: (
                    -row["objectives"][1],
                    -row["objectives"][0],
                    row["cell_id"],
                    row["proposal_number"],
                ),
            )[:20],
            "highest_support": sorted(
                support_rows,
                key=lambda row: (
                    -row["empirical_support_probability"],
                    -row["objectives"][0],
                    row["cell_id"],
                    row["proposal_number"],
                ),
            )[:20],
        }
        self._investigation_cache = result
        return result

    def proposal_analysis(self, cell_id: str, proposal_number: int) -> dict[str, Any]:
        if not 1 <= proposal_number <= matched_search.PROPOSAL_BUDGET:
            raise KeyError(proposal_number)
        proposal = self.proposals(cell_id)[proposal_number - 1]
        identity = self._cell_by_id[cell_id]
        method, seed, selection_order = identity
        cell = matched_coordinator.CellConfig(method, "natural", seed, selection_order)
        directory = matched_campaign.cell_output_dir(self.paths.campaign, cell)
        record = _json_object(
            directory / "proposals" / f"proposal-{proposal_number - 1:04d}.json"
        )
        gate = self._decisive_gate(proposal)
        labels = {
            "mutation_geometry": "the bounded mutation geometry was rejected",
            "scenario_validity": "the mutated scenario failed the validity contract",
            "pipeline_reproducibility": "the deterministic pipeline contract was not met",
            "empirical_support": "the mutation fell outside empirical support",
            "reference_controller": "the reference planner did not succeed",
            "tested_controller_failure": "the tested planner remained successful",
            "finding_contract": "the complete finding contract was not met",
            "qualifying_finding": "all finding gates passed",
        }
        support = proposal["empirical_support_probability"]
        criticality = float(proposal["objectives"][0])
        minimality = float(proposal["objectives"][1])
        parameters = proposal["mutation_parameters"]
        onset = float(parameters["braking_onset_offset_s"])
        speed = float(parameters["speed_multiplier"])
        replay_run_id = self._proposal_run_by_identity.get(
            (method, seed, selection_order, proposal_number)
        )
        return {
            "evidence_mode": "real_local_redacted",
            "analysis_mode": "deterministic_proposal_specific",
            "cell_id": cell_id,
            "proposal_number": proposal_number,
            "decision": (
                "qualified"
                if proposal["policy_specific_avoidable_failure"] is True
                else "not_qualified"
            ),
            "decisive_gate": gate,
            "explanation": (
                f"Proposal {proposal_number} did not qualify because {labels[gate]}."
                if gate != "qualifying_finding"
                else f"Proposal {proposal_number} satisfied every frozen finding gate."
            ),
            "facts": [
                {"label": "method", "value": method},
                {
                    "label": "case",
                    "value": f"scenario {selection_order}, seed {seed}",
                },
                {
                    "label": "scenario change",
                    "value": f"braking onset {onset:+.1f} s, lead speed {speed:.2f}x",
                },
                {
                    "label": "safety result",
                    "value": (
                        f"{self._proximity_label(criticality)} "
                        f"(derived from minimum signed separation; criticality {criticality:.4f})"
                    ),
                },
                {
                    "label": "change size",
                    "value": (
                        f"{self._change_size_label(minimality)} "
                        f"(derived from normalized edit distance; minimality {minimality:.4f})"
                    ),
                },
                {
                    "label": "recorded precedent",
                    "value": (
                        "not evaluated"
                        if support is None
                        else (
                            "seen in recorded behavior"
                            if proposal["support_passes"] is True
                            else "outside recorded behavior"
                        )
                        + f" (probability {support:.4f}; pass threshold 0.05)"
                    ),
                },
            ],
            "record_sha256": record["record_sha256"],
            "trajectory_available": replay_run_id is not None,
            "replay_run_id": replay_run_id,
        }

    def runs(self) -> list[dict[str, Any]]:
        collection = self._require(self.collection)
        result = [
            {
                "run_id": self._require(self._run_id),
                "label": "Private local Stage 0 controller comparison",
                "evidence_mode": "real_local_redacted",
                "collection_status": collection["collection_status"],
                "record_count": len(collection["records"]),
                "policy_specific_avoidable_failure": collection["comparison_finding"][
                    "policy_specific_avoidable_failure"
                ],
            }
        ]
        for run_id, (manifest, replay) in sorted(self._proposal_replays.items()):
            identity = manifest["identity"]
            result.append(
                {
                    "run_id": run_id,
                    "label": (
                        f"Exact campaign replay · {identity['method']} · "
                        f"S{identity['selection_order']} · seed {identity['seed']} · "
                        f"proposal {identity['proposal_number']}"
                    ),
                    "evidence_mode": "real_local_redacted",
                    "collection_status": replay["collection_status"],
                    "record_count": len(replay["records"]),
                    "policy_specific_avoidable_failure": replay[
                        "comparison_finding"
                    ].get("policy_specific_avoidable_failure", False),
                }
            )
        return result

    def run(self, run_id: str) -> dict[str, Any]:
        if run_id == self._run_id:
            collection = self._require(self.collection)
            scenario_label = "Private local WOMD comparison"
            hypothesis_id = "stage-0-counterfactual"
            hypothesis_label = "Validated Stage 0 counterfactual"
        else:
            replay = self._proposal_replays.get(run_id)
            if replay is None:
                raise KeyError(run_id)
            manifest, collection = replay
            identity = manifest["identity"]
            scenario_label = (
                f"Campaign replay · {identity['method']} · "
                f"S{identity['selection_order']} · seed {identity['seed']}"
            )
            hypothesis_id = "proposal-linked-counterfactual"
            hypothesis_label = f"Exact retained proposal {identity['proposal_number']}"
        return self.project_run(
            collection, run_id, scenario_label, hypothesis_id, hypothesis_label
        )

    def project_run(
        self,
        collection: dict[str, Any],
        run_id: str,
        scenario_label: str,
        hypothesis_id: str,
        hypothesis_label: str,
    ) -> dict[str, Any]:
        """Project an already validated collection without exposing source identifiers."""
        records = {
            (record["variant"], record["controller_role"]): record
            for record in collection["records"]
        }
        counterfactual_tested = records[("counterfactual", "tested")]
        counterfactual_reference = records[("counterfactual", "reference")]
        original_tested = records[("original", "tested")]
        scene = collection["scene_context"]
        lead = scene["actors"]["mutation_target"]["counterfactual"]
        metrics = self._timeline_metrics(
            counterfactual_tested["trajectory"], lead, scene["actors"]["sdc"]
        )
        mutation = counterfactual_tested["mutation"]
        onset = float(mutation["parameters"].get("braking_onset_offset_s", 0.0))
        speed = self._first_valid_speed(lead)
        checks = [
            "rollout_collection_schema",
            "content_identity",
            "aligned_timeline",
            "deterministic_replay",
        ]
        return {
            "schema_version": "planmargin.local-evidence.v1",
            "run_id": run_id,
            "scenario_label": scenario_label,
            "evidence_mode": "real_local_redacted",
            "synthetic": False,
            "step_seconds": speed_mutation.TIME_INTERVAL_S,
            "road_centerlines": [
                [
                    {"x": float(x), "y": float(y)}
                    for x, y in zip(feature["x_m"], feature["y_m"], strict=True)
                ]
                for feature in scene["roadgraph_features"]
                if len(feature["x_m"]) >= 2
            ],
            "mutation_target": {
                "original": self._points(
                    scene["actors"]["mutation_target"]["original"]
                ),
                "counterfactual": self._points(lead),
            },
            "hypothesis": {
                "id": hypothesis_id,
                "label": hypothesis_label,
                "mutation_type": mutation["mutation_type"],
                "mutation_parameters": mutation["parameters"],
                "onset_seconds": onset,
                "target_initial_speed_meters_per_second": speed,
                "supported": bool(mutation["accepted"]),
                "deterministic": all(
                    record["reproducibility"]["outputs_identical"]
                    for record in records.values()
                ),
                "validation_checks": checks,
                "controller_outcome": {
                    "tested": self._outcome(counterfactual_tested),
                    "reference": self._outcome(counterfactual_reference),
                },
                "trajectories": {
                    "tested": self._points(counterfactual_tested["trajectory"]),
                    "reference": self._points(counterfactual_reference["trajectory"]),
                    "recorded": self._points(original_tested["trajectory"]),
                },
                "metrics": metrics,
            },
            "privacy": {
                "scenario_identifier_exposed": False,
                "source_shard_exposed": False,
                "record_index_exposed": False,
                "raw_provenance_exposed": False,
            },
        }

    def gaussian_field(self) -> tuple[dict[str, Any], Path]:
        """Verify and project the ignored local Gaussian feasibility artifact."""
        directory = (self.paths.root / DEFAULT_GAUSSIAN).resolve()
        _confine_artifact(directory, self.paths.root)
        manifest_path = directory / "manifest.json"
        field_path = directory / "field.ply"
        for path in (manifest_path, field_path):
            if path.is_symlink() or not path.is_file():
                raise ValueError("Gaussian evidence must be regular local files")
            _confine_artifact(path.resolve(), self.paths.root)
        manifest = _json_object(manifest_path)
        if manifest.get("record_type") != "planmargin.lidar_gaussian_field_manifest":
            raise ValueError("Gaussian manifest record type is invalid")
        if manifest.get("schema_version") != "1.0.0":
            raise ValueError("Gaussian manifest schema version is invalid")
        random_search._validate_seal(manifest, "manifest_sha256", path=manifest_path)
        observed = manifest.get("observed")
        privacy = manifest.get("privacy")
        gates = manifest.get("gates")
        if not isinstance(observed, dict) or not isinstance(privacy, dict):
            raise ValueError("Gaussian manifest is incomplete")
        if not isinstance(gates, dict) or set(gates) != {
            "authorized_exact_input",
            "determinism",
            "scale",
            "local_compute",
            "geometric_quality",
            "trajectory_linkage",
        }:
            raise ValueError("Gaussian gate allowlist mismatch")
        if privacy != {
            "contains_scenario_id": False,
            "contains_source_uri": False,
            "contains_raw_points": False,
            "unrestricted_export": False,
        }:
            raise ValueError("Gaussian privacy boundary is invalid")
        if field_path.stat().st_size != observed.get("field_bytes"):
            raise ValueError("Gaussian field size does not match its manifest")
        if random_search._file_sha256(field_path) != manifest.get("field_sha256"):
            raise ValueError("Gaussian field hash does not match its manifest")
        geometric = observed.get("geometric_quality")
        if not isinstance(geometric, dict):
            raise ValueError("Gaussian geometry evidence is missing")
        summary = {
            "schema_version": "1.0.0",
            "evidence_mode": "real_local_redacted",
            "decision": manifest["decision"],
            "representation": manifest["representation"],
            "primitive_count": observed["primitive_count"],
            "field_bytes": observed["field_bytes"],
            "runtime_seconds": observed["runtime_seconds"],
            "trajectory_linkage_fraction": observed["trajectory_linkage_fraction"],
            "trajectory_linkage_gate": GAUSSIAN_LINKAGE_GATE,
            "geometry": {
                "median_nearest_mean_distance_m": geometric[
                    "median_nearest_mean_distance_m"
                ],
                "p90_nearest_mean_distance_m": geometric["p90_nearest_mean_distance_m"],
                "coverage_within_0_50_m": geometric["coverage_within_0_50_m"],
            },
            "gates": gates,
            "claim_boundary": manifest["claim_boundary"],
            "unrestricted_export": False,
        }
        return summary, field_path

    def sensor_scene(self) -> tuple[dict[str, Any], dict[str, Any]]:
        """Validate and project the ignored, same-frame local sensor bundle."""
        manifest_path = self.paths.root / DEFAULT_SENSOR_SCENE / "manifest.json"
        if manifest_path.is_symlink() or not manifest_path.is_file():
            raise FileNotFoundError("Prepared local sensor scene is unavailable")
        manifest = _json_object(manifest_path)
        expected = {
            "record_type": "planmargin.sensor_scene_manifest",
            "schema_version": "1.0.0",
            "source": "Waymo Open Dataset v2 Perception",
            "camera_name": "FRONT",
        }
        if any(manifest.get(key) != value for key, value in expected.items()):
            raise ValueError("Sensor scene manifest contract is invalid")
        frames = manifest.get("frames")
        annotations = manifest.get("annotations")
        reconstruction = manifest.get("reconstruction")
        reconstruction_reference = manifest.get("reconstruction_reference")
        reconstruction_context = manifest.get("reconstruction_context")
        lidar = manifest.get("lidar")
        trajectory = manifest.get("trajectory")
        if (
            not isinstance(frames, list)
            or not frames
            or not isinstance(annotations, dict)
            or not isinstance(reconstruction, dict)
            or not isinstance(lidar, dict)
        ):
            raise ValueError("Sensor scene manifest is incomplete")
        if manifest.get("frame_count") != len(frames):
            raise ValueError("Sensor scene frame count does not match its manifest")
        for index, frame in enumerate(frames):
            if not isinstance(frame, dict) or frame.get("index") != index:
                raise ValueError("Sensor scene frame ordering is invalid")
        annotations_path = (self.paths.root / annotations.get("file", "")).resolve()
        if (
            not annotations_path.is_relative_to(self.paths.root)
            or annotations_path.is_symlink()
            or not annotations_path.is_file()
            or annotations_path.stat().st_size != annotations.get("bytes")
            or random_search._file_sha256(annotations_path) != annotations.get("sha256")
            or annotations.get("frame_count") != len(frames)
        ):
            raise ValueError("Sensor frame annotations failed local validation")
        assets = [reconstruction, lidar]
        if reconstruction_reference is not None:
            if not isinstance(reconstruction_reference, dict):
                raise ValueError("Reference reconstruction is invalid")
            assets.append(reconstruction_reference)
        if reconstruction_context is not None:
            if not isinstance(reconstruction_context, dict):
                raise ValueError("Context reconstruction is invalid")
            assets.append(reconstruction_context)
        for asset in assets:
            relative = asset.get("file")
            if not isinstance(relative, str):
                raise ValueError("Sensor scene asset path is invalid")
            path = (self.paths.root / relative).resolve()
            if (
                not path.is_relative_to(self.paths.root)
                or path.is_symlink()
                or not path.is_file()
                or path.stat().st_size != asset.get("bytes")
            ):
                raise ValueError("Sensor scene asset failed local validation")
        if trajectory is not None:
            if not isinstance(trajectory, dict):
                raise ValueError("Sensor trajectory manifest is invalid")
            trajectory_path = (self.paths.root / trajectory.get("file", "")).resolve()
            if (
                not trajectory_path.is_relative_to(self.paths.root)
                or trajectory_path.is_symlink()
                or not trajectory_path.is_file()
                or trajectory_path.stat().st_size != trajectory.get("bytes")
                or random_search._file_sha256(trajectory_path)
                != trajectory.get("sha256")
            ):
                raise ValueError("Sensor trajectory failed local validation")
        summary = {
            "schema_version": "1.0.0",
            "evidence_mode": "real_local_sensor",
            "source": manifest["source"],
            "segment_id": manifest["segment_id"],
            "camera_name": manifest["camera_name"],
            "frame_count": manifest["frame_count"],
            "frame_rate_hz": manifest["frame_rate_hz"],
            "annotations": {
                key: annotations[key]
                for key in ("representation", "frame_count", "box_count", "bytes")
            },
            "reconstruction": {
                key: reconstruction[key]
                for key in (
                    "representation",
                    "source_frame_index",
                    "primitive_count",
                    "bytes",
                )
            },
            "lidar": {
                key: lidar[key]
                for key in (
                    "representation",
                    "source_frame_index",
                    "primitive_count",
                    "bytes",
                )
            },
        }
        if reconstruction_reference is not None:
            summary["reconstruction_reference"] = {
                key: reconstruction_reference[key]
                for key in (
                    "representation",
                    "source_frame_index",
                    "primitive_count",
                    "bytes",
                )
            }
        if reconstruction_context is not None:
            summary["reconstruction_context"] = {
                key: reconstruction_context[key]
                for key in (
                    "representation",
                    "source_frame_index",
                    "primitive_count",
                    "bytes",
                )
            }
        if trajectory is not None:
            summary["trajectory"] = {
                key: trajectory[key]
                for key in (
                    "representation",
                    "source_frame_index",
                    "bytes",
                    "future_steps",
                    "step_seconds",
                    "model_status",
                )
            }
        return summary, manifest

    def sensor_frame(self, frame_index: int) -> Path:
        """Return one validated FRONT camera frame from the prepared bundle."""
        _, manifest = self.sensor_scene()
        frames = manifest["frames"]
        if frame_index < 0 or frame_index >= len(frames):
            raise IndexError(frame_index)
        frame = frames[frame_index]
        directory = (self.paths.root / manifest["frames_directory"]).resolve()
        path = (directory / frame["file"]).resolve()
        if (
            not path.is_relative_to(directory)
            or path.is_symlink()
            or not path.is_file()
            or path.stat().st_size != frame["bytes"]
            or random_search._file_sha256(path) != frame["sha256"]
        ):
            raise ValueError("Sensor frame failed local validation")
        return path

    def sensor_asset(
        self,
        name: Literal[
            "reconstruction",
            "reconstruction_reference",
            "reconstruction_context",
            "lidar",
        ],
    ) -> Path:
        """Return one validated binary sensor representation."""
        _, manifest = self.sensor_scene()
        asset = manifest[name]
        path = (self.paths.root / asset["file"]).resolve(strict=True)
        if random_search._file_sha256(path) != asset["sha256"]:
            raise ValueError("Sensor asset failed integrity validation")
        return path

    def sensor_annotations(self) -> Path:
        """Return the validated native per-frame FRONT camera boxes."""
        _, manifest = self.sensor_scene()
        annotation = manifest["annotations"]
        return (self.paths.root / annotation["file"]).resolve(strict=True)

    def sensor_trajectory(self) -> Path:
        """Return the calibrated recorded/model trajectory overlay."""
        _, manifest = self.sensor_scene()
        trajectory = manifest.get("trajectory")
        if not isinstance(trajectory, dict):
            raise FileNotFoundError("Sensor trajectory is unavailable")
        return (self.paths.root / trajectory["file"]).resolve(strict=True)

    @staticmethod
    def _require(value: Any) -> Any:
        if value is None:
            raise RuntimeError("Evidence repository has not been opened")
        return value

    @staticmethod
    def _points(track: dict[str, Any]) -> list[dict[str, float]]:
        return [
            {"x": float(x), "y": float(y)}
            for x, y, valid in zip(
                track["x_m"], track["y_m"], track["valid"], strict=True
            )
            if valid
        ]

    @staticmethod
    def _outcome(record: dict[str, Any]) -> str:
        return "succeeds" if record["outcome"]["success"] else "fails"

    @staticmethod
    def _first_valid_speed(track: dict[str, Any]) -> float:
        x = track["x_m"]
        y = track["y_m"]
        valid = track["valid"]
        for index in range(1, len(x)):
            if valid[index - 1] and valid[index]:
                distance = math.hypot(x[index] - x[index - 1], y[index] - y[index - 1])
                return round(distance / speed_mutation.TIME_INTERVAL_S, 6)
        raise ValueError("Mutation target has no adjacent valid states")

    @staticmethod
    def _timeline_metrics(
        sdc: dict[str, Any], lead: dict[str, Any], sdc_shape: dict[str, Any]
    ) -> list[dict[str, float | None]]:
        count = len(sdc["x_m"])
        if len(lead["x_m"]) != count:
            raise ValueError("SDC and mutation-target timelines are not aligned")
        result: list[dict[str, float | None]] = []
        lead_velocity = EvidenceRepository._derived_velocity(lead)
        for index in range(count):
            if not sdc["valid"][index] or not lead["valid"][index]:
                raise ValueError("Debugger evidence contains an invalid timeline state")
            first = interaction_metrics.oriented_box_corners(
                x_m=float(sdc["x_m"][index]),
                y_m=float(sdc["y_m"][index]),
                yaw_rad=float(sdc["yaw_rad"][index]),
                length_m=float(sdc_shape["length_m"]),
                width_m=float(sdc_shape["width_m"]),
            )
            second = interaction_metrics.oriented_box_corners(
                x_m=float(lead["x_m"][index]),
                y_m=float(lead["y_m"][index]),
                yaw_rad=float(lead["yaw_rad"][index]),
                length_m=float(lead["length_m"][index]),
                width_m=float(lead["width_m"][index]),
            )
            ttc = interaction_metrics.longitudinal_ttc_s(
                sdc_x_m=float(sdc["x_m"][index]),
                sdc_y_m=float(sdc["y_m"][index]),
                sdc_yaw_rad=float(sdc["yaw_rad"][index]),
                sdc_vel_x_mps=float(sdc["vel_x_mps"][index]),
                sdc_vel_y_mps=float(sdc["vel_y_mps"][index]),
                sdc_length_m=float(sdc_shape["length_m"]),
                lead_x_m=float(lead["x_m"][index]),
                lead_y_m=float(lead["y_m"][index]),
                lead_vel_x_mps=lead_velocity[index][0],
                lead_vel_y_mps=lead_velocity[index][1],
                lead_length_m=float(lead["length_m"][index]),
            )
            result.append(
                {
                    "time_seconds": round(index * speed_mutation.TIME_INTERVAL_S, 6),
                    "signed_separation_meters": round(
                        interaction_metrics.signed_oriented_box_separation(
                            first, second
                        ),
                        6,
                    ),
                    "longitudinal_ttc_seconds": (
                        round(ttc, 6) if ttc is not None else None
                    ),
                }
            )
        return result

    @staticmethod
    def _derived_velocity(track: dict[str, Any]) -> list[tuple[float, float]]:
        result = []
        final = len(track["x_m"]) - 1
        for index in range(final + 1):
            left = max(0, index - 1)
            right = min(final, index + 1)
            elapsed = (right - left) * speed_mutation.TIME_INTERVAL_S
            result.append(
                (
                    float(track["x_m"][right] - track["x_m"][left]) / elapsed,
                    float(track["y_m"][right] - track["y_m"][left]) / elapsed,
                )
            )
        return result


def create_app(
    *,
    root: Path,
    token: str,
    origins: Sequence[str] = DEFAULT_ORIGINS,
    assistant_provider: Literal["offline", "gemini"] = "offline",
    confirm_gemini_free_tier: bool = False,
    gemini_model: str = evidence_assistant.DEFAULT_MODEL,
    planning_only: bool = False,
) -> FastAPI:
    """Create an authenticated app without performing import-time I/O."""
    if len(token) < 16:
        raise ValueError("Local API token must contain at least 16 characters")
    paths = EvidencePaths.from_root(root)
    repository = EvidenceRepository(paths)
    jobs = experiment_jobs.ExperimentJobs(root)
    if assistant_provider == "gemini":
        explainer: evidence_assistant.ExplanationProvider = (
            evidence_assistant.GeminiProvider(
                api_key=os.environ.get("GEMINI_API_KEY", ""),
                model=gemini_model,
                confirmed_free_tier=confirm_gemini_free_tier,
            )
        )
        assistant_tools: evidence_assistant.EvidenceTools = (
            evidence_assistant.PublicEvidenceTools()
        )
        assistant_source: Literal["real_local_redacted", "public_aggregate"] = (
            "public_aggregate"
        )
    else:
        explainer = evidence_assistant.OfflineProvider()
        assistant_tools = (
            evidence_assistant.PublicEvidenceTools()
            if planning_only
            else evidence_assistant.LocalEvidenceTools(repository)
        )
        assistant_source = (
            "public_aggregate" if planning_only else "real_local_redacted"
        )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if not planning_only:
            repository.open()
        jobs.open()
        try:
            yield
        finally:
            jobs.close()

    app = FastAPI(
        title="PlanMargin local evidence API",
        version=API_VERSION,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.repository = repository
    app.state.experiments = jobs
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["127.0.0.1", "localhost", "testserver"],
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(origins),
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["X-PlanMargin-Token", "Content-Type"],
    )

    @app.middleware("http")
    async def privacy_headers(request: Request, call_next: Any) -> Any:
        if request.url.query:
            response = JSONResponse(
                status_code=400,
                content={"detail": "Query parameters are not accepted"},
            )
        else:
            response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    token_header = APIKeyHeader(name="X-PlanMargin-Token", auto_error=False)

    def valid_token(supplied: str | None) -> bool:
        return supplied is not None and secrets.compare_digest(supplied, token)

    def authorize(
        request: Request,
        supplied: str | None = Security(token_header),
    ) -> None:
        if not valid_token(supplied) and not valid_token(
            request.cookies.get(SESSION_COOKIE_NAME)
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="A valid local evidence token is required",
            )
        if planning_only and request.url.path.split("/")[3] in {
            "campaign",
            "test-operations",
            "methods",
            "hypotheses",
            "cells",
            "investigation",
            "runs",
        }:
            raise HTTPException(
                status_code=503,
                detail="The recorded campaign is not loaded in planning-only mode. Local experiments remain available.",
            )

    auth = Depends(authorize)

    def authorize_write(
        request: Request, supplied: str | None = Security(token_header)
    ) -> None:
        authorize(request, supplied)
        origin = request.headers.get("origin")
        if origin not in origins and not (origin is None and valid_token(supplied)):
            raise HTTPException(
                status_code=403,
                detail="Experiment writes require a trusted local origin",
            )

    from planmargin.experiment_api import experiment_router

    app.include_router(
        experiment_router(jobs, repository.project_run, authorize, authorize_write)
    )

    @app.post("/api/v1/session", status_code=status.HTTP_204_NO_CONTENT)
    def create_session(
        supplied: str | None = Security(token_header),
    ) -> Response:
        if not valid_token(supplied):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="A valid local evidence token is required",
            )
        response = Response(status_code=status.HTTP_204_NO_CONTENT)
        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=token,
            httponly=True,
            secure=False,
            samesite="strict",
            path="/api/v1",
        )
        return response

    @app.post("/api/v1/session/logout", status_code=status.HTTP_204_NO_CONTENT)
    def delete_session() -> Response:
        response = Response(status_code=status.HTTP_204_NO_CONTENT)
        response.delete_cookie(
            key=SESSION_COOKIE_NAME,
            httponly=True,
            secure=False,
            samesite="strict",
            path="/api/v1",
        )
        return response

    @app.get("/api/v1/health", dependencies=[auth], response_model=HealthEvidence)
    def health() -> dict[str, Any]:
        return {
            "status": "ready",
            "evidence_mode": "real_local_redacted",
            "campaign_ready": not planning_only,
        }

    @app.get("/api/v1/campaign", dependencies=[auth], response_model=CampaignEvidence)
    def campaign() -> dict[str, Any]:
        return repository.campaign()

    @app.get(
        "/api/v1/test-operations",
        dependencies=[auth],
        response_model=TestOperationsEvidence,
    )
    def test_operations_report() -> dict[str, Any]:
        return repository.test_operations()

    @app.get(
        "/api/v1/methods",
        dependencies=[auth],
        response_model=list[MethodEvidence],
    )
    def methods() -> list[dict[str, Any]]:
        return repository.methods()

    @app.get(
        "/api/v1/hypotheses",
        dependencies=[auth],
        response_model=list[HypothesisEvidence],
    )
    def hypotheses() -> list[dict[str, Any]]:
        return repository.hypotheses()

    @app.get("/api/v1/cells", dependencies=[auth], response_model=list[CellEvidence])
    def cells() -> list[dict[str, Any]]:
        return repository.cells()

    @app.get(
        "/api/v1/cells/{cell_id}/proposals",
        dependencies=[auth],
        response_model=list[ProposalEvidence],
    )
    def proposals(cell_id: str) -> list[dict[str, Any]]:
        try:
            return repository.proposals(cell_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Cell not found") from error

    @app.get(
        "/api/v1/investigation",
        dependencies=[auth],
        response_model=CampaignInvestigationEvidence,
    )
    def investigation() -> dict[str, Any]:
        return repository.investigation()

    @app.get(
        "/api/v1/cells/{cell_id}/proposals/{proposal_number}/analysis",
        dependencies=[auth],
        response_model=ProposalAnalysisEvidence,
    )
    def proposal_analysis(cell_id: str, proposal_number: int) -> dict[str, Any]:
        try:
            return repository.proposal_analysis(cell_id, proposal_number)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Proposal not found") from error

    @app.get(
        "/api/v1/runs",
        dependencies=[auth],
        response_model=list[RunSummaryEvidence],
    )
    def runs() -> list[dict[str, Any]]:
        return repository.runs()

    @app.get("/api/v1/runs/{run_id}", dependencies=[auth], response_model=RunEvidence)
    def run(run_id: str) -> dict[str, Any]:
        try:
            return repository.run(run_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Run not found") from error

    @app.get(
        "/api/v1/assistant/status",
        dependencies=[auth],
        response_model=AssistantStatusEvidence,
    )
    def assistant_status() -> dict[str, Any]:
        return {
            "provider_id": explainer.provider_id,
            "model": getattr(explainer, "_model", None),
            "source_mode": assistant_source,
            "gemini_configured": assistant_provider == "gemini",
            "explanation_only": True,
        }

    @app.get(
        "/api/v1/assistant/questions",
        dependencies=[auth],
        response_model=list[AssistantQuestionEvidence],
    )
    def assistant_questions() -> list[dict[str, str]]:
        return [
            {
                "query_id": query_id,
                "label": evidence_assistant.QUERY_LABELS[query_id],
                "question": question,
            }
            for query_id, question in ASSISTANT_QUESTIONS.items()
        ]

    @app.get(
        "/api/v1/assistant/{query_id}",
        dependencies=[auth],
        response_model=AssistantResponseEvidence,
    )
    def assistant_answer(query_id: str) -> dict[str, Any]:
        question = ASSISTANT_QUESTIONS.get(query_id)
        if question is None:
            raise HTTPException(status_code=404, detail="Assistant question not found")
        try:
            response = evidence_assistant.answer_question(
                question, tools=assistant_tools, provider=explainer
            )
        except (RuntimeError, ValueError):
            if assistant_provider != "gemini":
                raise
            response = evidence_assistant.answer_question(
                question,
                tools=assistant_tools,
                provider=evidence_assistant.OfflineProvider(),
            )
        return {key: value for key, value in response.items() if key != "$schema"}

    @app.get(
        "/api/v1/gaussian-field",
        dependencies=[auth],
        response_model=GaussianFieldEvidence,
    )
    def gaussian_summary() -> dict[str, Any]:
        summary, _ = repository.gaussian_field()
        return summary

    @app.get(
        "/api/v1/gaussian-field/field.ply",
        dependencies=[auth],
        response_class=FileResponse,
        responses={200: {"content": {"application/octet-stream": {}}}},
    )
    def gaussian_field_file() -> FileResponse:
        _, path = repository.gaussian_field()
        return FileResponse(
            path,
            media_type="application/octet-stream",
            filename="planmargin-local-field.ply",
            content_disposition_type="inline",
        )

    @app.get(
        "/api/v1/sensor-scene",
        dependencies=[auth],
        response_model=SensorSceneEvidence,
    )
    def sensor_scene() -> dict[str, Any]:
        try:
            summary, _ = repository.sensor_scene()
            return summary
        except FileNotFoundError as error:
            raise HTTPException(
                status_code=404, detail="Sensor scene not prepared"
            ) from error

    @app.get(
        "/api/v1/sensor-scene/front/annotations.json",
        dependencies=[auth],
        response_class=FileResponse,
        responses={200: {"content": {"application/json": {}}}},
    )
    def sensor_annotations() -> FileResponse:
        try:
            path = repository.sensor_annotations()
        except FileNotFoundError as error:
            raise HTTPException(
                status_code=404, detail="Sensor annotations not found"
            ) from error
        return FileResponse(
            path, media_type="application/json", content_disposition_type="inline"
        )

    @app.get(
        "/api/v1/sensor-scene/trajectory.json",
        dependencies=[auth],
        response_class=FileResponse,
        responses={200: {"content": {"application/json": {}}}},
    )
    def sensor_trajectory() -> FileResponse:
        try:
            path = repository.sensor_trajectory()
        except FileNotFoundError as error:
            raise HTTPException(
                status_code=404, detail="Sensor trajectory not found"
            ) from error
        return FileResponse(
            path, media_type="application/json", content_disposition_type="inline"
        )

    @app.get(
        "/api/v1/sensor-scene/front/{frame_index}.jpg",
        dependencies=[auth],
        response_class=FileResponse,
        responses={200: {"content": {"image/jpeg": {}}}},
    )
    def sensor_frame(frame_index: int) -> FileResponse:
        try:
            path = repository.sensor_frame(frame_index)
        except (FileNotFoundError, IndexError) as error:
            raise HTTPException(
                status_code=404, detail="Sensor frame not found"
            ) from error
        return FileResponse(
            path, media_type="image/jpeg", content_disposition_type="inline"
        )

    @app.get(
        "/api/v1/sensor-scene/{asset}.ply",
        dependencies=[auth],
        response_class=FileResponse,
        responses={200: {"content": {"application/octet-stream": {}}}},
    )
    def sensor_asset(
        asset: Literal[
            "reconstruction",
            "reconstruction_reference",
            "reconstruction_context",
            "lidar",
        ],
    ) -> FileResponse:
        try:
            path = repository.sensor_asset(asset)
        except FileNotFoundError as error:
            raise HTTPException(
                status_code=404, detail="Sensor asset not found"
            ) from error
        return FileResponse(
            path,
            media_type="application/octet-stream",
            filename=f"planmargin-{asset}.ply",
            content_disposition_type="inline",
        )

    @app.get(
        "/api/v1/openapi.json",
        dependencies=[auth],
        include_in_schema=False,
    )
    def openapi_contract() -> dict[str, Any]:
        return app.openapi()

    @app.exception_handler(ValueError)
    async def invalid_evidence(_: Request, error: ValueError) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={"detail": "Local evidence failed validation"},
        )

    return app


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--assistant-provider", choices=("offline", "gemini"), default="offline"
    )
    parser.add_argument("--confirm-gemini-free-tier", action="store_true")
    parser.add_argument("--gemini-model", default=evidence_assistant.DEFAULT_MODEL)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if not 1024 <= args.port <= 65535:
        raise SystemExit("--port must be between 1024 and 65535")
    token = os.environ.get("PLANMARGIN_API_TOKEN") or secrets.token_urlsafe(32)
    app = create_app(
        root=args.root,
        token=token,
        assistant_provider=args.assistant_provider,
        confirm_gemini_free_tier=args.confirm_gemini_free_tier,
        gemini_model=args.gemini_model,
    )
    print("PlanMargin local evidence API")
    print(f"URL: http://127.0.0.1:{args.port}")
    print(f"X-PlanMargin-Token: {token}")
    print(f"Evidence assistant: {args.assistant_provider}")
    print("Private evidence remains local; responses are not cached.")
    uvicorn.run(app, host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
