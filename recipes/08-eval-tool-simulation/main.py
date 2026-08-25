"""Recipe 08 — evaluate a tool-using agent with *simulated* tools.

Recipes 04-07 evaluated agents whose tools returned canned strings, or no tools
at all. Real agents call tools that hit live infrastructure: order databases,
shipping APIs, payment gateways, hardware. You can't stand all that up just to
run an eval — and even if you could, you'd want its responses to be *controllable*
so each test exercises a specific scenario.

Tool simulation solves this. `strands_evals.simulation.ToolSimulator` replaces a
tool's real implementation with an LLM-backed stand-in: you declare the tool's
signature, its output schema, and a plain-English description of the world it
operates in, and the simulator generates schema-valid responses on every call —
no backend required.

The moving parts:

    @tool_simulator.tool(output_schema=..., ...)   register a simulated tool.
        The decorated function has NO body (just `...`) — the simulator, not
        your code, produces the return value.
    output_schema (a Pydantic model)               forces every simulated
        response to be valid, typed data your agent can rely on.
    share_state_id + initial_state_description      give a group of tools a
        shared, seeded world so their answers stay mutually consistent across
        calls (look up an order, then its item's stock — same story).
    tool_simulator.get_tool(name)                   hand the wrapped tool to a
        normal Strands Agent, exactly like a real @tool.

From there it's the same eval machinery as the rest of the series: a task runs
the agent over each Case, and an OutputEvaluator judges the answer. The whole
thing — the agent, the judge, AND the simulated tools — runs on one
ANTHROPIC_API_KEY via the shared model factory. The simulator defaults to Bedrock
if you don't pass a model; we pass ours so there's nothing else to configure.

Run from the repo root:

    uv run recipes/08-eval-tool-simulation/main.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from strands import Agent
from strands_evals import Case, Experiment
from strands_evals.evaluators import OutputEvaluator
from strands_evals.simulation import ToolSimulator

# Make the repo root importable so `shared` resolves when run directly.
sys.path.append(str(Path(__file__).resolve().parents[2]))

from shared.model import build_model  # noqa: E402


# --- Output schemas: the contract every simulated response must satisfy ------
# output_schema is mandatory. It's what makes a simulated tool trustworthy: the
# simulator is forced to return data matching these fields and types, so your
# agent gets the same well-formed shape it would from the real service — never a
# free-form paragraph it has to parse.
class OrderStatus(BaseModel):
    order_id: str = Field(..., description="Order identifier, e.g. 'O-1001'")
    status: str = Field(..., description="One of: processing, shipped, delayed, delivered")
    sku: str = Field(..., description="SKU of the item on the order")
    estimated_delivery: str = Field(..., description="Human-readable delivery estimate")


class InventoryStatus(BaseModel):
    sku: str = Field(..., description="The SKU queried")
    in_stock: bool = Field(..., description="Whether the item is currently in stock")
    quantity: int = Field(..., description="Units available (0 if out of stock)")


# --- The simulator: one shared, seeded world -------------------------------
# Passing model=build_model() runs the simulation on the same Anthropic provider
# as everything else (the simulator would otherwise default to Bedrock).
tool_simulator = ToolSimulator(model=build_model())

# Both tools share the SAME state group ("store_backend"), seeded once with the
# scenario below. Because they share state, the simulator keeps their answers
# consistent: the order's SKU and that SKU's stock level tell one coherent story
# across however many times the agent calls them. Seed the world with enough
# specifics that the cases have a knowable "right" answer to grade against.
STORE_STATE = """\
Online store backend. Known facts:
- Order O-1001 is for SKU BLUE-WIDGET, and is currently DELAYED in transit;
  estimated delivery is 'Sep 2, 2026' (about a week late).
- Order O-2002 is for SKU RED-GADGET, and was DELIVERED on Aug 20, 2026.
- Inventory: BLUE-WIDGET is OUT OF STOCK (0 units). RED-GADGET has 47 units.
  GREEN-GIZMO has 12 units.
