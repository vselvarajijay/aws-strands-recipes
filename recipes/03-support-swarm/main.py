"""Recipe 03 — a swarm of specialists that self-organize to work a support case.

The first two recipes drive a *single* agent through a fixed procedure. Real
operations work isn't that linear: a support case comes in, and who needs to
touch it — and in what order — depends on what the case turns out to be. A
billing question routes one way; a production outage on a top-tier account routes
another, and usually needs more than one specialist.

A Strands *Swarm* models exactly this. You hand it a team of specialized agents
and a single case. There is no central router hard-coded by you — each agent
decides, from what it learns, whether it can finish the case or should **hand off**
to a teammate. Strands gives every agent a ``handoff_to_agent`` tool for free and
shares the working context across the team, so a handoff carries the history with
it. The swarm ends when an agent stops handing off (the case is resolved) or a
safety limit trips.

The team here is a plausible enterprise support desk:

    triage              -> reads the case, does first-line classification, routes
    technical_support   -> reproduces/diagnoses technical issues, finds workarounds
    account_manager     -> owns the customer relationship, entitlements, retention
    escalation_manager  -> runs SEV1/at-risk situations: comms, credits, paging

Entry point is ``triage``. Where it goes from there is up to the agents.

See https://strandsagents.com/docs/user-guide/concepts/multi-agent/swarm/

Run from the repo root:

    uv run recipes/03-support-swarm/main.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from strands import Agent, tool
from strands.multiagent import Swarm

# Make the repo root importable so `shared` resolves when run directly.
sys.path.append(str(Path(__file__).resolve().parents[2]))

from shared.model import build_model  # noqa: E402

# The inbound support case. In a real system this arrives from your ticketing
# system (Zendesk/Salesforce/etc.). Edit it to change how the swarm self-organizes.
CASE = """\
Support case #48213 — Priority: Urgent
Account: Northwind Traders (Enterprise plan)
Reported by: ops@northwind.example

Subject: Webhooks stopped firing in production ~40 minutes ago

Body:
Our order-processing pipeline depends on your `order.completed` webhooks. As of
~14:20 UTC we've received ZERO webhook deliveries, though the dashboard shows the
orders completing normally. This is halting fulfillment for our Black Friday
pre-sale. We're seeing real revenue impact and considering pausing the campaign.

Please treat as critical. Our renewal is also up next month and leadership is
watching how this is handled.
"""


# --- Tools the specialists can use -----------------------------------------
# Swarm gives every agent a handoff tool automatically. These extra tools make
# two of the specialists concrete: they can pull real-ish context instead of
# guessing. They're mocked here so the recipe runs with no external services.


@tool
def search_runbooks(query: str) -> str:
    """Search the engineering runbooks and known-issues board.

    Args:
        query: What to look up, e.g. "webhooks not delivering".

    Returns:
        Matching runbook entries as text.
    """
    return (
        "RUNBOOK HIT — 'Webhook deliveries stalled':\n"
        "  * Known cause: the delivery worker pool can wedge when a downstream\n"
        "    endpoint times out repeatedly, backing up the queue for the whole\n"
        "    shard. Symptom: events are produced but 0 are delivered.\n"
        "  * Immediate workaround for the customer: none client-side — this is\n"
        "    server-side. Their events are NOT lost; they queue and replay once\n"
        "    the worker pool is cycled.\n"
        "  * Fix: on-call platform eng cycles the delivery workers for the shard.\n"
        "  * STATUS BOARD: incident INC-2291 opened 6m ago, 3 enterprise accounts\n"
        "    affected on shard us-east-1b. Northwind is on us-east-1b."
    )


@tool
def lookup_account(account_name: str) -> str:
    """Look up an account's tier, value, and relationship status.

    Args:
        account_name: The customer account to look up.

    Returns:
        Account facts relevant to support prioritization.
    """
    return (
        f"ACCOUNT: {account_name}\n"
        "  * Plan: Enterprise ($240k ARR), customer for 3 years\n"
        "  * Support entitlement: 24/7, 1-hour SLA on Urgent, service credits apply\n"
        "  * Renewal: 34 days out — flagged AT-RISK by CSM last week\n"
        "  * Sentiment: previously escalated once (resolved well). Champion is the\n"
        "    VP Eng; leadership visibility is high on this one."
    )


# --- The specialist team ----------------------------------------------------
# Each agent gets a name (used for handoffs), a role prompt, and — where useful —
# a tool. Prompts spell out the ONE thing each agent owns and *when to hand off*,
# which is what keeps the swarm from ping-ponging or trying to do everything.

TRIAGE_PROMPT = """\
You are the first-line support triage coordinator on an enterprise support desk.
You do NOT resolve cases yourself. Your job, in order:
  1. Read the case and classify it: type (technical / billing / account / outage),
     and a severity (SEV1 critical, SEV2 high, SEV3 normal).
  2. Immediately hand off to the single best specialist to start real work:
       - technical or outage symptoms  -> technical_support
       - billing, entitlement, renewal -> account_manager
  3. In your handoff message, state your classification and why, so the next
     agent has your reasoning.
