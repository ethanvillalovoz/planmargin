"""Data-free tests for the constrained evidence assistant."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import jsonschema
import pytest

from planmargin import evidence_assistant


ROOT = Path(__file__).parents[1]
SCHEMA = json.loads(
    (ROOT / "schemas/evidence-assistant-response-v1.schema.json").read_text(
        encoding="utf-8"
    )
)


@pytest.mark.parametrize(
    ("question", "query_id"),
    (
        ("What happened in the campaign overall?", "campaign_overview"),
        ("Was Bayesian better than random search?", "method_comparison"),
        ("What happened to H1, H2, and H3?", "hypothesis_decisions"),
        ("Does this prove the production Waymo Driver is safe?", "claim_boundary"),
        ("How does the Beam to Parquet pipeline work?", "beam_pipeline"),
    ),
)
def test_offline_answers_execute_one_allowlisted_query_and_validate(
    question: str, query_id: str
) -> None:
    response = evidence_assistant.answer_question(
        question, tools=evidence_assistant.PublicEvidenceTools()
    )
    repeated = evidence_assistant.answer_question(
        question, tools=evidence_assistant.PublicEvidenceTools()
    )

    assert response == repeated
    jsonschema.validate(response, SCHEMA)
    assert response["question"]["query_id"] == query_id
    assert response["tool_result"]["query_id"] == query_id
    assert response["provider"]["id"] == "offline_deterministic"
    assert response["privacy"] == {
        "raw_question_persisted": False,
        "raw_question_sent_to_provider": False,
        "private_data_sent_to_provider": False,
        "provider_input_scope": "none",
    }
    assert question not in json.dumps(response)
    available = {fact["fact_id"] for fact in response["tool_result"]["facts"]}
    assert set(response["explanation"]["cited_fact_ids"]).issubset(available)


def test_unknown_questions_and_nonallowlisted_tools_fail_closed() -> None:
    with pytest.raises(ValueError, match="outside the allowlisted scope"):
        evidence_assistant.answer_question(
            "Tell me a joke", tools=evidence_assistant.PublicEvidenceTools()
        )
    with pytest.raises(ValueError, match="not allowlisted"):
        evidence_assistant.PublicEvidenceTools().execute("run_arbitrary_sql")
    with pytest.raises(ValueError, match="exceeds"):
        evidence_assistant.classify_question("campaign " + "x" * 500)
    with pytest.raises(ValueError, match="exceeds"):
        evidence_assistant.classify_question("campaign" + " " * 1000)


def test_embedded_public_evidence_is_sealed_to_tracked_sources() -> None:
    for citation in evidence_assistant.PUBLIC_CITATIONS.values():
        source = ROOT / citation.repository_path
        assert source.is_file() and not source.is_symlink()
        assert hashlib.sha256(source.read_bytes()).hexdigest() == (citation.sha256)

    beam = json.loads(
        (ROOT / "experiments/platform/beam-feature-integration.json").read_text(
            encoding="utf-8"
        )
    )
    result = evidence_assistant.PublicEvidenceTools().execute("beam_pipeline")
    values = {fact.fact_id: fact.value for fact in result.facts}
    assert values["beam.records"] == beam["pipeline"]["records_scanned"]
    assert values["beam.events"] == beam["pipeline"]["accepted_event_count"]
    assert values["beam.shards"] == beam["pipeline"]["source_shard_count"]
    assert values["beam.partitions"] == beam["pipeline"]["partition_count"]
    assert all(beam["integrity_gates"].values())
    assert beam["privacy"]["held_out_opened"] is False
    integration = json.loads(
        (ROOT / "experiments/platform/evidence-assistant-integration.json").read_text(
            encoding="utf-8"
        )
    )
    assert integration["public_catalog_fingerprint"] == (
        evidence_assistant.public_catalog_fingerprint()
    )


class _FakeInteractions:
    def __init__(self, draft: dict[str, Any]) -> None:
        self.draft = draft
        self.arguments: dict[str, Any] | None = None

    def create(self, **kwargs: Any) -> SimpleNamespace:
        self.arguments = kwargs
        return SimpleNamespace(output_text=json.dumps(self.draft))


class _FakeClient:
    def __init__(self, draft: dict[str, Any]) -> None:
        self.interactions = _FakeInteractions(draft)
        self.closed = False

    def close(self) -> None:
        self.closed = True


def test_gemini_receives_only_public_tool_packet_and_structured_schema() -> None:
    question = "Compare Bayesian and random; private scenario is secret-123."
    draft = {
        "summary": "The constrained method retained more eligible proposals.",
        "interpretation": "The evidence supports validity yield, not failure discovery.",
        "cited_fact_ids": ["method.valid_rate_delta", "method.findings"],
        "limitation": "The result remains bounded development evidence.",
    }
    client = _FakeClient(draft)
    provider = evidence_assistant.GeminiProvider(
        api_key="test-key",
        model=evidence_assistant.DEFAULT_MODEL,
        confirmed_free_tier=True,
        client_factory=lambda _: client,
    )

    response = evidence_assistant.answer_question(
        question,
        tools=evidence_assistant.PublicEvidenceTools(),
        provider=provider,
    )

    assert client.closed
    assert client.interactions.arguments is not None
    packet = client.interactions.arguments
    assert packet["model"] == evidence_assistant.DEFAULT_MODEL
    assert packet["response_format"]["mime_type"] == "application/json"
    assert packet["response_format"]["schema"] == (
        evidence_assistant.GEMINI_RESPONSE_SCHEMA
    )
    encoded_schema = json.dumps(packet["response_format"]["schema"])
    assert "minLength" not in encoded_schema
    assert "maxLength" not in encoded_schema
    assert question not in packet["input"]
    assert "secret-123" not in packet["input"]
    sent = json.loads(packet["input"])
    assert sent["query_id"] == "method_comparison"
    assert set(sent) == {"facts", "instruction", "limitations", "query_id"}
    hosted_context = json.dumps(
        {
            "facts": [fact["qualitative_statement"] for fact in sent["facts"]],
            "limitations": sent["limitations"],
        }
    )
    assert not re.search(r"\d", hosted_context)
    assert not re.search(
        r"\b(?:safe|safety|production|held[ -]?out|causality)\b",
        hosted_context,
        flags=re.IGNORECASE,
    )
    assert response["privacy"]["provider_input_scope"] == (
        "public_aggregate_tool_result_only"
    )
    assert response["privacy"]["raw_question_sent_to_provider"] is False
    assert response["privacy"]["private_data_sent_to_provider"] is False
    jsonschema.validate(response, SCHEMA)


def test_gemini_defensively_clips_overlong_structured_prose() -> None:
    result = evidence_assistant.PublicEvidenceTools().execute("method_comparison")
    safe_phrase = "The bounded evidence remains qualitative and scoped to supplied facts. "
    provider = evidence_assistant.GeminiProvider(
        api_key="test-key",
        model=evidence_assistant.DEFAULT_MODEL,
        confirmed_free_tier=True,
        client_factory=lambda _: _FakeClient(
            {
                "summary": safe_phrase * 8,
                "interpretation": safe_phrase * 12,
                "cited_fact_ids": ["method.valid_rate_delta", "method.findings"],
                "limitation": safe_phrase * 8,
            }
        ),
    )

    draft = provider.explain(result)

    assert len(draft.summary) <= 280
    assert len(draft.interpretation) <= 500
    assert len(draft.limitation) <= 280
    assert draft.summary.endswith("…")
    assert draft.interpretation.endswith("…")
    assert draft.limitation.endswith("…")


def test_gemini_rejects_private_sources_and_generated_metrics() -> None:
    public = evidence_assistant.PublicEvidenceTools().execute("campaign_overview")
    private = evidence_assistant.ToolResult(
        public.query_id,
        public.title,
        "real_local_redacted",
        public.facts,
        public.citations,
        public.limitations,
    )
    provider = evidence_assistant.GeminiProvider(
        api_key="test-key",
        model=evidence_assistant.DEFAULT_MODEL,
        confirmed_free_tier=True,
        client_factory=lambda _: _FakeClient(
            {
                "summary": "The campaign had 100 cells.",
                "interpretation": "This is bounded evidence.",
                "cited_fact_ids": ["campaign.cells"],
                "limitation": "Held-out evidence is absent.",
            }
        ),
    )

    with pytest.raises(ValueError, match="public aggregate evidence only"):
        provider.explain(private)
    with pytest.raises(ValueError, match="numeric metrics"):
        provider.explain(public)


def test_gemini_rejects_unknown_citations_and_safety_claims() -> None:
    result = evidence_assistant.PublicEvidenceTools().execute("method_comparison")
    for draft, message in (
        (
            {
                "summary": "The method retained more eligible proposals.",
                "interpretation": "This proves the planner is safer.",
                "cited_fact_ids": ["method.valid_rate_delta"],
                "limitation": "The evidence is bounded.",
            },
            "claim boundary",
        ),
        (
            {
                "summary": "The constrained method showed superior efficiency.",
                "interpretation": "The eligible-proposal yield was higher.",
                "cited_fact_ids": ["method.valid_rate_delta"],
                "limitation": "The evidence is bounded.",
            },
            "claim boundary",
        ),
        (
            {
                "summary": "The method retained more eligible proposals.",
                "interpretation": "The result is narrow.",
                "cited_fact_ids": ["invented.fact"],
                "limitation": "The evidence is bounded.",
            },
            "outside the tool result",
        ),
        (
            {
                "summary": "   ",
                "interpretation": "The result is narrow.",
                "cited_fact_ids": ["method.valid_rate_delta"],
                "limitation": "The evidence is bounded.",
            },
            "empty explanation field",
        ),
    ):
        provider = evidence_assistant.GeminiProvider(
            api_key="test-key",
            model=evidence_assistant.DEFAULT_MODEL,
            confirmed_free_tier=True,
            client_factory=lambda _, value=draft: _FakeClient(value),
        )
        with pytest.raises(ValueError, match=message):
            provider.explain(result)


class _FakeLocalRepository:
    analytics_manifest = {"manifest_sha256": "a" * 64}

    def campaign(self) -> dict[str, Any]:
        return {
            "total_physical_rollouts": 14110,
            "waymax_rollout_steps": 1128800,
        }

    def methods(self) -> list[dict[str, Any]]:
        return [
            {
                "method": "bayesian",
                "support_and_pipeline_valid_rate": 0.69375,
                "qualifying_failure_count": 0,
            },
            {
                "method": "random",
                "support_and_pipeline_valid_rate": 0.545625,
                "qualifying_failure_count": 0,
            },
        ]

    def hypotheses(self) -> list[dict[str, Any]]:
        return [
            {
                "hypothesis": "h1_efficiency",
                "status": "untestable",
                "bayesian_minus_random_valid_rate": None,
            },
            {
                "hypothesis": "h2_minimality",
                "status": "untestable",
                "bayesian_minus_random_valid_rate": None,
            },
            {
                "hypothesis": "h3_validity",
                "status": "supported",
                "bayesian_minus_random_valid_rate": 0.148125,
            },
        ]


@pytest.mark.parametrize(
    "question",
    ("Summarize the campaign", "Compare methods", "Explain the hypotheses"),
)
def test_local_tools_use_verified_aggregate_vocabulary(question: str) -> None:
    tools = evidence_assistant.LocalEvidenceTools(_FakeLocalRepository())
    response = evidence_assistant.answer_question(question, tools=tools)

    assert response["tool_result"]["source_mode"] == "real_local_redacted"
    assert all(
        citation["repository_path"] == "[ignored local artifact]"
        for citation in response["tool_result"]["citations"]
    )
    jsonschema.validate(response, SCHEMA)


def test_gemini_requires_explicit_free_tier_confirmation() -> None:
    with pytest.raises(ValueError, match="free-tier"):
        evidence_assistant.GeminiProvider(
            api_key="test-key",
            model=evidence_assistant.DEFAULT_MODEL,
            confirmed_free_tier=False,
        )


def test_cli_rejects_gemini_without_confirmation_without_traceback(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit, match="free-tier"):
        evidence_assistant.main(
            [
                "--provider",
                "gemini",
                "--question",
                "Summarize the campaign",
            ]
        )
    assert capsys.readouterr().out == ""
