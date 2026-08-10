"""Data-free tests for the static trajectory-comparison renderer."""

import pytest

from planmargin import rollout_record
from planmargin import trajectory_visualization
from test_rollout_record import _source


def test_render_contains_two_accessible_directly_labeled_panels() -> None:
    collection = rollout_record.export_collection(_source())

    rendered = trajectory_visualization.render_html(collection)

    assert rendered.count('<svg class="scenario-panel"') == 2
    assert rendered.count('role="img"') == 2
    assert "<title id=\"original-title\">Original scenario</title>" in rendered
    assert "<desc id=\"counterfactual-desc\">" in rendered
    assert "Tested SDC" in rendered
    assert "Reference SDC" in rendered
    assert "Mutation target" in rendered
    assert "Outcome and failure-time audit" in rendered


def test_render_has_responsive_text_fallback_without_remote_dependencies() -> None:
    rendered = trajectory_visualization.render_html(
        rollout_record.export_collection(_source())
    )

    assert "@media (max-width: 760px)" in rendered
    assert "<table>" in rendered
    assert 'data-label="First failure"' in rendered
    assert "tbody tr { display: grid" in rendered
    assert "<script" not in rendered
    assert "https://" not in rendered
    assert "synthetic-scenario" not in rendered


def test_render_marks_and_names_first_failure() -> None:
    source = _source()
    outcome = source["rollouts"]["mutated"]["tested"]["outcome"]
    outcome["success"] = False
    outcome["failure_reasons"] = ["sdc_overlap"]
    outcome["max_sdc_overlap"] = 1.0
    outcome["first_failure_timestep"] = 11
    outcome["first_failure_reasons"] = ["sdc_overlap"]

    rendered = trajectory_visualization.render_html(
        rollout_record.export_collection(source)
    )

    assert "Counterfactual Tested controller first fails at timestep 11" in rendered
    assert 'class="failure-marker"' in rendered
    assert "Failure at timestep 11: sdc_overlap" in rendered


def test_render_escapes_record_text() -> None:
    source = _source()
    source["mutation"]["mutation_type"] = "<script>alert(1)</script>"

    rendered = trajectory_visualization.render_html(
        rollout_record.export_collection(source)
    )

    assert "<script>alert(1)</script>" not in rendered
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in rendered


def test_render_rejects_invalid_candidate_collection() -> None:
    source = _source(status="rejected")
    source.pop("rollouts")
    collection = rollout_record.export_collection(source)

    with pytest.raises(
        trajectory_visualization.VisualizationError,
        match="complete collection",
    ):
        trajectory_visualization.render_html(collection)