Keep your own turn short. Route; don't solve."""

TECH_PROMPT = """\
You are a senior technical support engineer. You own diagnosis of technical
issues. Use the search_runbooks tool to check for known issues before theorizing.
Then:
  - State the likely root cause and whether the customer's data is at risk.
  - Give any customer-facing workaround, or say clearly there is none.
If the issue is a broader incident, is customer-data/revenue impacting, or hits a
high-value/at-risk account, hand off to escalation_manager with your technical
findings. If it's a contained technical question you've fully answered, hand off
to account_manager to package the customer response. Don't write customer-facing
comms yourself — that's account_manager's job."""

ACCOUNT_PROMPT = """\
You are the account manager / customer relationship owner. Use the lookup_account
tool to ground your judgment in the account's tier, value, SLA, and renewal risk.
You own:
  - Entitlement and SLA calls (does this warrant credits? what's the SLA clock?).
  - The final customer-facing reply: empathetic, specific, honest about status
    and next steps. Write it out in full when the case is ready to answer.
If the situation is critical or the account is at-risk and leadership-visible,
hand off to escalation_manager rather than closing it yourself. If a technical
detail is unresolved, hand off to technical_support."""

ESCALATION_PROMPT = """\
You are the escalation manager / incident commander for high-severity, high-stakes
cases. You are engaged only when things are critical or a valuable account is at
risk. You own the coordinated response:
  - Decide and state the actions: page on-call/platform eng, link the incident,
    authorize service credits, set an internal update cadence, and flag the
    renewal risk to the CSM/leadership.
  - Summarize the situation crisply for internal stakeholders.
When the response plan is set, hand off to account_manager to turn it into the
customer-facing reply. Do not end the case with the customer un-replied-to."""


def _render(result: object) -> None:
    """Print the handoff path the swarm took and the final answer it produced."""
    print("\n" + "=" * 60)
    print(f"Swarm status: {result.status}")

    # node_history is the ordered list of agents that took control — i.e. the
    # path the case actually traveled. This is the swarm's self-chosen routing.
    path = " -> ".join(node.node_id for node in result.node_history)
    print(f"Handoff path: {path}")
    print(f"Agents engaged: {result.execution_count}   Time: {result.execution_time}ms")
    print("=" * 60)

    # The last agent to act produced the resolution. results is keyed by node_id;
    # each entry's .result is that agent's AgentResult (stringifies to its text).
    last_node_id = result.node_history[-1].node_id
    final = result.results[last_node_id].result
    print(f"\nFinal output (from {last_node_id}):\n")
    print(final)


def main() -> None:
    model = build_model()

    triage = Agent(name="triage", model=model, system_prompt=TRIAGE_PROMPT)
    technical_support = Agent(
        name="technical_support",
        model=model,
        system_prompt=TECH_PROMPT,
        tools=[search_runbooks],
    )
    account_manager = Agent(
        name="account_manager",
        model=model,
        system_prompt=ACCOUNT_PROMPT,
        tools=[lookup_account],
    )
    escalation_manager = Agent(
        name="escalation_manager", model=model, system_prompt=ESCALATION_PROMPT
    )

    # The swarm shares context across agents and hands every agent a
    # handoff_to_agent tool. entry_point is where the case starts; the limits are
    # safety rails so a confused team can't loop forever.
    swarm = Swarm(
        [triage, technical_support, account_manager, escalation_manager],
        entry_point=triage,
        max_handoffs=10,
        max_iterations=10,
        execution_timeout=300.0,
        node_timeout=120.0,
        # Break out of A->B->A->B ping-pong: if the last 6 hops don't include at
        # least 3 distinct agents, treat it as stuck.
        repetitive_handoff_detection_window=6,
        repetitive_handoff_min_unique_agents=3,
    )

    print("Working support case through the swarm...")
    result = swarm(CASE)  # blocks until the team resolves the case or a limit trips
    _render(result)


if __name__ == "__main__":
    main()
