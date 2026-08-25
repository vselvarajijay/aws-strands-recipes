"""Recipe 06 — evaluate the *path*, not just the answer: tool trajectories.

Recipes 04 and 05 judged the agent's final text. But a tool-using agent can
reach a right-looking answer the wrong way: refunding an order without first
looking it up, using an expensive tool where a cheap one would do, or calling
nothing at all and hallucinating the result. To catch that, you evaluate the
*trajectory* — the ordered sequence of tools the agent actually called.

The flow:

    1. The task runs the agent, then extracts the trajectory from its messages
       with `tools_use_extractor` and returns {output, trajectory}. The
       Experiment maps `trajectory` onto the case's `actual_trajectory`.
    2. Two evaluators score it:
         - TrajectoryMatches (custom, deterministic) — does the actual tool
           sequence contain the expected tools in the expected order? No model.
         - TrajectoryEvaluator (LLM judge) — was the tool use *appropriate* for
           the request? Handles nuance a strict matcher can't.

Each Case carries its OWN `expected_trajectory`, so different requests can expect
different tool paths — something a single global `ToolCalled(name)` check (from
recipe 05) can't express. `ToolCalled` is the right tool when every case must hit
the same tool; per-case expectations want a trajectory evaluator.

Run from the repo root:

    uv run recipes/06-eval-trajectory/main.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from strands import Agent, tool
from strands_evals import Case, Experiment
from strands_evals.evaluators import Evaluator, TrajectoryEvaluator
from strands_evals.extractors import tools_use_extractor
from strands_evals.types import EvaluationData, EvaluationOutput

# Make the repo root importable so `shared` resolves when run directly.
sys.path.append(str(Path(__file__).resolve().parents[2]))

from shared.model import build_model  # noqa: E402


# --- Tools the agent can use ------------------------------------------------
# Custom @tool functions (not strands_tools.calculator, which is deprecated).
# They return canned data so the recipe needs no external services. The names —
# get_order, issue_refund, store_hours — are what show up in the trajectory.


@tool
def get_order(order_id: str) -> str:
    """Look up an order's total and refund eligibility.

    Args:
        order_id: The order identifier, e.g. "O-1".
    """
    return f"Order {order_id}: total $80.00, status DELIVERED, refund-eligible: yes"


@tool
def issue_refund(order_id: str, amount: float) -> str:
    """Issue a refund against an order.

    Args:
        order_id: The order to refund.
        amount: The amount to refund in dollars.
    """
    return f"Refund of ${amount:.2f} issued for order {order_id}."


@tool
def store_hours(location: str) -> str:
    """Get a store's opening hours.

    Args:
        location: The store location, e.g. "downtown".
    """
    return f"The {location} store is open 9am-6pm, Monday through Saturday."


TOOLS = [get_order, issue_refund, store_hours]

SYSTEM_PROMPT = """\
You are a store operations assistant. Use the provided tools to answer.
Rule: never issue a refund without first looking up the order with get_order to
confirm it is refund-eligible. Answer only what was asked."""


# --- The task: run the agent, capture what tools it called ------------------
def run_agent(case: Case) -> dict:
    agent = Agent(
        model=build_model(),
        system_prompt=SYSTEM_PROMPT,
        tools=TOOLS,
        callback_handler=None,
    )
    response = agent(case.input)

    # extract_agent_tools_used_from_messages returns rich dicts (name, input,
    # result...). We reduce to the ordered list of tool NAMES — the trajectory.
    # Two reasons to reduce: deterministic name-matching needs plain strings, and
    # it keeps the judge's context small (the docs' "prevent context overflow").
    used = tools_use_extractor.extract_agent_tools_used_from_messages(agent.messages)
    trajectory = [step["name"] for step in used]

    # Keys map onto EvaluationData: `output` -> actual_output, `trajectory` ->
    # actual_trajectory. Both evaluators read those fields.
    return {"output": str(response), "trajectory": trajectory}


# --- A deterministic trajectory evaluator (no model) ------------------------
# Respects each case's own expected_trajectory: passes if the expected tool names
# appear in the actual trajectory in order (extra steps allowed). This is the
# "in-order match" idea, written out so you can see exactly what it checks.
class TrajectoryMatches(Evaluator[str, str]):
    """Pass if expected_trajectory is an in-order subsequence of the actual one."""

    def evaluate(self, evaluation_case: EvaluationData[str, str]) -> list[EvaluationOutput]:
        expected = evaluation_case.expected_trajectory or []
        actual = evaluation_case.actual_trajectory or []

        # Walk `actual`, advancing through `expected` as we match each name.
        idx = 0
        for name in actual:
            if idx < len(expected) and name == expected[idx]:
                idx += 1
        score = idx / len(expected) if expected else 1.0
        passed = idx == len(expected)

        return [EvaluationOutput(
            score=score,
            test_pass=passed,
            label="in_order_match",
            reason=(f"expected {expected} in order; actual was {actual} "
                    f"({idx}/{len(expected)} matched)"),
        )]


# --- Cases: each with its own expected tool path ----------------------------
CASES = [
    Case[str, str](
        name="just-hours",
        input="What are the hours of the downtown store?",
        expected_trajectory=["store_hours"],
        metadata={"note": "one tool, no order lookup"},
    ),
    Case[str, str](
        name="order-total",
        input="How much was order O-1?",
        expected_trajectory=["get_order"],
        metadata={"note": "read-only lookup"},
    ),
    Case[str, str](
        name="refund-after-lookup",
        input="Please refund order O-1 in full.",
        # The rule: look up BEFORE refunding. Order matters — this is why we use a
        # trajectory evaluator and not just 'was issue_refund called?'.
        expected_trajectory=["get_order", "issue_refund"],
        metadata={"note": "must look up before acting"},
    ),
]


RUBRIC = """
Judge whether the tools were used appropriately for the request:
  1. Right tools    - were the correct tools chosen for what was asked?
  2. Right order    - for actions with a prerequisite (e.g. look up an order
                      before refunding it), did the prerequisite come first?
  3. No waste       - were unnecessary tools avoided?
Use in_order_match_scorer against the expected trajectory as your starting score,
then adjust for appropriateness.
Score 1.0 for the correct tools in a sensible order, 0.5 for right tools but poor
order or extra calls, 0.0 for wrong or missing tool use.
"""


def main() -> None:
    # Give the LLM judge a short description of each available tool so it can
    # reason about appropriateness without being handed full schemas.
    sample_agent = Agent(model=build_model(), tools=TOOLS)
    tool_descriptions = tools_use_extractor.extract_tools_description(sample_agent, is_short=True)

    trajectory_judge = TrajectoryEvaluator(rubric=RUBRIC, model=build_model())
    trajectory_judge.update_trajectory_description(tool_descriptions)

    evaluators = [TrajectoryMatches(), trajectory_judge]
    experiment = Experiment[str, str](cases=CASES, evaluators=evaluators)

    print("Running trajectory evaluation...\n" + "=" * 60)
    report = experiment.run_evaluations(run_agent)
    report.display(include_actual_trajectory=True, include_expected_trajectory=True)

    print("=" * 60)
    for i, row in enumerate(report.cases):
        mark = "PASS" if report.test_passes[i] else "FAIL"
        print(f"  [{mark}] {row.get('name'):<20} {row.get('evaluator'):<20} "
              f"score={report.scores[i]:.2f}")
        print(f"         {report.reasons[i]}")

    pass_rate = sum(report.test_passes) / len(report.test_passes)
    print(f"\nOverall score: {report.overall_score:.2f}   Pass rate: {pass_rate:.0%}")


if __name__ == "__main__":
    main()
