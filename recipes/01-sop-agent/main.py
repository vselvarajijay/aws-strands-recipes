"""Recipe 01 — an agent that runs a Standard Operating Procedure.

The SOP is a markdown file used as the agent's system prompt. You kick it off
with a single prompt, and the agent works through the steps and produces the
report. Swap in your own SOP by editing sop.md — no code changes needed.

Run from the repo root:

    uv run recipes/01-sop-agent/main.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from strands import Agent

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


def main() -> None:
    # The SOP is the system prompt; the incident is the kickoff message.
    agent = Agent(model=build_model(), system_prompt=SOP)

    print("Running incident triage SOP...\n" + "=" * 60)
    agent(f"Start the incident triage SOP.\n\n{INCIDENT}")  # streams to stdout
    print("=" * 60)


if __name__ == "__main__":
    main()
