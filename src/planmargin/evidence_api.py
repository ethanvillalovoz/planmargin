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
from fastapi import Depends, FastAPI, HTTPException, Request, Security, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, ConfigDict
from starlette.middleware.trustedhost import TrustedHostMiddleware

from planmargin import analytics
from planmargin import evidence_assistant
from planmargin import interaction_metrics
from planmargin import matched_campaign
from planmargin import matched_coordinator
from planmargin import matched_search
from planmargin import random_search
from planmargin import rollout_record
from planmargin import speed_mutation

API_VERSION = "1.1.0"
DEFAULT_ANALYTICS = Path("artifacts/analytics/natural-development-v1")
DEFAULT_CAMPAIGN = Path("artifacts/search-comparison/natural-development-v1")
DEFAULT_ROLLOUTS = Path("artifacts/stage-0/rollout-records.json")
DEFAULT_GAUSSIAN = Path("artifacts/gaussian-field/feasibility")
DEFAULT_ORIGINS = ("http://127.0.0.1:4200", "http://localhost:4200")
MAX_JSON_BYTES = 128 * 1024 * 1024
GAUSSIAN_LINKAGE_GATE = 0.90
ASSISTANT_QUESTIONS = {
    "campaign_overview": "What happened in the development campaign?",
    "method_comparison": "How did Bayesian compare with random search?",
    "hypothesis_decisions": "What happened to H1, H2, and H3?",
    "claim_boundary": "What is the defensible claim and limitation?",
    "beam_pipeline": "What did the Beam feature pipeline process?",
}


class EvidenceModel(BaseModel):
    """Closed response object used to generate the authenticated OpenAPI contract."""

    model_config = ConfigDict(extra="forbid")


class HealthEvidence(EvidenceModel):
    status: Literal["ready"]
    evidence_mode: Literal["real_local_redacted"]


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


@dataclass(frozen=True)
class EvidencePaths:
    """Fixed artifact locations beneath one repository root."""

    root: Path
    analytics: Path
    campaign: Path
    rollouts: Path

    @classmethod
    def from_root(cls, root: Path) -> "EvidencePaths":
        resolved = root.resolve(strict=True)
        return cls(
            root=resolved,
            analytics=resolved / DEFAULT_ANALYTICS,
            campaign=resolved / DEFAULT_CAMPAIGN,
            rollouts=resolved / DEFAULT_ROLLOUTS,
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
            finding = record["finding"]
            support = record["support"]
            result.append(
                {
                    "proposal_number": index + 1,
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
                    "support_passes": (
                        support["passes"] if support is not None else None
                    ),
                    "objective_available": record["outcome"]["objective_available"],
                    "objectives": record["outcome"]["objectives"],
                    "constraints": record["outcome"]["constraints"],
                    "pipeline_reproducible": (
                        finding["pipeline_reproducible"]
                        if finding is not None
                        else None
                    ),
                    "policy_specific_avoidable_failure": (
                        finding["policy_specific_avoidable_failure"]
                        if finding is not None
                        else None
                    ),
                    "tested_mutated_failure": (
                        finding["tested_mutated_failure"]
                        if finding is not None
                        else None
                    ),
                    "reference_mutated_success": (
                        finding["reference_mutated_success"]
                        if finding is not None
                        else None
                    ),
                    "physical_rollouts": record["cost"]["total_physical_rollouts"],
                }
            )
        return result

    def runs(self) -> list[dict[str, Any]]:
        collection = self._require(self.collection)
        return [
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

    def run(self, run_id: str) -> dict[str, Any]:
        if run_id != self._run_id:
            raise KeyError(run_id)
        collection = self._require(self.collection)
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
            "scenario_label": "Private local WOMD comparison",
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
                "id": "stage-0-counterfactual",
                "label": "Validated Stage 0 counterfactual",
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
        random_search._validate_seal(
            manifest, "manifest_sha256", path=manifest_path
        )
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
            "trajectory_linkage_fraction": observed[
                "trajectory_linkage_fraction"
            ],
            "trajectory_linkage_gate": GAUSSIAN_LINKAGE_GATE,
            "geometry": {
                "median_nearest_mean_distance_m": geometric[
                    "median_nearest_mean_distance_m"
                ],
                "p90_nearest_mean_distance_m": geometric[
                    "p90_nearest_mean_distance_m"
                ],
                "coverage_within_0_50_m": geometric["coverage_within_0_50_m"],
            },
            "gates": gates,
            "claim_boundary": manifest["claim_boundary"],
            "unrestricted_export": False,
        }
        return summary, field_path

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
) -> FastAPI:
    """Create an authenticated app without performing import-time I/O."""
    if len(token) < 16:
        raise ValueError("Local API token must contain at least 16 characters")
    paths = EvidencePaths.from_root(root)
    repository = EvidenceRepository(paths)
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
        assistant_tools = evidence_assistant.LocalEvidenceTools(repository)
        assistant_source = "real_local_redacted"

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        repository.open()
        yield

    app = FastAPI(
        title="PlanMargin local evidence API",
        version=API_VERSION,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.repository = repository
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["127.0.0.1", "localhost", "testserver"],
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(origins),
        allow_credentials=False,
        allow_methods=["GET"],
        allow_headers=["X-PlanMargin-Token"],
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

    def authorize(supplied: str | None = Security(token_header)) -> None:
        if supplied is None or not secrets.compare_digest(supplied, token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="A valid local evidence token is required",
            )

    auth = Depends(authorize)

    @app.get("/api/v1/health", dependencies=[auth], response_model=HealthEvidence)
    def health() -> dict[str, str]:
        return {"status": "ready", "evidence_mode": "real_local_redacted"}

    @app.get("/api/v1/campaign", dependencies=[auth], response_model=CampaignEvidence)
    def campaign() -> dict[str, Any]:
        return repository.campaign()

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
        response = evidence_assistant.answer_question(
            question, tools=assistant_tools, provider=explainer
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
