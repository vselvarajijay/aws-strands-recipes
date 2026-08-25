"""The worker agent for Recipe 02.

Unlike Recipe 01 (where one agent runs the whole SOP in a single call), this
worker executes exactly one step per invocation. A single ``Agent`` instance is
reused across steps, so it keeps the full conversation history and remembers
what it found in earlier steps. Between steps, the supervisor decides whether
the worker may advance.
"""

from __future__ import annotations

import sys
from pathlib import Path

from strands import Agent, tool

sys.path.append(str(Path(__file__).resolve().parents[2]))

from shared.model import build_model  # noqa: E402

from sop import Step  # noqa: E402


# Mock ops tools — same idea as Recipe 01. Real recipes would wire these to a
# monitoring stack, log search, and pager.
@tool
def check_service_health(service: str) -> str:
    """Return current health metrics (error rate, p99 latency) for a service."""
    print(f"    [tool] check_service_health(service={service!r})")
    return (
        f"{service}: error_rate=8.2% (baseline 0.3%), "
        f"p99_latency=2400ms (baseline 180ms), status=DEGRADED"
    )


@tool
def search_logs(service: str, minutes: int = 15) -> str:
    """Search the last N minutes of logs for a service and summarize errors."""
    print(f"    [tool] search_logs(service={service!r}, minutes={minutes})")
    return (
        f"Top error over last {minutes}m for {service}: "
        "`ConnectionPoolTimeout: could not acquire connection from pool` "
        "(1,204 occurrences, 91% of errors)."
    )


@tool
def page_oncall(service: str, severity: str, message: str) -> str:
    """Page the on-call engineer for a service. Use only for SEV1/SEV2."""
    print(f"    [tool] page_oncall(service={service!r}, severity={severity!r})")
    return f"Paged on-call for {service} at {severity}: {message}"


@tool
def record_finding(step: str, finding: str) -> str:
    """Record a finding for an SOP step to the incident timeline."""
    print(f"    [tool] record_finding(step={step!r})")
    return f"Recorded [{step}]: {finding}"


WORKER_TOOLS = [check_service_health, search_logs, page_oncall, record_finding]


SYSTEM_PROMPT = """\
You are an operations agent executing a Standard Operating Procedure, one step
at a time, under the review of a supervisor.

For each step you are given:
- the step's instruction and its exit criteria,
- any feedback from the supervisor if a previous attempt was rejected.

Rules:
- Do ONLY the current step. Do not run ahead to later steps.
- Use the appropriate tool(s) to actually perform the step; do not fabricate
  tool results. Record a finding for the step with record_finding.
- If the supervisor gave feedback, address it directly on this attempt.
- End your reply with a brief "RESULT:" line stating what you did and what you
  found, so the supervisor can verify the exit criteria were met.
"""


def build_worker() -> Agent:
    """Construct the step-executing worker agent."""
    return Agent(
        model=build_model(max_tokens=2048),
        system_prompt=SYSTEM_PROMPT,
        tools=WORKER_TOOLS,
        name="sop-worker",
        description="Executes a single SOP step at a time.",
    )


def run_step(
    worker: Agent,
    step: Step,
    scenario: str,
    feedback: str | None = None,
) -> str:
    """Have the worker attempt one step; return its reported result text."""
    feedback_block = (
        f"\nThe supervisor REJECTED your previous attempt with this feedback:\n"
        f"{feedback}\nAddress it on this attempt.\n"
        if feedback
        else ""
    )
    prompt = (
        f"Scenario:\n{scenario}\n\n"
        f"Current step {step.number}: {step.title}\n"
        f"Instruction: {step.instruction}\n"
        f"Exit criteria: {step.exit_criteria}\n"
        f"{feedback_block}"
    )
    return str(worker(prompt))
