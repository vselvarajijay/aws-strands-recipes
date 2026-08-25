"""Recipe 13 — chaos testing: does the agent survive when its tools fail?

Recipes 04-07 evaluated agents under *ideal* conditions — every tool returns
clean data on demand. Production is not ideal. APIs time out, networks drop,
services return truncated garbage. Chaos testing asks the questions those recipes
can't: when a tool fails, does the agent fail *gracefully*? Does it tell the user
clearly? Does it still deliver the part of the goal it can?

The trick is that you inject failures WITHOUT touching your agent code. A
``ChaosPlugin`` hooks the agent's tool calls and, per test case, either cancels a
call (Timeout, NetworkError, ...) or corrupts its response (TruncateFields, ...).
Which tool fails, and how, is data — a `ChaosCase` — not a code change.

    ChaosCase        a Case plus an `effects` map: {tool_name: [failure]}
    ChaosPlugin      intercepts tool calls and applies the active case's effects
    ChaosExperiment  sets the active case, runs the task, then the evaluators
    chaos evaluators LLM judges tuned for failure behavior (below)

The agent under test answers weather questions using TWO tools. We ask for
current weather AND a forecast, then break ONE of the two tools — so a resilient
agent can still deliver half the answer and say clearly what it couldn't get.
That partial-success shape is exactly what the three resilience evaluators score:

    FailureCommunicationEvaluator  was the failure explained clearly + actionably?
    PartialCompletionEvaluator     how much of the goal survived the failure?
    RecoveryStrategyEvaluator      did it retry / route around / degrade sensibly?

Each is an LLM judge, so — like recipes 04/06/07 — we hand every one the SAME
shared model factory. Left to their defaults these evaluators reach for Bedrock;
passing `model=build_model()` keeps the whole recipe on one ANTHROPIC_API_KEY.

Run from the repo root:

    uv run recipes/13-eval-chaos/main.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from strands import Agent, tool
from strands_evals import Case
from strands_evals.chaos import (
    ChaosCase,
    ChaosPlugin,
    CorruptValues,
    NetworkError,
    Timeout,
)
from strands_evals.chaos import ChaosExperiment
from strands_evals.eval_task_handler import TracedHandler, eval_task
from strands_evals.evaluators.chaos import (
    FailureCommunicationEvaluator,
    PartialCompletionEvaluator,
    RecoveryStrategyEvaluator,
)

# Make the repo root importable so `shared` resolves when run directly.
sys.path.append(str(Path(__file__).resolve().parents[2]))

from shared.model import build_model  # noqa: E402


# --- Tools the agent can use ------------------------------------------------
# Two tools returning canned data — no external services. Under normal conditions
# both succeed; the chaos plugin decides at runtime whether a given call fails.
# The tool NAMES (get_weather, get_forecast) are the keys the effect maps target.


@tool
def get_weather(city: str) -> str:
    """Get the CURRENT weather for a city.

    Args:
        city: The city to look up, e.g. "Seattle".
    """
    return f'{{"city": "{city}", "temp_f": 72, "condition": "sunny"}}'


@tool
def get_forecast(city: str) -> str:
    """Get a 3-day weather FORECAST for a city.

    Args:
        city: The city to look up, e.g. "Seattle".
    """
    return (
        f'{{"city": "{city}", "forecast": ['
        '{"day": "Mon", "high": 70, "low": 55}, '
        '{"day": "Tue", "high": 68, "low": 54}, '
        '{"day": "Wed", "high": 73, "low": 56}]}'
    )


TOOLS = [get_weather, get_forecast]

SYSTEM_PROMPT = """\
You are a helpful weather assistant. Use get_weather for current conditions and
get_forecast for the multi-day outlook. If a tool fails, do NOT invent data:
tell the user plainly what you could not retrieve, still give them whatever you
*did* get, and suggest a sensible next step (e.g. try again shortly)."""


# --- The task under test ----------------------------------------------------
# Per the ChaosExperiment contract, the task body contains ZERO chaos concepts.
# It just builds the agent with plugins=[chaos]; the experiment has already set
# the active ChaosCase, and the plugin reads the failures from it.
#
# The @eval_task(TracedHandler()) wrapper does two jobs the resilience judges
# need. First, it auto-runs the returned Agent on case.input. Second — the reason
# it's required here and not in recipes 04-07 — it captures the agent's execution
# as OpenTelemetry spans and maps them into a Session. The chaos evaluators are
# TRACE-level: they grade the whole trajectory (which tool failed, how the agent
# reacted), not just the final text, so they need that Session, not a bare string.
#
# trace_attributes ties the spans to this case's session_id so the handler maps
# the right trace. TracedHandler shares one exporter, so run serially (max_workers=1).
chaos = ChaosPlugin()


@eval_task(TracedHandler())
def run_weather_agent(case: ChaosCase) -> Agent:
    return Agent(
        model=build_model(),
        system_prompt=SYSTEM_PROMPT,
        tools=TOOLS,
        plugins=[chaos],
        callback_handler=None,
        trace_attributes={"session.id": case.session_id},
    )


# --- Cases: one clean goal, then break it three different ways ---------------
# Every request asks for BOTH current weather and the forecast, so a single-tool
# failure leaves a partial goal to salvage — the interesting case for resilience.
BASE_CASES = [
    Case[str, str](
        name="seattle",
        input="What's the weather in Seattle right now, and the 3-day forecast?",
    ),
    Case[str, str](
        name="tokyo",
        input="Give me the current conditions in Tokyo plus the next 3 days.",
    ),
]

# Each effect map names ONE tool and ONE failure for it. (A ChaosCase allows only
# one effect per tool; test more failure modes by adding more maps, not more
# effects.) The three here span the important families:
#   - Timeout / NetworkError are PRE-hook: the tool call is cancelled outright,
#     so the agent sees a hard error and must react to a missing result.
#   - CorruptValues is POST-hook: the call SUCCEEDS but its JSON fields are
#     replaced with garbage. This is the subtler, nastier test — there's no
#     exception to catch, so it probes whether the agent notices bad data instead
#     of confidently relaying nonsense. (TruncateFields/RemoveFields are the other
#     post-hook effects; all three operate on the tool's parsed JSON fields.)
EFFECT_MAPS = {
    "forecast_timeout": {"tool_effects": {"get_forecast": [Timeout()]}},
    "weather_network_error": {"tool_effects": {"get_weather": [NetworkError()]}},
    "weather_corrupted": {"tool_effects": {"get_weather": [CorruptValues(corrupt_ratio=1.0)]}},
}

# expand() takes the Cartesian product: 2 base cases x 3 effect maps = 6 chaos
# cases. include_no_effect_baseline adds a clean, no-failure variant per base
# case (2 more) so you can compare behavior under chaos against the happy path.
CHAOS_CASES = ChaosCase.expand(
    BASE_CASES,
    EFFECT_MAPS,
    include_no_effect_baseline=True,
)


def main() -> None:
    # All three resilience judges share one model. Without model=..., each would
    # default to Bedrock; this keeps the recipe on a single ANTHROPIC_API_KEY.
    judge = build_model()
    evaluators = [
        FailureCommunicationEvaluator(model=judge),
        PartialCompletionEvaluator(model=judge),
        RecoveryStrategyEvaluator(model=judge),
    ]

    experiment = ChaosExperiment(cases=CHAOS_CASES, evaluators=evaluators)

    print(f"Running chaos evaluation over {len(CHAOS_CASES)} cases...\n" + "=" * 60)
    # run_evaluations is the sync entry point (it drives run_evaluations_async
    # with max_workers=1 under the hood). Chaos cases share a per-case ContextVar,
    # so keep concurrency low — serial execution is the safe default.
    report = experiment.run_evaluations(run_weather_agent)
    report.display()

    # Group the parallel result lists by case so you can read, per scenario, how
    # every resilience judge voted. The baseline rows (no injected failure) are
    # your reference: chaos rows should ideally hold up close to them.
    print("=" * 60)
    by_case: dict[str, list[int]] = {}
    for i, row in enumerate(report.cases):
        by_case.setdefault(row.get("name"), []).append(i)

    for name, idxs in by_case.items():
        all_pass = all(report.test_passes[i] for i in idxs)
        print(f"\n{name}  —  {'ALL PASS' if all_pass else 'HAS FAILURES'}")
        for i in idxs:
            mark = "PASS" if report.test_passes[i] else "FAIL"
            print(f"  [{mark}] {report.cases[i].get('evaluator'):<28} "
                  f"score={report.scores[i]:.2f}")
            print(f"         {report.reasons[i]}")

    pass_rate = sum(report.test_passes) / len(report.test_passes)
    print(f"\nOverall resilience score: {report.overall_score:.2f}   "
          f"Checks passed: {sum(report.test_passes)}/{len(report.test_passes)} "
          f"({pass_rate:.0%})")


if __name__ == "__main__":
    main()
