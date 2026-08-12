"""Answer bounded questions from deterministic aggregate PlanMargin evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal, Protocol, Sequence

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "1.0.0"
RECORD_TYPE = "planmargin.evidence_assistant_response"
SCHEMA_URI = (
    "https://raw.githubusercontent.com/ethanvillalovoz/planmargin/main/"
    "schemas/evidence-assistant-response-v1.schema.json"
)
DEFAULT_MODEL = "gemini-3.1-flash-lite"
MAX_QUESTION_CHARACTERS = 500


@dataclass(frozen=True)
class Citation:
    citation_id: str
    title: str
    repository_path: str
    sha256: str


@dataclass(frozen=True)
class Fact:
    fact_id: str
    statement: str
    value: str | int | float | bool | None
    unit: str | None
    citation_id: str


@dataclass(frozen=True)
class ToolResult:
    query_id: str
    title: str
    source_mode: Literal["public_aggregate", "real_local_redacted"]
    facts: tuple[Fact, ...]
    citations: tuple[Citation, ...]
    limitations: tuple[str, ...]


class EvidenceTools(Protocol):
    source_mode: Literal["public_aggregate", "real_local_redacted"]

    def execute(self, query_id: str) -> ToolResult: ...


class LocalEvidenceRepository(Protocol):
    analytics_manifest: dict[str, Any] | None

    def campaign(self) -> dict[str, Any]: ...

    def methods(self) -> list[dict[str, Any]]: ...

    def hypotheses(self) -> list[dict[str, Any]]: ...


class ExplanationDraft(BaseModel):
    """Strict hosted-provider output; deterministic facts remain out of model text."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=280)
    interpretation: str = Field(min_length=1, max_length=500)
    cited_fact_ids: list[str] = Field(min_length=1, max_length=8)
    limitation: str = Field(min_length=1, max_length=280)


# Keep the hosted schema inside Gemini's documented JSON Schema subset. Pydantic
# still enforces the tighter string lengths after the response returns.
GEMINI_RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "summary": {
            "type": "string",
            "description": "A concise qualitative explanation without numbers.",
        },
        "interpretation": {
            "type": "string",
            "description": "A bounded interpretation of the cited evidence.",
        },
        "cited_fact_ids": {
            "type": "array",
            "minItems": 1,
            "maxItems": 8,
            "items": {"type": "string"},
            "description": "Only fact IDs present in the supplied packet.",
        },
        "limitation": {
            "type": "string",
            "description": "One qualitative limitation without numbers.",
        },
    },
    "required": ["summary", "interpretation", "cited_fact_ids", "limitation"],
}


class ExplanationProvider(Protocol):
    provider_id: str

    def explain(self, result: ToolResult) -> ExplanationDraft: ...


def _fact(
    fact_id: str,
    statement: str,
    value: str | int | float | bool | None,
    unit: str | None,
    citation_id: str,
) -> Fact:
    return Fact(fact_id, statement, value, unit, citation_id)


CAMPAIGN = "campaign-results"
HELD_OUT = "held-out-decision"
BEAM = "beam-integration"

PUBLIC_CITATIONS = {
    CAMPAIGN: Citation(
        CAMPAIGN,
        "Natural matched-search development results",
        "docs/natural-development-results.md",
        "c0d579e364b6048cd275fcca273d59eb59d98a55c57f5135412226c81b938fb5",
    ),
    HELD_OUT: Citation(
        HELD_OUT,
        "Version-one held-out no-go decision",
        "docs/decisions/0003-version-one-heldout-no-go.md",
        "3637ed6a933a2bc080e4de1c5d67e9fee9d44202a59c679893cf1f6e53d3c131",
    ),
    BEAM: Citation(
        BEAM,
        "Beam feature pipeline integration evidence",
        "experiments/platform/beam-feature-integration.json",
        "eba6ac5949e78a4b5a1103868d7f811f1e821b12e2d76b99a833e0276425e099",
    ),
}


