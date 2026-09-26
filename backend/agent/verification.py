"""Grounding verification pass - checks whether each claim's cited
sourceIds actually support that claim, instead of trusting that the
generating agent attached them correctly.

Every strategy agent already tags claims with sourceIds and sanitizes them
against the real source list (structured_output.sanitize_source_ids) - but
sanitizing only confirms a cited id *exists*, not that the source text
actually backs the claim. A model can (and does) attach a plausible-looking
sourceId to a claim the source doesn't really support. This pass catches
that specific failure mode with one extra, cheap LLM call per section: it
never generates new content, only reads back claims the section already
produced and decides whether each one holds up against its own citation.

Fails open on any error (network, quota, bad JSON) - a verification
failure means "we couldn't double-check this," not "the claim is wrong",
so the original claims (with their original sourceIds) are returned
unchanged rather than treating a verification hiccup as a reason to strip
citations that were never actually checked.
"""

import logging

from crewai import Agent, Crew, Process, Task

from .llm import get_llm, kickoff_with_fallback
from .prompts.loader import load_prompt
from .structured_output import compact_json, extract_json_object

logger = logging.getLogger(__name__)

_MAX_CLAIMS_PER_PASS = 20


def _valid_shape(value: dict) -> bool:
    results = value.get("results")
    if not isinstance(results, list):
        return False
    return all(
        isinstance(item, dict) and isinstance(item.get("index"), int) and isinstance(item.get("supported"), bool)
        for item in results
    )


def _build_crew(idea: str, claims_text: str, model: str) -> Crew:
    checker = Agent(
        role="Grounding Fact-Checker",
        goal="Confirm or reject each claim strictly against its own cited source text.",
        backstory=load_prompt("verification_system"),
        llm=get_llm(max_tokens=400, model=model),
        verbose=False,
    )
    task = Task(
        description=load_prompt("verification_task", idea=idea, claims=claims_text),
        expected_output=load_prompt("verification_output"),
        agent=checker,
    )
    return Crew(agents=[checker], tasks=[task], process=Process.sequential, verbose=False)


def verify_claims(
    idea: str,
    claims: list[dict],
    source_snippets: dict[str, str],
    allow_local: bool = False,
) -> list[bool]:
    """`claims` is a flat list of {"text": str, "sourceIds": [str]} - the
    same shape every agent already builds internally. Returns a parallel
    list of booleans (True = supported, keep the citation); a claim with no
    sourceIds is always True, since there's nothing cited to check.

    Only the first _MAX_CLAIMS_PER_PASS cited claims are checked per call to
    keep this a small, cheap request - every section already caps its own
    claim counts well under that (see each agent's _MAX_* constants), so
    this is a safety bound, not a limit expected to bite in practice.
    """
    indices_to_check = [i for i, claim in enumerate(claims) if claim.get("sourceIds")]
    if not indices_to_check:
        return [True] * len(claims)

    checked = indices_to_check[:_MAX_CLAIMS_PER_PASS]
    payload = [
        {
            "index": i,
            "claim": claims[i]["text"],
            "sourceText": " ".join(
                source_snippets.get(sid, "") for sid in claims[i]["sourceIds"] if sid in source_snippets
            ),
        }
        for i in checked
    ]

    try:
        output = kickoff_with_fallback(
            lambda model: _build_crew(idea, compact_json(payload, max_chars=3000), model),
            allow_local=allow_local,
            validate=lambda o: extract_json_object(o.raw, _valid_shape) is not None,
        )
        data = extract_json_object(output.raw, _valid_shape)
        if data is None:
            raise ValueError("Verification pass did not return a valid result.")
        supported_by_index = {item["index"]: item["supported"] for item in data["results"]}
    except Exception:
        logger.warning("Verification pass unavailable, keeping claims as originally cited", exc_info=True)
        return [True] * len(claims)

    # Unchecked claims (no sourceIds, or beyond _MAX_CLAIMS_PER_PASS) default
    # to True - "not checked" is not the same as "unsupported".
    return [supported_by_index.get(i, True) for i in range(len(claims))]


def strip_unsupported(claims: list[dict], supported: list[bool]) -> list[dict]:
    """Clears sourceIds on any claim verify_claims marked unsupported,
    rather than deleting the claim - it's still a real (if now honestly
    inferred-not-cited) part of the analysis, the same way a claim the
    generating agent itself left uncited already is.
    """
    return [
        {**claim, "sourceIds": []} if not ok else claim
        for claim, ok in zip(claims, supported)
    ]
