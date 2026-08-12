"""Build verified private DuckDB and Parquet campaign analytics."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Sequence

import duckdb

from planmargin import matched_campaign
from planmargin import matched_search
from planmargin import random_search

SCHEMA_VERSION = "1.0.0"
SCHEMA_BASE_URI = (
    "https://raw.githubusercontent.com/ethanvillalovoz/planmargin/main/schemas"
)
MANIFEST_SCHEMA_URI = f"{SCHEMA_BASE_URI}/analytics-manifest-v1.schema.json"
MANIFEST_TYPE = "planmargin.analytics_manifest"
DEFAULT_CAMPAIGN_DIR = matched_campaign.DEFAULT_OUTPUT_DIR
DEFAULT_OUTPUT_DIR = Path("artifacts/analytics/natural-development-v1")
DATABASE_NAME = "planmargin.duckdb"

TABLE_NAMES = (
    "campaign",
    "methods",
    "hypotheses",
    "cells",
    "hypervolume_trace",
    "status_counts",
    "integrity_gates",
)

COST_FIELDS = (
    "core_mutation_attempts",
    "reference_controller_logical_evaluations",
    "reference_controller_physical_rollouts",
    "scenario_validation_logical_evaluations",
    "scenario_validation_physical_rollouts",
    "tested_controller_logical_evaluations",
    "tested_controller_physical_rollouts",
    "total_physical_rollouts",
    "waymax_rollout_steps",
)


def _validate_private_paths(campaign_dir: Path, output_dir: Path) -> None:
    root = Path.cwd().resolve()
    campaign_root = (root / "artifacts" / "search-comparison").resolve()
    analytics_root = (root / "artifacts" / "analytics").resolve()
    if not campaign_dir.resolve().is_relative_to(campaign_root):
        raise ValueError(
            "Campaign input is restricted; --campaign-dir must remain under "
            "artifacts/search-comparison/."
        )
    if not output_dir.resolve().is_relative_to(analytics_root):
        raise ValueError(
            "Analytics contain restricted cell aggregates; --output-dir must "
            "remain under artifacts/analytics/."
        )


def _load_validated_reports(
    campaign_dir: Path,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    matched_campaign._validate_existing_tree(campaign_dir)
    run_manifest = matched_campaign._load_sealed_record(
        campaign_dir / "run-manifest.json",
        record_type=matched_campaign.MANIFEST_TYPE,
        schema_uri=matched_campaign.MANIFEST_SCHEMA_URI,
        seal_field="manifest_sha256",
    )
    campaign_report = matched_campaign._load_sealed_record(
        campaign_dir / "report.json",
        record_type=matched_campaign.REPORT_TYPE,
        schema_uri=matched_campaign.REPORT_SCHEMA_URI,
        seal_field="report_sha256",
    )
    support_fingerprint = run_manifest["configuration"]["support"][
        "model_fingerprint"
    ]
    cell_reports = []
    for cell in matched_campaign.campaign_cells():
        path = matched_campaign.cell_output_dir(campaign_dir, cell) / "report.json"
        report = matched_campaign._load_json(path)
        matched_campaign._validate_cell_report(
            report,
            cell=cell,
            support_model_fingerprint=support_fingerprint,
        )
        cell_reports.append(report)
    expected = matched_campaign.build_report(
        run_manifest=run_manifest,
        cell_reports=cell_reports,
        invocation_seconds=float(campaign_report["final_invocation_seconds"]),
        process_peak_rss_bytes=campaign_report["process_peak_rss_bytes"],
    )
    if campaign_report != expected:
        raise ValueError("Campaign report does not reconstruct from cell reports")
    if campaign_report["decision"] != "campaign_complete":
        raise ValueError("Analytics require a valid completed campaign")
    return run_manifest, campaign_report, cell_reports


def _campaign_rows(report: dict[str, Any]) -> list[tuple[Any, ...]]:
    return [
        (
            report["campaign_id"],
            report["configuration_fingerprint"],
            report["support_model_fingerprint"],
            report["status"],
            report["decision"],
            report["report_sha256"],
            report["recorded_work_seconds"],
            report["final_invocation_seconds"],
            report["process_peak_rss_bytes"],
            report["cost_total"]["total_physical_rollouts"],
            report["cost_total"]["waymax_rollout_steps"],
        )
    ]


def _method_rows(report: dict[str, Any]) -> list[tuple[Any, ...]]:
    rows = []
    for method in matched_search.METHODS:
        metrics = report["metrics_by_method"][method]
        cost = report["cost_by_method"][method]
        rows.append(
            (
                method,
                metrics["cell_count"],
                metrics["proposal_count"],
                metrics["finding_cell_count"],
                metrics["qualifying_failure_count"],
                metrics["restricted_mean_proposals_to_first_finding"],
                metrics["restricted_mean_physical_rollouts_to_first_finding"],
                metrics["pipeline_valid_count"],
                metrics["support_and_pipeline_valid_count"],
                metrics["support_and_pipeline_valid_rate"],
                metrics["mean_final_feasible_hypervolume"],
                metrics["recorded_work_seconds"],
                *(cost[field] for field in COST_FIELDS),
            )
        )
    return rows


def _hypothesis_rows(report: dict[str, Any]) -> list[tuple[Any, ...]]:
    rows = []
    for name, result in report["hypotheses"].items():
        rows.append(
            (
                name,
                result["status"],
                result.get("paired_cell_count"),
                result.get("median_bayesian_minus_random_mutation_distance"),
                result.get("bayesian_minus_random_valid_rate"),
                result.get("noninferiority_margin"),
                result.get("bayesian_finding_count_at_least_random"),
                result.get("bayesian_lower_restricted_mean_proposals"),
                result.get("bayesian_lower_restricted_mean_physical_rollouts"),
            )
        )
    return rows


def _cell_rows(reports: Sequence[dict[str, Any]]) -> list[tuple[Any, ...]]:
    rows = []
    for report in reports:
        identity = report["identity"]
        metrics = report["metrics"]
        cost = report["cost"]["total"]
        rows.append(
            (
                identity["method"],
                identity["track"],
                identity["seed"],
                identity["selection_order"],
                report["report_sha256"],
                report["decision"],
                metrics["proposal_count"],
                metrics["accepted_proposal_count"],
                metrics["pipeline_valid_count"],
                metrics["support_and_pipeline_valid_count"],
                metrics["fully_feasible_count"],
                metrics["qualifying_failure_count"],
                metrics["first_qualifying_failure_proposal_count"],
                metrics[
                    "restricted_physical_rollouts_to_first_qualifying_failure"
                ],
                metrics["minimum_failure_mutation_distance"],
                metrics["pipeline_valid_rate"],
                metrics["support_and_pipeline_valid_rate"],
                metrics["duplicate_proposal_count"],
                metrics["final_feasible_hypervolume"],
                metrics["recorded_work_seconds"],
                metrics["final_invocation_seconds"],
                metrics["process_peak_rss_bytes"],
                *(cost[field] for field in COST_FIELDS),
            )
        )
    return rows


def _hypervolume_rows(reports: Sequence[dict[str, Any]]) -> list[tuple[Any, ...]]:
    return [
        (
            report["identity"]["method"],
            report["identity"]["seed"],
            report["identity"]["selection_order"],
            proposal_index + 1,
            value,
        )
        for report in reports
        for proposal_index, value in enumerate(
            report["metrics"]["feasible_hypervolume_by_proposal"]
        )
    ]


def _status_rows(reports: Sequence[dict[str, Any]]) -> list[tuple[Any, ...]]:
    return [
        (
            report["identity"]["method"],
            report["identity"]["seed"],
            report["identity"]["selection_order"],
            status,
            count,
        )
        for report in reports
        for status, count in sorted(report["metrics"]["status_counts"].items())
    ]


def _integrity_rows(
    campaign_report: dict[str, Any], cell_reports: Sequence[dict[str, Any]]
) -> list[tuple[Any, ...]]:
    rows = [
        ("campaign", None, None, None, gate, passed)
        for gate, passed in sorted(campaign_report["integrity_gates"].items())
    ]
    rows.extend(
        (
            "cell",
            report["identity"]["method"],
            report["identity"]["seed"],
            report["identity"]["selection_order"],
            gate,
            passed,
        )
        for report in cell_reports
        for gate, passed in sorted(report["integrity_gates"].items())
    )
    return rows


def _create_tables(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute(
        """
        CREATE TABLE campaign (
          campaign_id VARCHAR PRIMARY KEY,
          configuration_fingerprint VARCHAR NOT NULL,
          support_model_fingerprint VARCHAR NOT NULL,
          status VARCHAR NOT NULL,
          decision VARCHAR NOT NULL,
          report_sha256 VARCHAR NOT NULL,
          recorded_work_seconds DOUBLE NOT NULL,
          final_invocation_seconds DOUBLE NOT NULL,
          process_peak_rss_bytes BIGINT NOT NULL,
          total_physical_rollouts BIGINT NOT NULL,
          waymax_rollout_steps BIGINT NOT NULL
        );
        CREATE TABLE methods (
          method VARCHAR PRIMARY KEY,
          cell_count INTEGER NOT NULL,
          proposal_count INTEGER NOT NULL,
          finding_cell_count INTEGER NOT NULL,
          qualifying_failure_count INTEGER NOT NULL,
          restricted_mean_proposals_to_first_finding DOUBLE NOT NULL,
          restricted_mean_physical_rollouts_to_first_finding DOUBLE NOT NULL,
          pipeline_valid_count INTEGER NOT NULL,
          support_and_pipeline_valid_count INTEGER NOT NULL,
          support_and_pipeline_valid_rate DOUBLE NOT NULL,
          mean_final_feasible_hypervolume DOUBLE NOT NULL,
          recorded_work_seconds DOUBLE NOT NULL,
          core_mutation_attempts BIGINT NOT NULL,
          reference_controller_logical_evaluations BIGINT NOT NULL,
          reference_controller_physical_rollouts BIGINT NOT NULL,
          scenario_validation_logical_evaluations BIGINT NOT NULL,
          scenario_validation_physical_rollouts BIGINT NOT NULL,
          tested_controller_logical_evaluations BIGINT NOT NULL,
          tested_controller_physical_rollouts BIGINT NOT NULL,
          total_physical_rollouts BIGINT NOT NULL,
          waymax_rollout_steps BIGINT NOT NULL
        );
        CREATE TABLE hypotheses (
          hypothesis VARCHAR PRIMARY KEY,
          status VARCHAR NOT NULL,
          paired_cell_count INTEGER,
          median_bayesian_minus_random_mutation_distance DOUBLE,
          bayesian_minus_random_valid_rate DOUBLE,
          noninferiority_margin DOUBLE,
          bayesian_finding_count_at_least_random BOOLEAN,
          bayesian_lower_restricted_mean_proposals BOOLEAN,
          bayesian_lower_restricted_mean_physical_rollouts BOOLEAN
        );
        CREATE TABLE cells (
          method VARCHAR NOT NULL,
          track VARCHAR NOT NULL,
          seed INTEGER NOT NULL,
          selection_order INTEGER NOT NULL,
          report_sha256 VARCHAR NOT NULL,
          decision VARCHAR NOT NULL,
          proposal_count INTEGER NOT NULL,
          accepted_proposal_count INTEGER NOT NULL,
          pipeline_valid_count INTEGER NOT NULL,
          support_and_pipeline_valid_count INTEGER NOT NULL,
          fully_feasible_count INTEGER NOT NULL,
          qualifying_failure_count INTEGER NOT NULL,
          first_qualifying_failure_proposal_count INTEGER,
          restricted_physical_rollouts_to_first_finding BIGINT NOT NULL,
          minimum_failure_mutation_distance DOUBLE,
          pipeline_valid_rate DOUBLE NOT NULL,
          support_and_pipeline_valid_rate DOUBLE NOT NULL,
          duplicate_proposal_count INTEGER NOT NULL,
          final_feasible_hypervolume DOUBLE NOT NULL,
          recorded_work_seconds DOUBLE NOT NULL,
          final_invocation_seconds DOUBLE NOT NULL,
          process_peak_rss_bytes BIGINT NOT NULL,
          core_mutation_attempts BIGINT NOT NULL,
          reference_controller_logical_evaluations BIGINT NOT NULL,
          reference_controller_physical_rollouts BIGINT NOT NULL,
          scenario_validation_logical_evaluations BIGINT NOT NULL,
          scenario_validation_physical_rollouts BIGINT NOT NULL,
          tested_controller_logical_evaluations BIGINT NOT NULL,
          tested_controller_physical_rollouts BIGINT NOT NULL,
          total_physical_rollouts BIGINT NOT NULL,
          waymax_rollout_steps BIGINT NOT NULL,
          PRIMARY KEY (method, seed, selection_order)
        );
        CREATE TABLE hypervolume_trace (
          method VARCHAR NOT NULL,
          seed INTEGER NOT NULL,
          selection_order INTEGER NOT NULL,
          proposal_count INTEGER NOT NULL,
          feasible_hypervolume DOUBLE NOT NULL,
          PRIMARY KEY (method, seed, selection_order, proposal_count)
        );
        CREATE TABLE status_counts (
          method VARCHAR NOT NULL,
          seed INTEGER NOT NULL,
          selection_order INTEGER NOT NULL,
          attempt_status VARCHAR NOT NULL,
          attempt_count INTEGER NOT NULL,
          PRIMARY KEY (method, seed, selection_order, attempt_status)
        );
        CREATE TABLE integrity_gates (
          scope VARCHAR NOT NULL,
          method VARCHAR,
          seed INTEGER,
          selection_order INTEGER,
          gate_name VARCHAR NOT NULL,
          passed BOOLEAN NOT NULL
        );
        """
    )


def _insert_rows(
    connection: duckdb.DuckDBPyConnection,
    table: str,
    rows: Sequence[tuple[Any, ...]],
) -> None:
    if not rows:
        raise ValueError(f"Analytics table {table} cannot be empty")
    placeholders = ", ".join("?" for _ in rows[0])
    connection.executemany(f"INSERT INTO {table} VALUES ({placeholders})", rows)


def _round_six(value: float) -> float:
    return round(float(value), 6)


def _verify_sql(
    connection: duckdb.DuckDBPyConnection,
    campaign_report: dict[str, Any],
    cell_reports: Sequence[dict[str, Any]],
) -> dict[str, int]:
    row_counts = {
        table: int(connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0])
        for table in TABLE_NAMES
    }
    expected_counts = {
        "campaign": 1,
        "methods": len(matched_search.METHODS),
        "hypotheses": len(campaign_report["hypotheses"]),
        "cells": len(cell_reports),
        "hypervolume_trace": len(cell_reports) * matched_search.PROPOSAL_BUDGET,
        "status_counts": sum(
            len(report["metrics"]["status_counts"]) for report in cell_reports
        ),
        "integrity_gates": len(campaign_report["integrity_gates"])
        + sum(len(report["integrity_gates"]) for report in cell_reports),
    }
    if row_counts != expected_counts:
        raise ValueError("Analytics table row counts do not match source reports")
    if connection.execute(
        "SELECT count(*) FROM integrity_gates WHERE NOT passed"
    ).fetchone()[0]:
        raise ValueError("Analytics source contains a failed integrity gate")

    aggregates = connection.execute(
        """
        SELECT method,
               count(*) AS cell_count,
               sum(proposal_count) AS proposal_count,
               count(*) FILTER (WHERE qualifying_failure_count > 0)
                 AS finding_cell_count,
               sum(qualifying_failure_count) AS qualifying_failure_count,
               sum(pipeline_valid_count) AS pipeline_valid_count,
               sum(support_and_pipeline_valid_count)
                 AS support_and_pipeline_valid_count,
               round(sum(support_and_pipeline_valid_count)::DOUBLE /
                 sum(proposal_count), 6) AS valid_rate,
               round(avg(final_feasible_hypervolume), 6) AS mean_hypervolume,
               sum(total_physical_rollouts) AS total_physical_rollouts,
               sum(waymax_rollout_steps) AS waymax_rollout_steps
        FROM cells
        GROUP BY method
        ORDER BY method
        """
    ).fetchall()
    for row in aggregates:
        method = row[0]
        metrics = campaign_report["metrics_by_method"][method]
        cost = campaign_report["cost_by_method"][method]
        expected = (
            method,
            metrics["cell_count"],
            metrics["proposal_count"],
            metrics["finding_cell_count"],
            metrics["qualifying_failure_count"],
            metrics["pipeline_valid_count"],
            metrics["support_and_pipeline_valid_count"],
            _round_six(metrics["support_and_pipeline_valid_rate"]),
            _round_six(metrics["mean_final_feasible_hypervolume"]),
            cost["total_physical_rollouts"],
            cost["waymax_rollout_steps"],
        )
        actual = (*row[:7], _round_six(row[7]), _round_six(row[8]), *row[9:])
        if actual != expected:
            raise ValueError(f"SQL method aggregate mismatch for {method}")

    traces = connection.execute(
        """
        SELECT method, proposal_count, round(avg(feasible_hypervolume), 6)
        FROM hypervolume_trace
        GROUP BY method, proposal_count
        ORDER BY method, proposal_count
        """
    ).fetchall()
    expected_traces = {
        (method, index + 1): _round_six(value)
        for method in matched_search.METHODS
        for index, value in enumerate(
            campaign_report["metrics_by_method"][method][
                "mean_feasible_hypervolume_by_proposal"
            ]
        )
    }
    if {
        (method, proposal_count): _round_six(value)
        for method, proposal_count, value in traces
    } != expected_traces:
        raise ValueError("SQL hypervolume traces do not match campaign report")
    return row_counts


def _export_parquet(
    connection: duckdb.DuckDBPyConnection, output_dir: Path
) -> dict[str, dict[str, Any]]:
    result = {}
    for table in TABLE_NAMES:
        path = output_dir / f"{table}.parquet"
        connection.execute(
            f"COPY {table} TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(path)]
        )
        parquet_count = connection.execute(
            "SELECT count(*) FROM read_parquet(?)", [str(path)]
        ).fetchone()[0]
        table_count = connection.execute(
            f"SELECT count(*) FROM {table}"
        ).fetchone()[0]
        if parquet_count != table_count:
            raise ValueError(f"Parquet row count mismatch for {table}")
        result[table] = {"file": path.name, "row_count": int(parquet_count)}
    return result


def _file_metadata(output_dir: Path, file_name: str) -> dict[str, Any]:
    path = output_dir / file_name
    return {
        "file": file_name,
        "bytes": path.stat().st_size,
        "sha256": random_search._file_sha256(path),
    }


def build_analytics(
    *,
    campaign_dir: Path = DEFAULT_CAMPAIGN_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    """Build an atomic, SQL-verified analytical copy of sealed aggregates."""
    _validate_private_paths(campaign_dir, output_dir)
    if output_dir.exists():
        raise FileExistsError("Analytics output already exists")
    run_manifest, campaign_report, cell_reports = _load_validated_reports(
        campaign_dir
    )
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{output_dir.name}-", dir=output_dir.parent)
    )
    try:
        database_path = temporary / DATABASE_NAME
        connection = duckdb.connect(str(database_path))
        try:
            _create_tables(connection)
            _insert_rows(connection, "campaign", _campaign_rows(campaign_report))
            _insert_rows(connection, "methods", _method_rows(campaign_report))
            _insert_rows(
                connection, "hypotheses", _hypothesis_rows(campaign_report)
            )
            _insert_rows(connection, "cells", _cell_rows(cell_reports))
            _insert_rows(
                connection, "hypervolume_trace", _hypervolume_rows(cell_reports)
            )
            _insert_rows(connection, "status_counts", _status_rows(cell_reports))
            _insert_rows(
                connection,
                "integrity_gates",
                _integrity_rows(campaign_report, cell_reports),
            )
            row_counts = _verify_sql(connection, campaign_report, cell_reports)
            parquet = _export_parquet(connection, temporary)
            connection.execute("CHECKPOINT")
        finally:
            connection.close()

        database = _file_metadata(temporary, DATABASE_NAME)
        parquet_files = {
            table: {
                **metadata,
                **_file_metadata(temporary, metadata["file"]),
            }
            for table, metadata in parquet.items()
        }
        logical_fingerprint = random_search._content_sha256(
            {
                "campaign_manifest_sha256": run_manifest["manifest_sha256"],
                "campaign_report_sha256": campaign_report["report_sha256"],
                "builder_source_sha256": random_search._file_sha256(Path(__file__)),
                "duckdb_version": duckdb.__version__,
                "parquet": parquet_files,
                "table_row_counts": row_counts,
            }
        )
        manifest = random_search._seal_record(
            {
                "$schema": MANIFEST_SCHEMA_URI,
                "schema_version": SCHEMA_VERSION,
                "record_type": MANIFEST_TYPE,
                "campaign_id": campaign_report["campaign_id"],
                "campaign_configuration_fingerprint": campaign_report[
                    "configuration_fingerprint"
                ],
                "campaign_manifest_sha256": run_manifest["manifest_sha256"],
                "campaign_report_sha256": campaign_report["report_sha256"],
                "builder_source_sha256": random_search._file_sha256(Path(__file__)),
                "duckdb_version": duckdb.__version__,
                "logical_fingerprint": logical_fingerprint,
                "privacy_scope": "sealed_campaign_and_cell_aggregates_only",
                "database": database,
                "parquet": parquet_files,
                "table_row_counts": row_counts,
                "sql_aggregate_verification": "passed",
            },
            "manifest_sha256",
        )
        random_search._atomic_write_json(temporary / "manifest.json", manifest)
        os.replace(temporary, output_dir)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return manifest


def public_summary(manifest: dict[str, Any]) -> dict[str, Any]:
    """Return aggregate-only completion fields suitable for a terminal."""
    return {
        "status": "completed",
        "decision": "analytics_verified",
        "campaign_id": manifest["campaign_id"],
        "privacy_scope": manifest["privacy_scope"],
        "sql_aggregate_verification": manifest["sql_aggregate_verification"],
        "table_row_counts": manifest["table_row_counts"],
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-dir", type=Path, default=DEFAULT_CAMPAIGN_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    result = build_analytics(
        campaign_dir=args.campaign_dir,
        output_dir=args.output_dir,
    )
    print(json.dumps(public_summary(result), indent=2, sort_keys=True))