class PublicEvidenceTools:
    """Execute closed queries over already-published aggregate evidence."""

    source_mode: Literal["public_aggregate"] = "public_aggregate"

    @staticmethod
    def _citations(*citation_ids: str) -> tuple[Citation, ...]:
        return tuple(PUBLIC_CITATIONS[item] for item in citation_ids)

    def execute(self, query_id: str) -> ToolResult:
        try:
            return getattr(self, f"_query_{query_id}")()
        except AttributeError as error:
            raise ValueError(f"Query is not allowlisted: {query_id}") from error

    def _query_campaign_overview(self) -> ToolResult:
        return ToolResult(
            "campaign_overview",
            "Frozen experiment-v1 campaign overview",
            self.source_mode,
            (
                _fact(
                    "campaign.cells",
                    "The campaign completed 100 cells.",
                    100,
                    "cells",
                    CAMPAIGN,
                ),
                _fact(
                    "campaign.proposals",
                    "The campaign evaluated 3,200 proposals.",
                    3200,
                    "proposals",
                    CAMPAIGN,
                ),
                _fact(
                    "campaign.rollouts",
                    "The campaign executed 14,110 physical rollouts.",
                    14110,
                    "rollouts",
                    CAMPAIGN,
                ),
                _fact(
                    "campaign.steps",
                    "The campaign executed 1,128,800 Waymax rollout steps.",
                    1128800,
                    "steps",
                    CAMPAIGN,
                ),
                _fact(
                    "campaign.findings",
                    "Neither method produced a qualifying finding.",
                    0,
                    "findings per method",
                    CAMPAIGN,
                ),
                _fact(
                    "campaign.held_out",
                    "No held-out comparative campaign was run.",
                    False,
                    None,
                    HELD_OUT,
                ),
            ),
            self._citations(CAMPAIGN, HELD_OUT),
            _standard_limitations(),
        )

    def _query_method_comparison(self) -> ToolResult:
        return ToolResult(
            "method_comparison",
            "Random and constrained-Bayesian aggregate comparison",
            self.source_mode,
            (
                _fact(
                    "method.random_valid_rate",
                    "Random search had a 54.5625% support-and-pipeline-valid rate.",
                    54.5625,
                    "percent",
                    CAMPAIGN,
                ),
                _fact(
                    "method.bayesian_valid_rate",
                    "Constrained Bayesian search had a 69.3750% support-and-pipeline-valid rate.",
                    69.375,
                    "percent",
                    CAMPAIGN,
                ),
                _fact(
                    "method.valid_rate_delta",
                    "The Bayesian-minus-random valid-rate difference was 14.8125 percentage points.",
                    14.8125,
                    "percentage points",
                    CAMPAIGN,
                ),
                _fact(
                    "method.random_hypervolume",
                    "Random search had mean final feasible hypervolume 0.227223.",
                    0.227223,
                    None,
                    CAMPAIGN,
                ),
                _fact(
                    "method.bayesian_hypervolume",
                    "Constrained Bayesian search had mean final feasible hypervolume 0.258250.",
                    0.25825,
                    None,
                    CAMPAIGN,
                ),
                _fact(
                    "method.findings",
                    "Both methods produced zero qualifying findings.",
                    0,
                    "findings per method",
                    CAMPAIGN,
                ),
                _fact(
                    "method.h3",
                    "The frozen H3 validity hypothesis was supported.",
                    "supported",
                    None,
                    CAMPAIGN,
                ),
            ),
            self._citations(CAMPAIGN),
            _standard_limitations(),
        )

    def _query_hypothesis_decisions(self) -> ToolResult:
        return ToolResult(
            "hypothesis_decisions",
            "Frozen experiment-v1 hypothesis decisions",
            self.source_mode,
            (
                _fact(
                    "hypothesis.h1",
                    "H1 efficiency was untestable because neither method found a qualifying failure.",
                    "untestable",
                    None,
                    CAMPAIGN,
                ),
                _fact(
                    "hypothesis.h2",
                    "H2 minimality was untestable because there were no paired qualifying findings.",
                    "untestable",
                    None,
                    CAMPAIGN,
                ),
                _fact(
                    "hypothesis.h3",
                    "H3 validity was supported under its predeclared noninferiority rule.",
                    "supported",
                    None,
                    CAMPAIGN,
                ),
                _fact(
                    "hypothesis.no_censoring",
                    "Budget-censored discovery costs were not reported as observed costs.",
                    True,
                    None,
                    CAMPAIGN,
                ),
            ),
            self._citations(CAMPAIGN),
            _standard_limitations(),
        )

    def _query_claim_boundary(self) -> ToolResult:
        return ToolResult(
            "claim_boundary",
            "Permitted interpretation and claim boundary",
            self.source_mode,
            (
                _fact(
                    "claim.supported",
                    "The evidence supports a narrower claim of higher eligible-proposal yield for constrained Bayesian search in development.",
                    "eligible-proposal yield",
                    None,
                    CAMPAIGN,
                ),
                _fact(
                    "claim.not_discovery",
                    "The evidence does not establish better failure discovery or smaller failure-inducing mutations.",
                    False,
                    None,
                    CAMPAIGN,
                ),
                _fact(
                    "claim.not_waymo",
                    "PlanMargin does not evaluate the production Waymo Driver.",
                    False,
                    None,
                    CAMPAIGN,
                ),
                _fact(
                    "claim.development",
                    "The result covers ten selected WOMD training scenarios and is not a broad statistical generalization.",
                    "development only",
                    None,
                    CAMPAIGN,
                ),
                _fact(
                    "claim.held_out",
                    "No held-out comparative WOMD evaluation was run.",
                    False,
                    None,
                    HELD_OUT,
                ),
            ),
            self._citations(CAMPAIGN, HELD_OUT),
            _standard_limitations(),
        )

    def _query_beam_pipeline(self) -> ToolResult:
        return ToolResult(
            "beam_pipeline",
            "Beam-to-Parquet-to-DuckDB integration evidence",
            self.source_mode,
            (
                _fact(
                    "beam.records",
                    "The verified integration consumed evidence derived from 7,796 WOMD records.",
                    7796,
                    "records",
                    BEAM,
                ),
                _fact(
                    "beam.events",
                    "The pipeline retained 265 accepted feature events.",
                    265,
                    "events",
                    BEAM,
                ),
                _fact(
                    "beam.shards",
                    "The run consumed 16 sealed source-shard checkpoints.",
                    16,
                    "source shards",
                    BEAM,
                ),
                _fact(
                    "beam.partitions",
                    "All 8 deterministic partitions were reconciled.",
                    8,
                    "partitions",
                    BEAM,
                ),
                _fact(
                    "beam.integrity",
                    "Every published pipeline integrity gate passed.",
                    True,
                    None,
                    BEAM,
                ),
                _fact(
                    "beam.held_out",
                    "The pipeline did not open held-out data.",
                    False,
                    None,
                    BEAM,
                ),
            ),
            self._citations(BEAM),
            (
                "This verifies a bounded local dataflow, not distributed throughput.",
                "Pipeline evidence does not establish planner safety or failure discovery.",
                "Feature rows and source identities remain ignored local artifacts.",
            ),
        )


