"""Recipe 02 — an SOP agent that pauses for a human on high-impact steps.

This builds on recipe 01: the SOP is still a markdown system prompt that the
agent works through step by step. The difference is step 5. When the agent
decides an incident is severe enough to page the on-call engineer, it must call
the ``escalate_to_oncall`` tool — and that tool *interrupts* the run to ask a
human to approve or deny the page.

An interrupt suspends the agent mid-tool-call and hands control back to us. We
show the human the context, collect a decision, and resume the same run by
feeding the decision back in. The agent then continues the SOP with the human's
answer as the tool's return value — approve and it records the page, deny and it
records that escalation was refused.

See https://strandsagents.com/docs/user-guide/concepts/interrupts/

Run from the repo root (this recipe is interactive — it reads from stdin):

    uv run recipes/02-sop-interrupt/main.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from strands import Agent, tool
from strands.types.tools import ToolContext

# Make the repo root importable so `shared` resolves when run directly.
sys.path.append(str(Path(__file__).resolve().parents[2]))

from shared.model import build_model  # noqa: E402

HERE = Path(__file__).resolve().parent
SOP = (HERE / "sop.md").read_text()

# The incident to triage. In a real system this would come from your alerting.
INCIDENT = """\
Alert: HighErrorRate on service "checkout-api" (us-east-1)

Health metrics:
- error_rate: 8.2% (baseline 0.3%)
- p99_latency: 2400ms (baseline 180ms)
- status: DEGRADED

Recent logs (last 15m):
- ConnectionPoolTimeout: could not acquire connection from pool
  (1,204 occurrences, 91% of errors)
"""


@tool(context=True)
def escalate_to_oncall(
    service: str,
    severity: str,
    summary: str,
    tool_context: ToolContext,
) -> str:
    """Request approval to page the on-call engineer for a service.

    Paging a human is high-impact, so this tool does not act on its own. It
    raises an interrupt that suspends the agent and asks a human reviewer to
    approve or deny. The reviewer's decision is returned to the agent as this
    tool's result.

    Args:
        service: The affected service to page for.
        severity: The incident severity (e.g. SEV1, SEV2).
        summary: A one-line summary of what is happening.

    Returns:
        A short string describing the human reviewer's decision.
    """
    # `interrupt` raises out of this tool on the first call, pausing the run.
    # When we resume the agent with a response, `interrupt` returns that value
    # instead of raising — so control lands right back here and continues.
    decision = tool_context.interrupt(
        "escalation-approval",
        reason={
            "action": "Page the on-call engineer",
            "service": service,
            "severity": severity,
            "summary": summary,
        },
    )

    if str(decision).strip().lower() in {"y", "yes", "approve", "approved"}:
        return f"APPROVED by reviewer — {service} on-call engineer has been paged."
    return f"DENIED by reviewer — on-call was not paged. Reviewer note: {decision!r}"


def _ask_human(reason: object) -> str:
    """Render an interrupt's reason and collect the reviewer's decision."""
    print("\n" + "!" * 60)
    print("HUMAN APPROVAL REQUIRED — agent is paused")
    if isinstance(reason, dict):
        for key, value in reason.items():
            print(f"  {key}: {value}")
    else:
        print(f"  {reason}")
    print("!" * 60)
    return input("Approve paging on-call? [y/N], or type an instruction: ")


def main() -> None:
    agent = Agent(
        model=build_model(),
        system_prompt=SOP,
        tools=[escalate_to_oncall],
    )

    print("Running incident triage SOP...\n" + "=" * 60)
    result = agent(f"Start the incident triage SOP.\n\n{INCIDENT}")  # streams to stdout

    # The agent stops with reason "interrupt" whenever a tool paused for a human.
    # Answer each pending interrupt, then resume the *same* run by passing the
    # responses back in. Loop in case the run interrupts again.
    while result.stop_reason == "interrupt":
        responses = []
        for interrupt in result.interrupts:
            answer = _ask_human(interrupt.reason)
            responses.append(
                {
                    "interruptResponse": {
                        "interruptId": interrupt.id,
                        "response": answer,
                    }
                }
            )
        print("\nResuming agent with your decision...\n" + "-" * 60)
        result = agent(responses)  # streams the rest of the SOP to stdout

    print("=" * 60)


if __name__ == "__main__":
    main()
