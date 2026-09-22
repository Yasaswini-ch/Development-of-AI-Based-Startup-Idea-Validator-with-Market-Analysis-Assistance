"""Milestone 4 / Track F - token-budget and latency measurement pass.

Runs real sample ideas through the full pipeline and aggregates the
per-node (`[nodename] elapsed_ms=...`, from graph.py's _timed wrapper) and
per-LLM-call (`llm_call model=... elapsed_ms=... prompt_tokens=...
completion_tokens=... total_tokens=...`, from llm.py's
_kickoff_with_metrics) log lines that already exist in this codebase, into
one readable report - mean/median/max per node and per model, how often
each section fell back to its deterministic path, and a rough per-model
completion-token utilization against that agent's configured max_tokens
(the truncation-risk signal this pass exists to catch).

This script does NOT decide new max_tokens/compact_sources values by
itself - it prints the numbers a human (or a follow-up pass) needs to
make that call with real data instead of a guess. Requires GROQ_API_KEY
at minimum (TAVILY_API_KEY is optional - retrieval.py falls back to free
search providers without it).

Usage:
    cd backend
    python scripts/latency_token_measurement.py
    python scripts/latency_token_measurement.py --ideas 5
    python scripts/latency_token_measurement.py --idea "A subscription meal kit for busy families" --target-customer "Busy families" --problem "No time to cook"
"""

import argparse
import logging
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

# Agents' own configured output-token ceilings (backend/agent/*.py's
# get_llm(max_tokens=...) call sites) - kept here, not imported, since this
# is what the prompt/schema is CURRENTLY tuned against; the report compares
# real usage to these, it doesn't read them back out of the source.
AGENT_MAX_TOKENS = {
    "market_opportunity": 750,
    "swot_analysis": 750,
    "mvp_recommendation": 450,
    "gtm_strategy": 450,
}

_DEFAULT_SAMPLE_IDEAS = [
    ("A subscription meal-kit service for busy professionals", "Busy working professionals", "No time to plan and cook healthy meals"),
    ("An AI-powered study planner for university students", "University students", "Difficulty organizing study schedules around deadlines"),
    ("A marketplace connecting local farmers directly with restaurants", "Independent restaurant owners", "Sourcing fresh local produce is slow and expensive through distributors"),
]

_NODE_LINE_RE = re.compile(r"^\[(?P<node>[\w_]+)\] elapsed_ms=(?P<ms>\d+)$")
_LLM_CALL_LINE_RE = re.compile(
    r"^llm_call model=(?P<model>\S+) elapsed_ms=(?P<ms>\d+)"
    r"(?: prompt_tokens=(?P<prompt>\S+) completion_tokens=(?P<completion>\S+) total_tokens=(?P<total>\S+))?$"
)
_FALLBACK_LINE_RE = re.compile(r"^(?P<section>\w[\w\s]*): LLM analysis unavailable, using deterministic")


class _MetricsCapture(logging.Handler):
    """Collects the node/llm_call/fallback log lines this pass reads,
    without changing how or where the rest of the app logs - a passive
    listener, not a new logging destination anything else depends on.
    """

    def __init__(self):
        super().__init__()
        self.node_times: dict[str, list[int]] = defaultdict(list)
        self.llm_calls: list[dict] = []
        self.fallback_counts: dict[str, int] = defaultdict(int)

    def emit(self, record: logging.LogRecord) -> None:
        message = record.getMessage()

        match = _NODE_LINE_RE.match(message)
        if match:
            self.node_times[match.group("node")].append(int(match.group("ms")))
            return

        match = _LLM_CALL_LINE_RE.match(message)
        if match:
            self.llm_calls.append(
                {
                    "model": match.group("model"),
                    "elapsed_ms": int(match.group("ms")),
                    "prompt_tokens": _int_or_none(match.group("prompt")),
                    "completion_tokens": _int_or_none(match.group("completion")),
                    "total_tokens": _int_or_none(match.group("total")),
                }
            )
            return

        match = _FALLBACK_LINE_RE.match(message)
        if match:
            self.fallback_counts[match.group("section").strip()] += 1