class LocalEvidenceTools:
    """Execute the same closed aggregate queries over verified ignored artifacts."""

    source_mode: Literal["real_local_redacted"] = "real_local_redacted"

    def __init__(self, repository: LocalEvidenceRepository) -> None:
        self._repository = repository

    def execute(self, query_id: str) -> ToolResult:
        if query_id == "beam_pipeline":
            return PublicEvidenceTools().execute(query_id)
        if query_id == "campaign_overview":
            campaign = self._repository.campaign()
            methods = self._repository.methods()
            finding_count = sum(row["qualifying_failure_count"] for row in methods)
            facts = (
                _fact(
                    "campaign.rollouts",
                    f"The verified local campaign executed {campaign['total_physical_rollouts']:,} physical rollouts.",
                    campaign["total_physical_rollouts"],
                    "rollouts",
                    "local-campaign",
                ),
                _fact(
                    "campaign.steps",
                    f"The verified local campaign executed {campaign['waymax_rollout_steps']:,} Waymax rollout steps.",
                    campaign["waymax_rollout_steps"],
                    "steps",
                    "local-campaign",
                ),
                _fact(
                    "campaign.findings",
                    f"The verified local campaign contains {finding_count} qualifying findings.",
                    finding_count,
                    "findings",
                    "local-campaign",
                ),
                _fact(
                    "campaign.held_out",
                    "The local evidence contract records that no held-out comparative campaign ran.",
                    False,
                    None,
                    "local-campaign",
                ),
            )
        elif query_id == "method_comparison":
            methods = {row["method"]: row for row in self._repository.methods()}
            hypotheses = {
                row["hypothesis"]: row for row in self._repository.hypotheses()
            }
            random = methods["random"]
            bayesian = methods["bayesian"]
            h3 = hypotheses["h3_validity"]
            facts = (
                _fact(
                    "method.random_valid_rate",
                    f"Random search had a {random['support_and_pipeline_valid_rate'] * 100:.4f}% support-and-pipeline-valid rate.",
                    random["support_and_pipeline_valid_rate"],
                    "proportion",
                    "local-methods",
                ),
                _fact(
                    "method.bayesian_valid_rate",
                    f"Constrained Bayesian search had a {bayesian['support_and_pipeline_valid_rate'] * 100:.4f}% support-and-pipeline-valid rate.",
                    bayesian["support_and_pipeline_valid_rate"],
                    "proportion",
                    "local-methods",
                ),
                _fact(
                    "method.valid_rate_delta",
                    f"The sealed H3 row records a Bayesian-minus-random difference of {h3['bayesian_minus_random_valid_rate'] * 100:.4f} percentage points.",
                    h3["bayesian_minus_random_valid_rate"],
                    "proportion",
                    "local-hypotheses",
                ),
                _fact(
                    "method.findings",
                    "Random search produced "
                    f"{random['qualifying_failure_count']} qualifying findings and "
                    "constrained Bayesian search produced "
                    f"{bayesian['qualifying_failure_count']}.",
                    "random="
                    f"{random['qualifying_failure_count']},bayesian="
                    f"{bayesian['qualifying_failure_count']}",
                    None,
                    "local-methods",
                ),
                _fact(
                    "method.h3",
                    f"The frozen H3 validity hypothesis status is {h3['status']}.",
                    h3["status"],
                    None,
                    "local-hypotheses",
                ),
            )
        elif query_id == "hypothesis_decisions":
            facts = tuple(
                _fact(
                    f"hypothesis.{row['hypothesis'].split('_', maxsplit=1)[0].lower()}",
                    f"{row['hypothesis'].split('_', maxsplit=1)[0].upper()} has frozen status {row['status']}.",
                    row["status"],
                    None,
                    "local-hypotheses",
                )
                for row in self._repository.hypotheses()
            )
        elif query_id == "claim_boundary":
            return PublicEvidenceTools().execute(query_id)
        else:
            raise ValueError(f"Query is not allowlisted: {query_id}")

        citations = tuple(
            Citation(
                item,
                "Verified ignored local aggregate query",
                "[ignored local artifact]",
                self._local_seal(),
            )
            for item in sorted({fact.citation_id for fact in facts})
        )
        return ToolResult(
            query_id,
            "Verified local aggregate evidence",
            self.source_mode,
            facts,
            citations,
            _standard_limitations(),
        )

    def _local_seal(self) -> str:
        manifest = self._repository.analytics_manifest
        if not isinstance(manifest, dict):
            raise ValueError("Local evidence repository has not been opened")
        seal = manifest.get("manifest_sha256")
        if not isinstance(seal, str) or len(seal) != 64:
            raise ValueError("Local analytics manifest seal is unavailable")
        return seal


