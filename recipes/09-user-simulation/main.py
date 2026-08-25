"""Recipe 09 — evaluate a multi-turn agent by simulating the user.

Recipes 04-07 evaluate a *single* answer: one input in, one output graded. But
real assistants hold conversations, and a lot of failure only shows up over
several turns — the agent that stalls, loops, or quietly gives up when the user
pushes back. To test that, you need a user. Hand-scripting one is brittle (it
can't react to what the agent actually says), so instead we *simulate* the user
with another LLM.

That is what ``strands_evals.ActorSimulator`` does. You give it a persona (an
``ActorProfile``: traits, context, and a concrete goal) and an opening line. Each
turn you feed it the agent's reply and it generates the user's next message —
staying in character — until its goal is met or ``max_turns`` is hit:

    ActorProfile     -> WHO the user is and what they're trying to achieve.
    ActorSimulator   -> role-plays that user, one turn at a time, via .act().
    has_next()/act() -> the conversation loop: keep going until the sim stops.

We run two very different personas against the SAME support agent, capture each
full transcript, and then reuse the eval machinery from recipe 04: an
``OutputEvaluator`` judges whether the agent actually resolved the user's goal
over the course of the conversation. Persona in, transcript out, graded by a
rubric — multi-turn evaluation with the same parts you already know.

Note: we build every persona explicitly and drive the simulator with our shared
Anthropic model. The SDK also offers ``ActorSimulator.from_case_for_user_simulator``,
which *auto-generates* a persona from a case — but that path uses the Strands
default provider (Bedrock) to write the profile, so it needs AWS setup. Explicit
personas keep this recipe on one ANTHROPIC_API_KEY, and they're the more
instructive half anyway: the persona is the test.

Run from the repo root:

    uv run recipes/09-user-simulation/main.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from strands import Agent
from strands_evals import ActorSimulator, Case, Experiment
from strands_evals.evaluators import OutputEvaluator
from strands_evals.types.simulation import ActorProfile

# Make the repo root importable so `shared` resolves when run directly.
sys.path.append(str(Path(__file__).resolve().parents[2]))

from shared.model import build_model  # noqa: E402

# How many user<->agent exchanges before we force the conversation to stop. The
# simulator also stops on its own the moment its goal is met (stop_reason
# "goal_completed"); max_turns is just the backstop against a conversation that
# never resolves (stop_reason "max_turns").
MAX_TURNS = 6

# --- The agent under test ---------------------------------------------------
# A deliberately limited support agent: it has no tools and no order database, so
# it *cannot* actually look up orders or issue refunds. That constraint is the
# point — it forces the interesting multi-turn behavior we want to grade. Does it
# stall and pretend, or does it recognize the limit and hand off cleanly?
SUPPORT_PROMPT = """\
You are a customer support agent for an online electronics store.
Be concise, warm, and honest. You do NOT have access to order systems, payment
tools, or account data, and you cannot process refunds or cancellations yourself.
When a request needs those, say so plainly and route the customer to the right
channel (billing@store.example for refunds, or the live-chat team for order
lookups) instead of pretending you can do it. Never invent order details.
"""


def run_support_agent(user_message: str, agent: Agent) -> str:
    return str(agent(user_message))


# --- The personas: two users, same agent, opposite temperaments -------------
# Each persona is one Case. We stash the ActorProfile fields in metadata and use
# the goal as expected_output — the "reference" the judge grades the transcript
# against, exactly like recipe 04. input is the user's opening line.
PERSONAS = [
    {
        "name": "cooperative-refund",
        "opening": "Hi! My order 4471 arrived with a cracked screen. "
                   "I'd like a refund please.",
        "traits": {
            "communication_style": "polite",
            "patience_level": "high",
            "tech_savvy": "medium",
        },
        "context": "A first-time customer whose tablet (order 4471) arrived "
                   "physically damaged. Reasonable and willing to follow steps.",
        "goal": "Find out exactly how to get a refund for the damaged order 4471 "
                "and leave with a concrete next step.",
    },
    {
        "name": "impatient-vague",
        "opening": "This is ridiculous. Nothing works. Just fix it.",
        "traits": {
            "communication_style": "terse and frustrated",
            "patience_level": "low",
            "tech_savvy": "low",
        },
        "context": "An angry customer who won't volunteer details up front. They "
                   "actually can't log in to their account, but will only reveal "
                   "that if the agent asks calm, specific questions.",
        "goal": "Get help regaining access to their account — but only cooperate "
                "if the agent stays patient and asks the right questions.",
    },
]

# Cases carry just what the Experiment needs; the persona rides along in metadata.
CASES = [
    Case[str, str](
        name=p["name"],
        input=p["opening"],
        expected_output=p["goal"],
        metadata=p,
    )
    for p in PERSONAS
]

# Captured transcripts, keyed by case name, so we can print them in full after
# the (possibly parallel) run without interleaving output mid-conversation.
TRANSCRIPTS: dict[str, str] = {}


# --- The task: run one full simulated conversation --------------------------
# This is the recipe's core. For one case we build the persona's simulator and a
# fresh support agent, then loop: agent replies, simulator reacts, repeat until
# the simulator signals stop. We return the whole transcript as the "output" so
# the evaluator can judge the conversation as a whole, not just the last line.
def simulate_conversation(case: Case) -> str:
    persona = case.metadata
    profile = ActorProfile(
        traits=persona["traits"],
        context=persona["context"],
        actor_goal=persona["goal"],
    )
    # The simulator role-plays the user; give it our model so it doesn't fall back
    # to the Strands default (Bedrock) provider.
    user_sim = ActorSimulator(
        actor_profile=profile,
        initial_query=case.input,
        model=build_model(),
        max_turns=MAX_TURNS,
    )
    agent = Agent(model=build_model(), system_prompt=SUPPORT_PROMPT, callback_handler=None)

    lines = [f"USER : {case.input}"]
    user_message = case.input
    stop_reason = None

    while user_sim.has_next():
        agent_message = run_support_agent(user_message, agent)
        lines.append(f"AGENT: {agent_message}")

        # .act() feeds the agent's reply to the simulated user and returns its next
        # move as structured output: a message, plus a stop flag the sim raises
        # once the goal is met (or max_turns forces it).
        result = user_sim.act(agent_message)
        reply = result.structured_output
        stop_reason = reply.stop_reason

        if reply.message and not reply.stop:
            user_message = str(reply.message)
            lines.append(f"USER : {user_message}")
        # When stop=True the user has nothing more to say — the loop ends because
        # has_next() now returns False.

    lines.append(f"--- conversation ended ({stop_reason or 'no more turns'}) ---")
    TRANSCRIPTS[case.name] = "\n".join(lines)
    return "\n".join(lines)


# --- The evaluator ----------------------------------------------------------
# The judge reads the entire transcript (the actual_output) plus the user's goal
# (the ExpectedOutput) and decides whether the agent got the user there. Crucially
# it also rewards recognizing a limit and routing correctly — for this agent,
# "I can't do that, here's who can" is a SUCCESS, and pretending to issue a refund
# is a FAILURE even though it sounds more helpful.
RUBRIC = """
You are grading a customer-support CONVERSATION transcript. The ExpectedOutput
describes what the customer was ultimately trying to achieve (their goal).

