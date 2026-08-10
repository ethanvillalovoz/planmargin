"""Continuous pairwise interaction metrics for same-route vehicle traces."""

from __future__ import annotations

import math
from typing import Any

import numpy as np


def oriented_box_corners(
    *,
    x_m: float,
    y_m: float,
    yaw_rad: float,
    length_m: float,
    width_m: float,
) -> np.ndarray:
    """Return four counter-clockwise corners for an oriented vehicle box."""
    forward = np.array([math.cos(yaw_rad), math.sin(yaw_rad)])
    lateral = np.array([-forward[1], forward[0]])
    center = np.array([x_m, y_m], dtype=np.float64)
    half_length = length_m / 2.0
    half_width = width_m / 2.0
    return np.array(
        [
            center + half_length * forward + half_width * lateral,
            center - half_length * forward + half_width * lateral,
            center - half_length * forward - half_width * lateral,
            center + half_length * forward - half_width * lateral,
        ]
    )


def _point_segment_distance(
    point: np.ndarray, start: np.ndarray, end: np.ndarray
) -> float:
    segment = end - start
    squared_length = float(np.dot(segment, segment))
    if squared_length <= 1e-12:
        return float(np.linalg.norm(point - start))
    fraction = float(np.dot(point - start, segment) / squared_length)
    projection = start + np.clip(fraction, 0.0, 1.0) * segment
    return float(np.linalg.norm(point - projection))


def signed_oriented_box_separation(
    first: np.ndarray, second: np.ndarray
) -> float:
    """Return exact positive distance or negative SAT penetration depth."""
    polygons = (np.asarray(first, dtype=np.float64), np.asarray(second, dtype=np.float64))
    if any(polygon.shape != (4, 2) for polygon in polygons):
        raise ValueError("oriented boxes must each have shape (4, 2)")
    axes: list[np.ndarray] = []
    for polygon in polygons:
        for index in range(4):
            edge = polygon[(index + 1) % 4] - polygon[index]
            normal = np.array([-edge[1], edge[0]])
            magnitude = float(np.linalg.norm(normal))
            if magnitude > 1e-12:
                axes.append(normal / magnitude)
    overlaps: list[float] = []
    separated = False
    for axis in axes:
        first_projection = polygons[0] @ axis
        second_projection = polygons[1] @ axis
        overlap = min(first_projection.max(), second_projection.max()) - max(
            first_projection.min(), second_projection.min()
        )
        overlaps.append(float(overlap))
        if overlap < 0.0:
            separated = True
    if not separated:
        return -min(overlaps)
    distances = []
    for source, target in ((polygons[0], polygons[1]), (polygons[1], polygons[0])):
        for point in source:
            distances.extend(
                _point_segment_distance(
                    point, target[index], target[(index + 1) % 4]
                )
                for index in range(4)
            )
    return min(distances)


def longitudinal_ttc_s(
    *,
    sdc_x_m: float,
    sdc_y_m: float,
    sdc_yaw_rad: float,
    sdc_vel_x_mps: float,
    sdc_vel_y_mps: float,
    sdc_length_m: float,
    lead_x_m: float,
    lead_y_m: float,
    lead_vel_x_mps: float,
    lead_vel_y_mps: float,
    lead_length_m: float,
) -> float | None:
    """Return same-route closing TTC, or None when the lead is not closing."""
    forward = np.array(
        [math.cos(sdc_yaw_rad), math.sin(sdc_yaw_rad)], dtype=np.float64
    )
    relative_position = np.array(
        [lead_x_m - sdc_x_m, lead_y_m - sdc_y_m]
    )
    center_gap = float(np.dot(relative_position, forward))
    if center_gap <= 0.0:
        return None
    bumper_gap = center_gap - (sdc_length_m + lead_length_m) / 2.0
    if bumper_gap <= 0.0:
        return 0.0
    relative_velocity = np.array(
        [
            sdc_vel_x_mps - lead_vel_x_mps,
            sdc_vel_y_mps - lead_vel_y_mps,
        ]
    )
    closing_speed = float(np.dot(relative_velocity, forward))
    if closing_speed <= 1e-6:
        return None
    return bumper_gap / closing_speed


def interaction_metrics(
    sdc: dict[str, Any], lead: dict[str, Any]
) -> dict[str, float | int | None]:
    """Aggregate separation and TTC over aligned SDC and lead tracks."""
    required = (
        "x_m",
        "y_m",
        "yaw_rad",
        "vel_x_mps",
        "vel_y_mps",
        "length_m",
        "width_m",
        "valid",
    )
    for name, track in (("sdc", sdc), ("lead", lead)):
        if any(field not in track for field in required):
            raise ValueError(f"{name} track is missing required fields")
        lengths = {len(track[field]) for field in required}
        if len(lengths) != 1:
            raise ValueError(f"{name} track fields must have equal lengths")
    if len(sdc["x_m"]) != len(lead["x_m"]):
        raise ValueError("SDC and lead tracks must be aligned")
    separations: list[float] = []
    ttcs: list[float] = []
    for index in range(len(sdc["x_m"])):
        if not sdc["valid"][index] or not lead["valid"][index]:
            continue
        first = oriented_box_corners(
            x_m=float(sdc["x_m"][index]),
            y_m=float(sdc["y_m"][index]),
            yaw_rad=float(sdc["yaw_rad"][index]),
            length_m=float(sdc["length_m"][index]),
            width_m=float(sdc["width_m"][index]),
        )
        second = oriented_box_corners(
            x_m=float(lead["x_m"][index]),
            y_m=float(lead["y_m"][index]),
            yaw_rad=float(lead["yaw_rad"][index]),
            length_m=float(lead["length_m"][index]),
            width_m=float(lead["width_m"][index]),
        )
        separations.append(signed_oriented_box_separation(first, second))
        ttc = longitudinal_ttc_s(
            sdc_x_m=float(sdc["x_m"][index]),
            sdc_y_m=float(sdc["y_m"][index]),
            sdc_yaw_rad=float(sdc["yaw_rad"][index]),
            sdc_vel_x_mps=float(sdc["vel_x_mps"][index]),
            sdc_vel_y_mps=float(sdc["vel_y_mps"][index]),
            sdc_length_m=float(sdc["length_m"][index]),
            lead_x_m=float(lead["x_m"][index]),
            lead_y_m=float(lead["y_m"][index]),
            lead_vel_x_mps=float(lead["vel_x_mps"][index]),
            lead_vel_y_mps=float(lead["vel_y_mps"][index]),
            lead_length_m=float(lead["length_m"][index]),
        )
        if ttc is not None and math.isfinite(ttc):
            ttcs.append(ttc)
    if not separations:
        raise ValueError("tracks have no jointly valid states")
    return {
        "jointly_valid_states": len(separations),
        "minimum_signed_separation_m": round(min(separations), 6),
        "minimum_longitudinal_ttc_s": (
            round(min(ttcs), 6) if ttcs else None
        ),
    }