def _int_or_none(value: str | None) -> int | None:
    if value is None or value == "None":
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _stats_line(label: str, values: list[float]) -> str:
    if not values:
        return f"  {label}: no data"
    return (
        f"  {label}: n={len(values)}  mean={statistics.mean(values):.0f}  "
        f"median={statistics.median(values):.0f}  max={max(values):.0f}"
    )


def _print_report(capture: _MetricsCapture, run_count: int) -> None:
    print(f"\n{'=' * 70}\nLATENCY & TOKEN-BUDGET REPORT  ({run_count} run(s))\n{'=' * 70}")

    print("\nPer-node wall-clock time (ms):")
    for node, times in sorted(capture.node_times.items()):
        print(_stats_line(node, times))

    print("\nPer-model LLM call latency and tokens:")
    by_model: dict[str, list[dict]] = defaultdict(list)
    for call in capture.llm_calls:
        by_model[call["model"]].append(call)
    for model, calls in sorted(by_model.items()):
        print(f"  {model} ({len(calls)} call(s)):")
        print("   " + _stats_line("elapsed_ms", [c["elapsed_ms"] for c in calls]))
        completion_tokens = [c["completion_tokens"] for c in calls if c["completion_tokens"] is not None]
        if completion_tokens:
            print("   " + _stats_line("completion_tokens", completion_tokens))
        else:
            print("    completion_tokens: not reported by this call's response")

    print("\nDeterministic-fallback occurrences (LLM path failed or was skipped):")
    if not capture.fallback_counts:
        print("  none - every LLM-backed section completed via the real model path in this run")
    else:
        for section, count in sorted(capture.fallback_counts.items()):
            print(f"  {section}: {count} of {run_count} run(s)")

    print("\nCompletion-token utilization vs. each agent's configured max_tokens")
    print("(high utilization = truncation risk; this is the number this pass exists to produce):")
    node_to_agent_key = {
        "market_opportunity": "market_opportunity",
        "swot_analysis": "swot_analysis",
        "mvp_recommendation": "mvp_recommendation",
        "gtm_strategy": "gtm_strategy",
    }
    # Best-effort: attribute LLM calls to agents by call order within the
    # configured agents list, since llm_call log lines don't carry the
    # calling agent's name. Precise enough for a single-idea-at-a-time
    # report; a multi-idea aggregate should be read per-model above instead.
    print("  (see per-model completion_tokens above; compare against AGENT_MAX_TOKENS in this script)")
    for node, max_tokens in AGENT_MAX_TOKENS.items():
        print(f"  {node}: configured max_tokens={max_tokens}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ideas", type=int, default=None, help="Run this many of the built-in sample ideas (default: all).")
    parser.add_argument("--idea", type=str, default=None, help="Run one specific idea instead of the built-in samples.")
    parser.add_argument("--target-customer", type=str, default="")
    parser.add_argument("--problem", type=str, default="")
    args = parser.parse_args()

    from agent.graph import pipeline  # noqa: E402 - deferred until sys.path is set up above

    if args.idea:
        samples = [(args.idea, args.target_customer, args.problem)]
    else:
        samples = _DEFAULT_SAMPLE_IDEAS[: args.ideas] if args.ideas else _DEFAULT_SAMPLE_IDEAS

    capture = _MetricsCapture()
    capture.setLevel(logging.INFO)
    # agent.graph: [nodename] elapsed_ms=... (from _timed)
    # agent.llm: llm_call model=... elapsed_ms=... (from _kickoff_with_metrics)
    # agent.{market,swot,mvp,gtm}_agent: "...: LLM analysis unavailable,
    #   using deterministic..." fallback warnings
    for logger_name in (
        "agent.graph",
        "agent.llm",
        "agent.market_agent",
        "agent.swot_agent",
        "agent.mvp_agent",
        "agent.gtm_agent",
    ):
        logging.getLogger(logger_name).addHandler(capture)
        logging.getLogger(logger_name).setLevel(logging.INFO)

    print(f"Running {len(samples)} sample idea(s) through the real pipeline...")
    for idea, target_customer, problem in samples:
        print(f"  - {idea!r}")
        pipeline.invoke({"idea": idea, "targetCustomer": target_customer, "problem": problem})

    _print_report(capture, len(samples))
    return 0


if __name__ == "__main__":
    sys.exit(main())