def _standard_limitations() -> tuple[str, ...]:
    return (
        "This is development evidence, not a broad statistical generalization.",
        "PlanMargin does not evaluate the production Waymo Driver.",
        "No held-out comparative WOMD evaluation was run.",
    )


QUERY_LABELS = {
    "campaign_overview": "campaign summary",
    "method_comparison": "method comparison",
    "hypothesis_decisions": "hypothesis decisions",
    "claim_boundary": "claim boundary",
    "beam_pipeline": "data-pipeline evidence",
}


def classify_question(question: str) -> str:
    """Map a bounded natural-language question to one closed query identifier."""
    if len(question) > MAX_QUESTION_CHARACTERS:
        raise ValueError(f"Question exceeds {MAX_QUESTION_CHARACTERS} characters")
    normalized = " ".join(question.split()).lower()
    if not normalized:
        raise ValueError("Question must not be empty")
    if any(ord(character) < 32 for character in question if character not in "\t\n\r"):
        raise ValueError("Question contains unsupported control characters")

    routes = (
        (
            "beam_pipeline",
            ("beam", "parquet", "duckdb", "pipeline", "shard", "dataflow"),
        ),
        (
            "hypothesis_decisions",
            ("hypothesis", "hypotheses", " h1", " h2", " h3", "untestable"),
        ),
        (
            "claim_boundary",
            (
                "claim",
                "conclude",
                "prove",
                "production",
                "waymo driver",
                "held-out",
                "held out",
                "safe",
                "limitation",
                "generalize",
            ),
        ),
        (
            "method_comparison",
            (
                "random",
                "bayesian",
                "method",
                "valid rate",
                "hypervolume",
                "better",
                "compare",
            ),
        ),
        (
            "campaign_overview",
            (
                "campaign",
                "overall",
                "summary",
                "result",
                "happened",
                "rollout",
                "proposal",
                "finding",
            ),
        ),
    )
    for query_id, phrases in routes:
        if any(phrase in f" {normalized}" for phrase in phrases):
            return query_id
    allowed = ", ".join(QUERY_LABELS.values())
    raise ValueError(
        f"Question is outside the allowlisted scope. Ask about: {allowed}."
    )


