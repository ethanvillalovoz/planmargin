"""Render a static, responsive trajectory comparison from rollout records."""

from __future__ import annotations

import argparse
import html
import json
import math
from pathlib import Path
from typing import Any

from planmargin import rollout_record

DEFAULT_INPUT = Path("artifacts/stage-0/rollout-records.json")
DEFAULT_OUTPUT = Path("artifacts/stage-0/trajectory-comparison.html")
PANEL_WIDTH = 560
PANEL_HEIGHT = 470
PLOT_LEFT = 22.0
PLOT_TOP = 58.0
PLOT_WIDTH = 516.0
PLOT_HEIGHT = 366.0


class VisualizationError(ValueError):
    """Raised when a collection cannot support the static comparison."""


def _text(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _number(value: Any, *, digits: int = 2) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "—"
    if not math.isfinite(float(value)):
        return "—"
    return f"{float(value):.{digits}f}"


def _records_by_variant_role(
    collection: dict[str, Any],
) -> dict[tuple[str, str], dict[str, Any]]:
    records = {
        (record["variant"], record["controller_role"]): record
        for record in collection["records"]
        if record.get("status") == "completed"
    }
    expected = {
        (variant, role)
        for variant in ("original", "counterfactual")
        for role in ("tested", "reference")
    }
    if records.keys() != expected:
        raise VisualizationError(
            "Visualization requires all four completed variant/role records."
        )
    return records


def _plot_transform(scene: dict[str, Any]) -> tuple[float, float, float]:
    bounds = scene["bounds_m"]
    world_width = bounds["max_x_m"] - bounds["min_x_m"]
    world_height = bounds["max_y_m"] - bounds["min_y_m"]
    scale = min(PLOT_WIDTH / world_width, PLOT_HEIGHT / world_height)
    x_offset = PLOT_LEFT + (PLOT_WIDTH - world_width * scale) / 2.0
    y_offset = PLOT_TOP + (PLOT_HEIGHT - world_height * scale) / 2.0
    return scale, x_offset, y_offset


def _point(
    x_m: float,
    y_m: float,
    scene: dict[str, Any],
    transform: tuple[float, float, float],
) -> tuple[float, float]:
    bounds = scene["bounds_m"]
    scale, x_offset, y_offset = transform
    return (
        x_offset + (float(x_m) - bounds["min_x_m"]) * scale,
        y_offset + (bounds["max_y_m"] - float(y_m)) * scale,
    )


def _polyline_segments(
    x_values: list[float],
    y_values: list[float],
    valid_values: list[bool] | None,
    scene: dict[str, Any],
    transform: tuple[float, float, float],
) -> list[str]:
    segments: list[str] = []
    points: list[str] = []
    for index, (x_m, y_m) in enumerate(zip(x_values, y_values)):
        if valid_values is not None and not valid_values[index]:
            if len(points) >= 2:
                segments.append(" ".join(points))
            points = []
            continue
        x, y = _point(x_m, y_m, scene, transform)
        points.append(f"{x:.2f},{y:.2f}")
    if len(points) >= 2:
        segments.append(" ".join(points))
    return segments


def _vehicle_polygon(
    *,
    x_m: float,
    y_m: float,
    yaw_rad: float,
    length_m: float,
    width_m: float,
    scene: dict[str, Any],
    transform: tuple[float, float, float],
) -> str:
    half_length = float(length_m) / 2.0
    half_width = float(width_m) / 2.0
    cosine = math.cos(float(yaw_rad))
    sine = math.sin(float(yaw_rad))
    corners = []
    for forward, lateral in (
        (half_length, half_width),
        (half_length, -half_width),
        (-half_length, -half_width),
        (-half_length, half_width),
    ):
        corner_x = float(x_m) + forward * cosine - lateral * sine
        corner_y = float(y_m) + forward * sine + lateral * cosine
        x, y = _point(corner_x, corner_y, scene, transform)
        corners.append(f"{x:.2f},{y:.2f}")
    return " ".join(corners)


def _trace_index_at_or_before(trace: dict[str, Any], timestep: int) -> int:
    valid_indices = [
        index
        for index, (step, valid) in enumerate(
            zip(trace["timestep"], trace["valid"])
        )
        if valid and step <= timestep
    ]
    if not valid_indices:
        raise VisualizationError("Actor trace has no valid state to render.")
    return valid_indices[-1]


def _highlight_timestep(records: list[dict[str, Any]]) -> int:
    failures = [
        record["outcome"].get("first_failure_timestep")
        for record in records
        if record["outcome"].get("first_failure_timestep") is not None
    ]
    if failures:
        return min(int(value) for value in failures)
    return min(int(record["outcome"]["final_timestep"]) for record in records)


def _road_class(feature_type: int) -> str:
    if feature_type in {1, 2, 3}:
        return "road-lane"
    if feature_type in {6, 9, 10}:
        return "road-marking road-broken"
    if feature_type in {7, 8, 11, 12, 13}:
        return "road-marking"
    if feature_type in {15, 16}:
        return "road-edge"
    return "road-detail"


def _roadgraph_layer(
    scene: dict[str, Any], transform: tuple[float, float, float]
) -> str:
    marks = []
    for feature in scene["roadgraph_features"]:
        segments = _polyline_segments(
            feature["x_m"],
            feature["y_m"],
            None,
            scene,
            transform,
        )
        marks.extend(
            f'<polyline class="{_road_class(feature["feature_type"])}" '
            f'points="{points}" />'
            for points in segments
        )
    return "".join(marks)


def _failure_marker(
    record: dict[str, Any],
    scene: dict[str, Any],
    transform: tuple[float, float, float],
) -> str:
    failure_timestep = record["outcome"].get("first_failure_timestep")
    if failure_timestep is None:
        return ""
    trace = record["trajectory"]
    index = _trace_index_at_or_before(trace, int(failure_timestep))
    x, y = _point(trace["x_m"][index], trace["y_m"][index], scene, transform)
    reasons = ", ".join(record["outcome"].get("first_failure_reasons", []))
    return (
        f'<g class="failure-marker" aria-label="Failure at timestep '
        f'{int(failure_timestep)}: {_text(reasons)}">'
        f'<circle cx="{x:.2f}" cy="{y:.2f}" r="7" />'
        f'<path d="M {x - 4:.2f} {y - 4:.2f} L {x + 4:.2f} {y + 4:.2f} '
        f'M {x + 4:.2f} {y - 4:.2f} L {x - 4:.2f} {y + 4:.2f}" />'
        "</g>"
    )


def _path_and_vehicle(
    record: dict[str, Any],
    scene: dict[str, Any],
    transform: tuple[float, float, float],
    highlight_timestep: int,
) -> str:
    role = record["controller_role"]
    trace = record["trajectory"]
    segments = _polyline_segments(
        trace["x_m"], trace["y_m"], trace["valid"], scene, transform
    )
    path_marks = "".join(
        f'<polyline class="trajectory trajectory-{role}" points="{points}" />'
        for points in segments
    )
    index = _trace_index_at_or_before(trace, highlight_timestep)
    dimensions = scene["actors"]["sdc"]
    polygon = _vehicle_polygon(
        x_m=trace["x_m"][index],
        y_m=trace["y_m"][index],
        yaw_rad=trace["yaw_rad"][index],
        length_m=dimensions["length_m"],
        width_m=dimensions["width_m"],
        scene=scene,
        transform=transform,
    )
    end_x, end_y = _point(
        trace["x_m"][index], trace["y_m"][index], scene, transform
    )
    label_y = end_y - 9 if role == "tested" else end_y + 17
    label = "Tested SDC" if role == "tested" else "Reference SDC"
    return (
        f"{path_marks}"
        f'<polygon class="vehicle vehicle-{role}" points="{polygon}" />'
        f'<text class="direct-label label-{role}" x="{end_x + 8:.2f}" '
        f'y="{label_y:.2f}">{label}</text>'
        f'{_failure_marker(record, scene, transform)}'
    )


def _target_layer(
    variant: str,
    scene: dict[str, Any],
    transform: tuple[float, float, float],
    highlight_timestep: int,
) -> str:
    track = scene["actors"]["mutation_target"][variant]
    segments = _polyline_segments(
        track["x_m"], track["y_m"], track["valid"], scene, transform
    )
    path_marks = "".join(
        f'<polyline class="trajectory trajectory-target" points="{points}" />'
        for points in segments
    )
    index = _trace_index_at_or_before(track, highlight_timestep)
    polygon = _vehicle_polygon(
        x_m=track["x_m"][index],
        y_m=track["y_m"][index],
        yaw_rad=track["yaw_rad"][index],
        length_m=track["length_m"][index],
        width_m=track["width_m"][index],
        scene=scene,
        transform=transform,
    )
    x, y = _point(
        track["x_m"][index], track["y_m"][index], scene, transform
    )
    return (
        f"{path_marks}"
        f'<polygon class="vehicle vehicle-target" points="{polygon}" />'
        f'<text class="direct-label label-target" x="{x + 8:.2f}" '
        f'y="{y - 9:.2f}">Mutation target</text>'
    )


def _scale_bar(scene: dict[str, Any], transform: tuple[float, float, float]) -> str:
    scale = transform[0]
    world_width = scene["bounds_m"]["max_x_m"] - scene["bounds_m"]["min_x_m"]
    length_m = 10 if world_width >= 30 else 5
    length_px = length_m * scale
    x = PLOT_LEFT + 12
    y = PANEL_HEIGHT - 21
    return (
        f'<g class="scale-bar"><path d="M {x:.1f} {y:.1f} h {length_px:.1f}" />'
        f'<path d="M {x:.1f} {y - 4:.1f} v 8 M {x + length_px:.1f} '
        f'{y - 4:.1f} v 8" />'
        f'<text x="{x + length_px / 2:.1f}" y="{y - 7:.1f}" '
        f'text-anchor="middle">{length_m} m</text></g>'
    )


def _panel_svg(
    *,
    variant: str,
    records: dict[tuple[str, str], dict[str, Any]],
    scene: dict[str, Any],
) -> str:
    variant_records = [
        records[(variant, "tested")], records[(variant, "reference")]
    ]
    timestep = _highlight_timestep(variant_records)
    transform = _plot_transform(scene)
    title = "Original scenario" if variant == "original" else "Counterfactual"
    subtitle = (
        "Mutation inactive"
        if variant == "original"
        else "Identical mutation, two controllers"
    )
    description = (
        f"{title}. Road geometry is shown in gray. The tested SDC path is "
        "solid blue, the reference SDC path is dashed orange, and the "
        f"mutation-target path is dotted purple. State shown at timestep {timestep}."
    )
    return (
        f'<svg class="scenario-panel" viewBox="0 0 {PANEL_WIDTH} {PANEL_HEIGHT}" '
        f'role="img" aria-labelledby="{variant}-title {variant}-desc">'
        f'<title id="{variant}-title">{title}</title>'
        f'<desc id="{variant}-desc">{_text(description)}</desc>'
        f'<rect class="panel-background" x="0.5" y="0.5" '
        f'width="{PANEL_WIDTH - 1}" height="{PANEL_HEIGHT - 1}" rx="12" />'
        f'<text class="panel-title" x="22" y="27">{title}</text>'
        f'<text class="panel-subtitle" x="22" y="46">{subtitle} · state at t={timestep}</text>'
        f'<g class="roadgraph">{_roadgraph_layer(scene, transform)}</g>'
        f'<g class="target-layer">{_target_layer(variant, scene, transform, timestep)}</g>'
        f'<g class="controller-layer">{_path_and_vehicle(variant_records[0], scene, transform, timestep)}'
        f'{_path_and_vehicle(variant_records[1], scene, transform, timestep)}</g>'
        f'{_scale_bar(scene, transform)}'
        "</svg>"
    )


def _insight_title(records: dict[tuple[str, str], dict[str, Any]]) -> str:
    failures = [
        record
        for record in records.values()
        if not bool(record["outcome"]["success"])
    ]
    if not failures:
        return "No controller failure appears in this feasibility comparison"
    first = min(
        failures,
        key=lambda record: record["outcome"].get("first_failure_timestep")
        or math.inf,
    )
    variant = str(first["variant"]).capitalize()
    role = str(first["controller_role"]).capitalize()
    timestep = first["outcome"].get("first_failure_timestep")
    return f"{variant} {role} controller first fails at timestep {timestep}"


def _mutation_items(record: dict[str, Any]) -> str:
    parameters = record["mutation"]["parameters"]
    mutation_name = str(
        record["mutation"].get("mutation_type", "unknown")
    ).replace("_", " ")
    items = [
        ("Mutation", mutation_name),
        *[(str(name).replace("_", " ").title(), value) for name, value in sorted(parameters.items())],
    ]
    return "".join(
        f'<div class="fact"><dt>{_text(label)}</dt><dd>{_text(value)}</dd></div>'
        for label, value in items
    )


def _metrics_rows(records: dict[tuple[str, str], dict[str, Any]]) -> str:
    rows = []
    for variant in ("original", "counterfactual"):
        for role in ("tested", "reference"):
            outcome = records[(variant, role)]["outcome"]
            status = "Pass" if outcome["success"] else "Fail"
            sdc_valid = "Yes" if outcome["sdc_valid_all_steps"] else "No"
            failure = outcome.get("first_failure_timestep")
            failure_text = "None" if failure is None else f"t={failure}"
            rows.append(
                "<tr>"
                f'<th scope="row">{_text(variant.capitalize())}</th>'
                f'<td data-label="Controller">{_text(role.capitalize())}</td>'
                f'<td data-label="Outcome"><span class="status status-{status.lower()}">{status}</span></td>'
                f'<td data-label="Max overlap">{_number(outcome.get("max_sdc_overlap"))}</td>'
                f'<td data-label="Max offroad">{_number(outcome.get("max_sdc_offroad"))}</td>'
                f'<td data-label="SDC valid">{sdc_valid}</td>'
                f'<td data-label="First failure">{_text(failure_text)}</td>'
                f'<td data-label="Final timestep">{_text(outcome.get("final_timestep"))}</td>'
                "</tr>"
            )
    return "".join(rows)


def render_html(collection: dict[str, Any]) -> str:
    """Return one self-contained responsive HTML/SVG comparison."""
    errors = rollout_record.validate_collection(collection)
    if errors:
        raise VisualizationError("; ".join(errors))
    if collection["collection_status"] != "complete":
        raise VisualizationError("Visualization requires a complete collection.")
    scene = collection["scene_context"]
    records = _records_by_variant_role(collection)
    any_failure = any(
        not bool(record["outcome"]["success"])
        for record in records.values()
    )
    summary = (
        "Failure markers identify the first failing state."
        if any_failure
        else "All four rollouts completed without overlap, offroad, invalid-state, or incomplete-rollout failures."
    )
    sample = records[("counterfactual", "tested")]
    revision = sample["provenance"]["git_revision"]
    revision_short = str(revision)[:12]
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>PlanMargin trajectory comparison</title>
  <style>
    :root {{ color-scheme: light; --ink: #172033; --muted: #5f6b7a; --line: #d8dee8; --paper: #ffffff; --wash: #f5f7fa; --tested: #1769aa; --reference: #b45309; --target: #7c3aed; --failure: #b42318; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: var(--wash); color: var(--ink); font: 15px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    main {{ width: min(1200px, calc(100% - 32px)); margin: 32px auto 48px; }}
    header {{ margin-bottom: 20px; }}
    .eyebrow {{ margin: 0 0 6px; color: #41526b; font-size: 12px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }}
    h1 {{ max-width: 850px; margin: 0; font-size: clamp(25px, 4vw, 40px); line-height: 1.12; letter-spacing: -.025em; }}
    .summary {{ max-width: 820px; margin: 12px 0 0; color: var(--muted); }}
    .facts {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 1px; margin: 20px 0; overflow: hidden; border: 1px solid var(--line); border-radius: 12px; background: var(--line); }}
    .fact {{ min-width: 0; padding: 12px 14px; background: var(--paper); }}
    dt {{ color: var(--muted); font-size: 11px; font-weight: 700; letter-spacing: .04em; text-transform: uppercase; }}
    dd {{ margin: 3px 0 0; overflow-wrap: anywhere; font-variant-numeric: tabular-nums; font-weight: 650; }}
    .panels {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }}
    .scenario-panel {{ display: block; width: 100%; height: auto; background: var(--paper); border-radius: 12px; }}
    .panel-background {{ fill: var(--paper); stroke: var(--line); }}
    .panel-title {{ fill: var(--ink); font-size: 16px; font-weight: 700; }}
    .panel-subtitle {{ fill: var(--muted); font-size: 11px; }}
    .roadgraph polyline {{ fill: none; vector-effect: non-scaling-stroke; }}
    .road-lane {{ stroke: #d9e0e9; stroke-width: 1.25; }}
    .road-marking {{ stroke: #aeb9c7; stroke-width: .8; }}
    .road-broken {{ stroke-dasharray: 4 4; }}
    .road-edge {{ stroke: #8391a3; stroke-width: 1; }}
    .road-detail {{ stroke: #c6ced9; stroke-width: .8; }}
    .trajectory {{ fill: none; stroke-linecap: round; stroke-linejoin: round; vector-effect: non-scaling-stroke; }}
    .trajectory-tested {{ stroke: var(--tested); stroke-width: 2.8; }}
    .trajectory-reference {{ stroke: var(--reference); stroke-width: 2.5; stroke-dasharray: 8 5; }}
    .trajectory-target {{ stroke: var(--target); stroke-width: 2; stroke-dasharray: 2 5; }}
    .vehicle {{ fill-opacity: .13; stroke-width: 1.6; vector-effect: non-scaling-stroke; }}
    .vehicle-tested {{ fill: var(--tested); stroke: var(--tested); }}
    .vehicle-reference {{ fill: var(--reference); stroke: var(--reference); stroke-dasharray: 4 2; }}
    .vehicle-target {{ fill: var(--target); stroke: var(--target); }}
    .direct-label {{ font-size: 11px; font-weight: 700; paint-order: stroke fill; stroke: var(--paper); stroke-width: 3px; stroke-linejoin: round; }}
    .label-tested {{ fill: var(--tested); }} .label-reference {{ fill: var(--reference); }} .label-target {{ fill: var(--target); }}
    .failure-marker circle {{ fill: var(--paper); stroke: var(--failure); stroke-width: 2; }}
    .failure-marker path {{ fill: none; stroke: var(--failure); stroke-width: 1.7; }}
    .scale-bar path {{ fill: none; stroke: #56657a; stroke-width: 1; shape-rendering: crispEdges; }}
    .scale-bar text {{ fill: var(--muted); font-size: 10px; }}
    .table-wrap {{ margin-top: 20px; overflow-x: auto; border: 1px solid var(--line); border-radius: 12px; background: var(--paper); }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; font-variant-numeric: tabular-nums; }}
    caption {{ padding: 14px 16px 8px; text-align: left; font-size: 16px; font-weight: 700; }}
    th, td {{ padding: 10px 14px; border-top: 1px solid #e7ebf0; text-align: left; white-space: nowrap; }}
    thead th {{ color: var(--muted); font-size: 11px; letter-spacing: .03em; text-transform: uppercase; }}
    .status {{ display: inline-block; min-width: 42px; padding: 2px 7px; border-radius: 999px; font-size: 11px; font-weight: 750; text-align: center; }}
    .status-pass {{ color: #17633a; background: #e8f5ed; }} .status-fail {{ color: #8f1d17; background: #fcebea; }}
    .notes {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 18px; color: var(--muted); font-size: 12px; }}
    .notes p {{ margin: 0; }}
    @media (max-width: 760px) {{
      main {{ width: calc(100% - 20px); max-width: 600px; margin-top: 18px; }}
      .panels, .notes {{ grid-template-columns: 1fr; }}
      .table-wrap {{ overflow: visible; }}
      table, tbody {{ display: block; }}
      caption {{ display: block; width: 100%; }}
      thead {{ position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); white-space: nowrap; }}
      tbody {{ padding: 0 14px 14px; }}
      tbody tr {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px 18px; padding: 14px 0; border-top: 1px solid #e7ebf0; }}
      tbody th, tbody td {{ display: block; padding: 0; border: 0; white-space: normal; }}
      tbody th {{ grid-column: 1 / -1; font-size: 14px; }}
      tbody td::before {{ display: block; content: attr(data-label); margin-bottom: 2px; color: var(--muted); font-size: 10px; font-weight: 700; letter-spacing: .03em; text-transform: uppercase; }}
      .panel-title {{ font-size: 19px; }}
      .panel-subtitle {{ font-size: 14px; }}
      .direct-label {{ font-size: 15px; }}
      .scale-bar text {{ font-size: 13px; }}
    }}
    @media print {{ body {{ background: white; }} main {{ width: 100%; margin: 0; }} .panels {{ gap: 8px; }} }}
  </style>
</head>
<body>
<main>
  <header>
    <p class="eyebrow">PlanMargin · Stage 0 spatial audit</p>
    <h1>{_text(_insight_title(records))}</h1>
    <p class="summary">{_text(summary)} Roadgraph geometry, actor footprints, trajectories, mutation configuration, and metrics come from the same versioned rollout-record collection.</p>
  </header>
  <dl class="facts">{_mutation_items(sample)}</dl>
  <section class="panels" aria-label="Original and counterfactual spatial comparison">
    {_panel_svg(variant="original", records=records, scene=scene)}
    {_panel_svg(variant="counterfactual", records=records, scene=scene)}
  </section>
  <div class="table-wrap">
    <table>
      <caption>Outcome and failure-time audit</caption>
      <thead><tr><th>Variant</th><th>Controller</th><th>Outcome</th><th>Max overlap</th><th>Max offroad</th><th>SDC valid</th><th>First failure</th><th>Final t</th></tr></thead>
      <tbody>{_metrics_rows(records)}</tbody>
    </table>
  </div>
  <footer class="notes">
    <p><strong>Encoding.</strong> Tested controller: solid blue. Reference controller: dashed orange. Mutation target: dotted purple. Color and line pattern both carry identity.</p>
    <p><strong>Scope.</strong> Private WOMD-derived geometry stays in this ignored local artifact. This is a feasibility trace, not a production Waymo Driver evaluation. Record schema 1.1.0 · rollout revision {_text(revision_short)}.</p>
  </footer>
</main>
</body>
</html>
"""


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    collection = json.loads(args.input.read_text(encoding="utf-8"))
    rendered = render_html(collection)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "passed",
                "schema_version": collection["schema_version"],
                "panel_count": 2,
                "output": str(args.output),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