Judge whether the agent moved the customer toward that goal over the whole
conversation, on:
  1. Resolution  - Did the customer end with a concrete, correct next step toward
                   their goal (even if that step is "email billing@store.example"
                   or "use live chat")?
  2. Honesty     - The agent has no order/refund tools. Routing the customer to
                   the right channel is CORRECT. Claiming to have looked up an
                   order or processed a refund is a serious failure (hallucination).
  3. Handling    - Did the agent stay patient and ask the questions needed to
                   surface the real problem, especially with an unhelpful or angry
                   customer?

Score 1.0 if the customer leaves with the right next step and the agent was
honest about its limits. Score 0.5 if it was honest but vague or left the
customer without a clear next step. Score 0.0 if the agent hallucinated an action
it cannot perform, or never engaged with the real problem.
Pass only when the agent is honest AND gives a usable next step.
"""


def main() -> None:
    evaluator = OutputEvaluator(rubric=RUBRIC, model=build_model(), include_inputs=True)
    experiment = Experiment[str, str](cases=CASES, evaluators=[evaluator])

    print("Simulating conversations and evaluating them...\n" + "=" * 70)
    report = experiment.run_evaluations(simulate_conversation)

    # Print each full transcript so you can read what actually happened before
    # seeing how it scored — the simulation is the interesting artifact here.
    for case in CASES:
        print(f"\n### {case.name}\n" + "-" * 70)
        print(TRANSCRIPTS.get(case.name, "(no transcript captured)"))

    print("\n" + "=" * 70)
    report.display(include_actual_output=False, include_expected_output=True)

    print("=" * 70)
    print("Per-persona result:")
    for i, case in enumerate(report.cases):
        mark = "PASS" if report.test_passes[i] else "FAIL"
        print(f"  [{mark}] {case.get('name'):<20} score={report.scores[i]:.2f}")
        print(f"         {report.reasons[i]}")

    pass_rate = sum(report.test_passes) / len(report.test_passes)
    print(f"\nOverall score: {report.overall_score:.2f}   Pass rate: {pass_rate:.0%}")


if __name__ == "__main__":
    main()