Any order id or SKU not listed above does not exist."""


@tool_simulator.tool(
    share_state_id="store_backend",
    initial_state_description=STORE_STATE,
    output_schema=OrderStatus,
)
def get_order(order_id: str) -> dict[str, Any]:
    """Look up a customer order's status, item, and delivery estimate.

    Args:
        order_id: The order identifier, e.g. "O-1001".
    """
    ...  # No body: the simulator produces the response from the schema + state.


@tool_simulator.tool(
    share_state_id="store_backend",
    output_schema=InventoryStatus,
)
def check_inventory(sku: str) -> dict[str, Any]:
    """Check current stock for a product SKU.

    Args:
        sku: The product SKU, e.g. "BLUE-WIDGET".
    """
    ...  # No body: the simulator produces the response from the schema + state.


SYSTEM_PROMPT = """\
You are a customer-support agent for an online store. Use get_order to look up
orders and check_inventory to check stock. Answer only what the customer asked,
grounded in what the tools return — don't volunteer details the customer didn't
ask for. When someone wants a replacement item, check its stock before promising
anything."""


# --- The task: run the agent against the simulated tools --------------------
# get_tool(name) returns the LLM-backed wrapper, which drops into a normal Agent
# exactly like a real @tool. A fresh agent per case keeps tests independent; the
# simulator's shared state persists across calls WITHIN a run so the backend
# tells one consistent story.
def run_support(case: Case) -> str:
    agent = Agent(
        model=build_model(),
        system_prompt=SYSTEM_PROMPT,
        tools=[
            tool_simulator.get_tool("get_order"),
            tool_simulator.get_tool("check_inventory"),
        ],
        callback_handler=None,
    )
    return str(agent(case.input))


# --- Cases: questions with a knowable answer given the seeded world ---------
# expected_output is a reference for the judge, derived from STORE_STATE above.
# Because the world is seeded, the "right" answer is knowable even though a model
# generated the tool responses.
CASES = [
    Case[str, str](
        name="delayed-order",
        input="Where is my order O-1001? When will it arrive?",
        expected_output=(
            "Order O-1001 is delayed in transit, with an estimated delivery "
            "around Sep 2, 2026."
        ),
        metadata={"scenario": "single order lookup"},
    ),
    Case[str, str](
        name="delivered-order",
        input="Has order O-2002 been delivered yet?",
        expected_output="Yes — order O-2002 was delivered on Aug 20, 2026.",
        metadata={"scenario": "single order lookup"},
    ),
    Case[str, str](
        name="delayed-and-restock",
        input=(
            "My order O-1001 is late. Can you just send me a replacement of the "
            "same item instead?"
        ),
        expected_output=(
            "O-1001 (a BLUE-WIDGET) is delayed, but BLUE-WIDGET is out of stock, "
            "so an immediate replacement can't be shipped. The agent should say so "
            "rather than promise a reshipment it can't fulfill."
        ),
        metadata={"scenario": "two tools, shared state must stay consistent"},
    ),
]


# The rubric grades whether the answer is faithful to what the simulated tools
# returned — the same standard you'd hold a real tool-using agent to.
RUBRIC = """
You are grading a customer-support agent that answered using backend tools.
Score on:
  1. Accuracy   - Does the answer match the order/inventory facts (status,
                  delivery date, stock)?
  2. Grounding  - Is every claim supported by a tool result, with nothing
                  invented (no promised reshipment of an out-of-stock item)?
  3. Relevance  - Does it actually answer what the customer asked?
Compare against the ExpectedOutput, which states the correct facts.
Score 1.0 if the answer is accurate, grounded, and on-point. Score 0.5 if it is
partially correct or makes an unsupported claim. Score 0.0 if it is wrong or
invents facts. Pass only when the answer is accurate and fully grounded.
"""


def main() -> None:
    evaluator = OutputEvaluator(rubric=RUBRIC, model=build_model(), include_inputs=True)
    experiment = Experiment[str, str](cases=CASES, evaluators=[evaluator])

    print("Running eval with simulated tools (no backend)...\n" + "=" * 60)
    report = experiment.run_evaluations(run_support)
    report.display(include_actual_output=True, include_expected_output=True)

    # Per-case breakdown from the parallel result lists (see recipe 04).
    print("=" * 60)
    print("Per-case breakdown:")
    for i, row in enumerate(report.cases):
        mark = "PASS" if report.test_passes[i] else "FAIL"
        print(f"  [{mark}] {row.get('name'):<20} score={report.scores[i]:.2f}")
        print(f"         {report.reasons[i]}")

    # Inspecting the simulator's state is a debugging superpower: you can see
    # exactly which tool calls happened and what the simulated backend returned.
    final_state = tool_simulator.get_state("store_backend")
    calls = final_state.get("previous_calls", [])
    print("=" * 60)
    print(f"Simulated backend recorded {len(calls)} tool call(s) this run:")
    for call in calls:
        print(f"  {call['tool_name']}({call['parameters']}) -> {call['response']}")

    pass_rate = sum(report.test_passes) / len(report.test_passes)
    print(f"\nOverall score: {report.overall_score:.2f}   Pass rate: {pass_rate:.0%}")


if __name__ == "__main__":
    main()