OFFLINE_DRAFTS = {
    "campaign_overview": ExplanationDraft(
        summary="The frozen development campaign completed as designed and found no qualifying failures.",
        interpretation="The absence of findings keeps the discovery questions unresolved; the completed run is still useful evidence about feasibility, cost, and the tested search space.",
        cited_fact_ids=["campaign.findings", "campaign.rollouts", "campaign.held_out"],
        limitation="Treat this as bounded development evidence because held-out evaluation has not been authorized.",
    ),
    "method_comparison": ExplanationDraft(
        summary="Constrained Bayesian search produced a higher yield of eligible proposals, while neither method discovered a qualifying failure.",
        interpretation="That supports the frozen validity result but does not support a claim of better failure discovery or mutation minimality.",
        cited_fact_ids=[
            "method.random_valid_rate",
            "method.bayesian_valid_rate",
            "method.valid_rate_delta",
            "method.findings",
            "method.h3",
        ],
        limitation="The comparison is restricted to the frozen development campaign and its tested budget.",
    ),
    "hypothesis_decisions": ExplanationDraft(
        summary="The validity hypothesis was supported, while efficiency and minimality remained untestable.",
        interpretation="The latter decisions follow from the absence of qualifying findings, so censored discovery costs were not reinterpreted as observed outcomes.",
        cited_fact_ids=[
            "hypothesis.h1",
            "hypothesis.h2",
            "hypothesis.h3",
            "hypothesis.no_censoring",
        ],
        limitation="An untestable decision is not evidence for or against the associated hypothesis.",
    ),
    "claim_boundary": ExplanationDraft(
        summary="The defensible result is about eligible-proposal yield in a bounded development study.",
        interpretation="It is not evidence of production-system safety, superior failure discovery, or broad generalization.",
        cited_fact_ids=[
            "claim.supported",
            "claim.not_discovery",
            "claim.not_waymo",
            "claim.development",
            "claim.held_out",
        ],
        limitation="Keep every public description inside the frozen claim boundary.",
    ),
    "beam_pipeline": ExplanationDraft(
        summary="The Beam integration demonstrates a restartable and reconciled local feature-dataflow responsibility.",
        interpretation="Its evidence covers bounded ingestion, stable partitioning, and DuckDB reconciliation; it does not measure distributed scale or planner quality.",
        cited_fact_ids=[
            "beam.records",
            "beam.events",
            "beam.shards",
            "beam.partitions",
            "beam.integrity",
            "beam.held_out",
        ],
        limitation="This is pipeline verification rather than experimental outcome evidence.",
    ),
}


