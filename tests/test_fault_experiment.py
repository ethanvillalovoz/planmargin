"""The interactive command-fault metadata must satisfy the public interchange schema."""

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from planmargin.fault_experiment import fault_mutation


@pytest.mark.parametrize("plan", ["command_dropout", "assistance_handoff"])
def test_fault_mutation_contract(plan):
    schema = json.loads(
        (
            Path(__file__).parents[1]
            / "schemas/rollout-record-collection-v1.1.schema.json"
        ).read_text()
    )
    definition = schema["$defs"]["rolloutRecord"]["properties"]["mutation"]
    mutation = fault_mutation(plan)
    for applied in (False, True):
        Draft202012Validator(definition).validate({**mutation, "applied": applied})
    assert mutation["rejection_reasons"] == []
    assert mutation["parameters"]["fault_onset_seconds"] == 2
    assert ("recovery_seconds" in mutation["parameters"]) == (
        plan == "assistance_handoff"
    )


def test_fault_mutation_rejects_unknown_plan():
    with pytest.raises(ValueError):
        fault_mutation("arbitrary")
