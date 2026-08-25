"""Entry point for Recipe 02 — SOP verifier.

Runs the SOP agent from Recipe 01 (same sop.md, same incident), then hands the
transcript to a verifier agent that checks each step went through.

Run from the repo root:

    uv run recipes/02-sop-verifier/main.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from strands import Agent

sys.path.append(str(Path(__file__).resolve().parents[2]))

from shared.model import build_model  # noqa: E402

from verifier import build_verifier, verify_run  # noqa: E402

# Reuse Recipe 01's SOP as the single source of truth.
SOP = (Path(__file__).resolve().parents[1] / "01-sop-agent" / "sop.md").read_text()

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
    # 1. Run the SOP agent (silently — we'll print its transcript once).
    sop_agent = Agent(model=build_model(), system_prompt=SOP, callback_handler=None)
    transcript = str(sop_agent(f"Start the incident triage SOP.\n\n{INCIDENT}"))

    print("SOP agent transcript\n" + "=" * 60)
    print(transcript)

    # 2. Verify each step went through.
    print("\nVerifying steps\n" + "=" * 60)
    report = verify_run(build_verifier(), SOP, transcript)

    for check in report.checks:
        mark = "✅" if check.completed else "❌"
        print(f"{mark} {check.step} — {check.note}")

    print("=" * 60)
    if report.all_steps_completed:
        print("✅ All SOP steps completed.")
    else:
        missing = [c.step for c in report.checks if not c.completed]
        print(f"❌ Incomplete. Missing/failed: {', '.join(missing)}")


if __name__ == "__main__":
    main()