class OfflineProvider:
    provider_id = "offline_deterministic"

    def explain(self, result: ToolResult) -> ExplanationDraft:
        draft = OFFLINE_DRAFTS[result.query_id]
        available = {fact.fact_id for fact in result.facts}
        cited = [fact_id for fact_id in draft.cited_fact_ids if fact_id in available]
        if not cited:
            cited = [result.facts[0].fact_id]
        return draft.model_copy(update={"cited_fact_ids": cited})


class GeminiProvider:
    """Optional hosted explainer that receives public aggregate facts only."""

    provider_id = "gemini_public_aggregate"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        confirmed_free_tier: bool,
        client_factory: Callable[[str], Any] | None = None,
    ) -> None:
        if not confirmed_free_tier:
            raise ValueError(
                "Gemini requires explicit confirmation of a free-tier project"
            )
        if not api_key:
            raise ValueError("GEMINI_API_KEY is required for Gemini mode")
        if not re.fullmatch(r"gemini-[a-z0-9.-]+", model):
            raise ValueError("Gemini model name is invalid")
        self._api_key = api_key
        self._model = model
        self._client_factory = client_factory or _google_client

    def explain(self, result: ToolResult) -> ExplanationDraft:
        if result.source_mode != "public_aggregate":
            raise ValueError("Gemini mode accepts public aggregate evidence only")
        prompt_packet = {
            "instruction": (
                "Explain only the supplied PlanMargin evidence. Do not calculate, "
                "copy, or spell out numeric metrics; those render separately. Do not "
                "claim safety, production Waymo Driver evaluation, held-out evidence, "
                "or causality. Cite only supplied fact IDs."
            ),
            "query_id": result.query_id,
            "facts": [
                {"fact_id": fact.fact_id, "statement": fact.statement}
                for fact in result.facts
            ],
            "limitations": list(result.limitations),
        }
        client = self._client_factory(self._api_key)
        try:
            interaction = client.interactions.create(
                model=self._model,
                input=json.dumps(prompt_packet, sort_keys=True, separators=(",", ":")),
                response_format={
                    "type": "text",
                    "mime_type": "application/json",
                    "schema": GEMINI_RESPONSE_SCHEMA,
                },
            )
            draft = ExplanationDraft.model_validate_json(interaction.output_text)
        except Exception as error:
            raise RuntimeError(
                "Gemini returned an invalid structured explanation"
            ) from error
        finally:
            close = getattr(client, "close", None)
            if callable(close):
                close()
        _validate_provider_draft(draft, result)
        _validate_hosted_claims(draft)
        return draft


def _google_client(api_key: str) -> Any:
    try:
        from google import genai
    except ImportError as error:
        raise RuntimeError(
            "Gemini support is not installed; run `uv sync --extra assistant`"
        ) from error
    return genai.Client(api_key=api_key, http_options={"timeout": 20_000})


def _validate_provider_draft(draft: ExplanationDraft, result: ToolResult) -> None:
    available = {fact.fact_id for fact in result.facts}
    if len(draft.cited_fact_ids) != len(set(draft.cited_fact_ids)):
        raise ValueError("Provider returned duplicate fact citations")
    if not set(draft.cited_fact_ids).issubset(available):
        raise ValueError("Provider cited facts outside the tool result")
    if any(
        not text.strip()
        for text in (draft.summary, draft.interpretation, draft.limitation)
    ):
        raise ValueError("Provider returned an empty explanation field")
    generated = " ".join((draft.summary, draft.interpretation, draft.limitation))
    if re.search(r"\d", generated):
        raise ValueError("Provider prose may not generate numeric metrics")


