"""Recipe 01 — an agent that executes a Standard Operating Procedure.

The agent is a plain ``strands.Agent`` given (a) a system prompt that tells it
to follow an SOP step by step, and (b) a small set of tools so that each step
does real work you can watch happen. The SOP itself is loaded from a markdown
file at runtime, so you can swap in your own procedure without touching code.
"""

from __future__ import annotations

import sys
from pathlib import Path

from strands import Agent, tool

# Make the repo root importable so `shared` resolves when run directly.
sys.path.append(str(Path(__file__).resolve().parents[2]))

from shared.model import build_model  # noqa: E402

# --------------------------------------------------------------------------- #
# Tools
#
# These are mock implementations that return canned data. In a real recipe
# they'd call your monitoring stack, log search, pager, etc. What matters is
# that they give the agent concrete actions to take for each SOP step, and
# print as they run so you can see the procedure being followed.
# --------------------------------------------------------------------------- #


@tool
def check_service_health(service: str) -> str:
    """Return current health metrics (error rate, p99 latency) for a service."""
    print(f"  [tool] check_service_health(service={service!r})")
    return (
        f"{service}: error_rate=8.2% (baseline 0.3%), "
        f"p99_latency=2400ms (baseline 180ms), status=DEGRADED"
    )


@tool
def search_logs(service: str, minutes: int = 15) -> str:
    """Search the last N minutes of logs for a service and summarize errors."""
    print(f"  [tool] search_logs(service={service!r}, minutes={minutes})")
    return (
        f"Top error over last {minutes}m for {service}: "
        "`ConnectionPoolTimeout: could not acquire connection from pool` "
        "(1,204 occurrences, 91% of errors)."
    )


@tool
def page_oncall(service: str, severity: str, message: str) -> str:
    """Page the on-call engineer for a service. Use only for SEV1/SEV2."""
    print(f"  [tool] page_oncall(service={service!r}, severity={severity!r})")
    return f"Paged on-call for {service} at {severity}: {message}"


@tool
def record_finding(step: str, finding: str) -> str:
    """Record a finding for an SOP step to the incident timeline."""
    print(f"  [tool] record_finding(step={step!r})")
    return f"Recorded [{step}]: {finding}"


SOP_TOOLS = [check_service_health, search_logs, page_oncall, record_finding]


SYSTEM_PROMPT = """\
You are an operations agent that executes Standard Operating Procedures (SOPs).

You will be given an SOP as a numbered list of steps and a scenario to handle.

Rules:
- Work through the SOP one step at a time, in order. Never skip a step.
- Before moving to the next step, use the appropriate tool(s) to actually
  perform the current step. Do not fabricate tool results.
- Announce each step as you begin it, e.g. "Step 3: Search recent logs".
- Record a finding for each step with the record_finding tool so there is an
  audit trail.
- When every step is complete, output a final section titled
  "TRIAGE SUMMARY" with the outcome.

Be concise. Let the tools do the work; don't narrate at length between them.
"""


def build_sop_agent() -> Agent:
    """Construct the SOP-executing agent."""
    return Agent(
        model=build_model(max_tokens=4096),
        system_prompt=SYSTEM_PROMPT,
        tools=SOP_TOOLS,
        name="sop-agent",
        description="Executes a standard operating procedure step by step.",
    )
