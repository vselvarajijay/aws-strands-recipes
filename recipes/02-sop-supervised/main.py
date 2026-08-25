"""Entry point for Recipe 02 — supervised SOP agent.

The supervision loop: for each step, the worker attempts it and the supervisor
verifies the result against the step's exit criteria. A rejected step is retried
(with the supervisor's feedback) up to MAX_ATTEMPTS times before the run aborts.
The procedure only advances when the supervisor is satisfied.

Run from the repo root:

    uv run recipes/02-sop-supervised/main.py
"""

from __future__ import annotations

from sop import INCIDENT_TRIAGE
from supervisor import build_supervisor, review_step
from worker import build_worker, run_step

MAX_ATTEMPTS = 3

SCENARIO = """\
A PagerDuty alert just fired:
    Alert: HighErrorRate on service "checkout-api"
    Region: us-east-1
    Triggered: just now
"""


def main() -> None:
    worker = build_worker()
    supervisor = build_supervisor()
    steps = INCIDENT_TRIAGE

    print(f"Supervised SOP run — {len(steps)} steps\n" + "=" * 60)

    for step in steps:
        print(f"\n### Step {step.number}: {step.title}")
        feedback: str | None = None

        for attempt in range(1, MAX_ATTEMPTS + 1):
            print(f"  Attempt {attempt}/{MAX_ATTEMPTS} — worker:")
            result = run_step(worker, step, SCENARIO, feedback)

            verdict = review_step(supervisor, step, result)
            if verdict.satisfied:
                print(f"  ✅ supervisor: PASS — {verdict.reason}")
                break

            print(f"  ❌ supervisor: RETRY — {verdict.reason}")
            if verdict.guidance:
                print(f"     guidance: {verdict.guidance}")
            feedback = verdict.guidance or verdict.reason
        else:
            print(
                f"\n🛑 Step {step.number} failed after {MAX_ATTEMPTS} attempts. "
                "Aborting the run — a human should take over."
            )
            return

    print("\n" + "=" * 60)
    print("✅ All steps passed supervision. SOP complete.")


if __name__ == "__main__":
    main()
