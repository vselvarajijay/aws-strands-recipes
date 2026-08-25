"""Entry point for Recipe 01 — SOP agent.

Loads an SOP from markdown, hands it to the agent along with a scenario, and
lets the agent execute the procedure end to end.

Run from the repo root:

    uv run recipes/01-sop-agent/main.py

Pass a different SOP file as the first argument:

    uv run recipes/01-sop-agent/main.py path/to/your_sop.md
"""

from __future__ import annotations

import sys
from pathlib import Path

from agent import build_sop_agent

HERE = Path(__file__).resolve().parent
DEFAULT_SOP = HERE / "sops" / "incident_triage.md"

# The situation the agent must handle by following the SOP.
SCENARIO = """\
A PagerDuty alert just fired:

    Alert: HighErrorRate on service "checkout-api"
    Region: us-east-1
    Triggered: just now

Handle this alert by following the SOP below exactly.
"""


def main() -> None:
    sop_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SOP
    sop_text = sop_path.read_text()

    prompt = f"{SCENARIO}\n\n=== SOP ===\n{sop_text}"

    agent = build_sop_agent()
    print(f"Executing SOP: {sop_path.name}\n" + "=" * 60)
    result = agent(prompt)
    print("=" * 60)
    print(result)


if __name__ == "__main__":
    main()