def _validate_hosted_claims(draft: ExplanationDraft) -> None:
    generated = " ".join((draft.summary, draft.interpretation, draft.limitation))
    prohibited_words = (
        r"\b(?:safe|safer|safest|safety|certif\w*|guarantee\w*|production|"
        r"held[ -]?out|caus\w*)\b"
    )
    number_words = (
        r"\b(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|"
        r"twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|"
        r"twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|"
        r"thousand|million|billion|percent|percentage)\b"
    )
    if re.search(prohibited_words, generated, flags=re.IGNORECASE):
        raise ValueError("Provider prose exceeds the frozen claim boundary")
    if re.search(number_words, generated, flags=re.IGNORECASE):
        raise ValueError("Provider prose may not spell out numeric metrics")


def _result_dict(result: ToolResult) -> dict[str, Any]:
    return {
        "query_id": result.query_id,
        "title": result.title,
        "source_mode": result.source_mode,
        "facts": [fact.__dict__ for fact in result.facts],
        "citations": [citation.__dict__ for citation in result.citations],
    }


def public_catalog_fingerprint() -> str:
    """Seal the ordered allowlist, facts, citations, and limitations."""
    tools = PublicEvidenceTools()
    payload = []
    for query_id in QUERY_LABELS:
        result = tools.execute(query_id)
        payload.append(
            {**_result_dict(result), "limitations": list(result.limitations)}
        )
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def answer_question(
    question: str,
    *,
    tools: EvidenceTools,
    provider: ExplanationProvider | None = None,
) -> dict[str, Any]:
    """Execute exactly one deterministic tool before asking an explainer."""
    query_id = classify_question(question)
    result = tools.execute(query_id)
    selected_provider = provider or OfflineProvider()
    draft = selected_provider.explain(result)
    _validate_provider_draft(draft, result)
    cited = set(draft.cited_fact_ids)
    citation_ids = sorted(
        {fact.citation_id for fact in result.facts if fact.fact_id in cited}
    )
    return {
        "$schema": SCHEMA_URI,
        "record_type": RECORD_TYPE,
        "schema_version": SCHEMA_VERSION,
        "status": "answered",
        "question": {
            "sha256": hashlib.sha256(question.encode("utf-8")).hexdigest(),
            "query_id": query_id,
            "query_label": QUERY_LABELS[query_id],
        },
        "provider": {
            "id": selected_provider.provider_id,
            "model": getattr(selected_provider, "_model", None),
            "role": "explanation_only",
        },
        "tool_result": _result_dict(result),
        "explanation": {
            **draft.model_dump(),
            "citation_ids": citation_ids,
        },
        "privacy": {
            "raw_question_persisted": False,
            "raw_question_sent_to_provider": False,
            "private_data_sent_to_provider": False,
            "provider_input_scope": (
                "none"
                if selected_provider.provider_id == "offline_deterministic"
                else "public_aggregate_tool_result_only"
            ),
        },
        "limitations": list(result.limitations),
    }


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--question", required=True)
    parser.add_argument("--source", choices=("public", "local"), default="public")
    parser.add_argument("--provider", choices=("offline", "gemini"), default="offline")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument(
        "--confirm-free-tier",
        action="store_true",
        help="Confirm the configured Gemini project is on Google's free tier.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = _parse_args(argv)
    try:
        if args.source == "local":
            if args.provider == "gemini":
                raise ValueError("Gemini cannot be combined with local evidence")
            from planmargin import evidence_api

            repository = evidence_api.EvidenceRepository(
                evidence_api.EvidencePaths.from_root(args.root)
            )
            repository.open()
            tools: EvidenceTools = LocalEvidenceTools(repository)
        else:
            tools = PublicEvidenceTools()

        if args.provider == "gemini":
            provider: ExplanationProvider = GeminiProvider(
                api_key=os.environ.get("GEMINI_API_KEY", ""),
                model=args.model,
                confirmed_free_tier=args.confirm_free_tier,
            )
        else:
            provider = OfflineProvider()
        response = answer_question(args.question, tools=tools, provider=provider)
    except (RuntimeError, ValueError) as error:
        raise SystemExit(str(error)) from error
    print(json.dumps(response, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
