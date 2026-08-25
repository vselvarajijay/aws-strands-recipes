"""Recipe 07 — a real eval suite over a real agent (the capstone).

Recipes 04-06 each taught one kind of evaluator in isolation. This one puts them
together the way you actually would: several evaluators — deterministic AND
LLM-judged — run over the SAME agent, because different guarantees need different
tools.

The agent under test is the incident-triage SOP agent from
[recipe 01](../01-sop-agent/). We reuse its `sop.md` verbatim as the single
source of truth, so this suite tests the real thing, not a copy. The SOP demands
a specific shape (six numbered steps, a `TRIAGE SUMMARY`) and specific behavior
(severity must be justified by the telemetry; the escalation decision must match
the severity). We check each property with the cheapest tool that can:

    Contains("TRIAGE SUMMARY")   deterministic  — the required section exists
    StepCoverage (custom)        deterministic  — all six SOP steps are present
    OutputEvaluator (rubric)     LLM judge      — did it follow the SOP and reach
                                                  the right, self-consistent call?

Deterministic checks are the guardrails you never want to regress and can verify
for free; the judge handles the reasoning a regex can't. Together they give a
fuller picture than any one evaluator alone.

Run from the repo root:

    uv run recipes/07-eval-agent-suite/main.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from strands import Agent
from strands_evals import Case, Experiment
from strands_evals.evaluators import Contains, Evaluator, OutputEvaluator
from strands_evals.types import EvaluationData, EvaluationOutput

# Make the repo root importable so `shared` resolves when run directly.
sys.path.append(str(Path(__file__).resolve().parents[2]))

from shared.model import build_model  # noqa: E402

HERE = Path(__file__).resolve().parent
# Reuse recipe 01's SOP verbatim — the agent we're evaluating IS recipe 01.
SOP = (HERE.parent / "01-sop-agent" / "sop.md").read_text()


# --- The agent under test ---------------------------------------------------
# Same construction as recipe 01: the SOP is the system prompt, and we kick it
# off with the incident. A fresh agent per case keeps the tests independent.
def run_triage(case: Case) -> str:
    agent = Agent(model=build_model(), system_prompt=SOP, callback_handler=None)
    return str(agent(f"Start the incident triage SOP.\n\n{case.input}"))


# --- A custom deterministic evaluator: SOP step coverage --------------------
# The SOP says to address each step under a "Step N: <title>" heading. That's a
# structural contract we can verify without a model: are all six headings there?
class StepCoverage(Evaluator[str, str]):
    """Pass only if the report contains a 'Step 1'..'Step N' heading for each step."""

    def __init__(self, num_steps: int = 6, name: str | None = None):
        super().__init__(name=name)
        self.num_steps = num_steps

    def evaluate(self, evaluation_case: EvaluationData[str, str]) -> list[EvaluationOutput]:
        text = evaluation_case.actual_output or ""
        # Match "Step 3", "Step 3:", "**Step 3:**", "### Step 3" — heading noise
        # varies, the step number doesn't.
        present = {n for n in range(1, self.num_steps + 1)
                   if re.search(rf"Step\s+{n}\b", text)}
        missing = [n for n in range(1, self.num_steps + 1) if n not in present]
        score = len(present) / self.num_steps

        return [EvaluationOutput(
            score=score,
            test_pass=not missing,
            label="step_coverage",
            reason=("all steps present" if not missing
                    else f"missing step(s): {missing}"),
        )]


# --- Cases: incidents with a known correct triage ---------------------------
# expected_output is a reference for the judge: the severity we'd expect and the
# escalation that must follow from it. The high-severity case is recipe 01's own
# incident; the second is a genuinely minor one that should NOT escalate.
HIGH_SEV_INCIDENT = """\
Alert: HighErrorRate on service "checkout-api" (us-east-1)

Health metrics:
- error_rate: 8.2% (baseline 0.3%)
- p99_latency: 2400ms (baseline 180ms)
- status: DEGRADED

Recent logs (last 15m):
- ConnectionPoolTimeout: could not acquire connection from pool
  (1,204 occurrences, 91% of errors)
"""

LOW_SEV_INCIDENT = """\
Alert: ElevatedLatency on service "nightly-report-exporter" (us-west-2)

Health metrics:
- error_rate: 0.0% (baseline 0.0%)
- p99_latency: 950ms (baseline 700ms)
- status: HEALTHY

Recent logs (last 15m):
- INFO: export batch completed in 41s (usual 28s); no errors
- This is an internal, non-customer-facing nightly job with no SLA.
"""

CASES = [
    Case[str, str](
        name="checkout-outage",
        input=HIGH_SEV_INCIDENT,
        expected_output=(
            "A SEV1 or SEV2 classification justified by the 8.2% error rate and "
            "2400ms p99 (far above baseline) and the ConnectionPoolTimeout "
            "signature, WITH escalation to the on-call engineer."
        ),
        metadata={"expected_severity": "SEV1/SEV2", "should_escalate": True},
    ),
    Case[str, str](
        name="slow-nightly-job",
        input=LOW_SEV_INCIDENT,
        expected_output=(
            "A SEV3 classification: latency is only mildly elevated, there are no "
            "errors, and the job is internal with no SLA — so NO escalation is "
            "needed."
        ),
        metadata={"expected_severity": "SEV3", "should_escalate": False},
    ),
]


# The judge focuses on SOP adherence and internal consistency, not prose quality.
RUBRIC = """
You are grading an incident-triage report produced from a six-step SOP.
Score on:
  1. Procedure   - Are all six steps worked, in order, using the given telemetry?
  2. Severity    - Is the SEV1/SEV2/SEV3 classification justified by the actual
                   metrics and logs (not guessed)?
  3. Consistency - Does the escalation decision MATCH the severity? (SEV1/SEV2 =>
                   escalate to on-call; SEV3 => no escalation.) A mismatch here is
                   a serious failure even if everything else is fine.
The ExpectedOutput describes the correct severity and escalation for this
incident — compare against it.
Score 1.0 if the procedure is followed and the severity + escalation are correct
and consistent. Score 0.5 for the right severity but an inconsistent or missing
escalation decision, or a skipped step. Score 0.0 for the wrong severity.
Pass only when severity and escalation are both correct.
"""


def main() -> None:
    evaluators = [
        Contains("TRIAGE SUMMARY"),          # required section, verified for free
        StepCoverage(num_steps=6),           # custom structural contract
        OutputEvaluator(rubric=RUBRIC, model=build_model(), include_inputs=True),
    ]

    experiment = Experiment[str, str](cases=CASES, evaluators=evaluators)

    print("Evaluating the recipe 01 SOP agent...\n" + "=" * 60)
    report = experiment.run_evaluations(run_triage)
    report.display()

    # Group the parallel result lists by case so you can see, per incident, how
    # every evaluator voted — the real value of a multi-evaluator suite.
    print("=" * 60)
    by_case: dict[str, list[int]] = {}
    for i, row in enumerate(report.cases):
        by_case.setdefault(row.get("name"), []).append(i)

    for name, idxs in by_case.items():
        all_pass = all(report.test_passes[i] for i in idxs)
        print(f"\n{name}  —  {'ALL PASS' if all_pass else 'HAS FAILURES'}")
        for i in idxs:
            mark = "PASS" if report.test_passes[i] else "FAIL"
            print(f"  [{mark}] {report.cases[i].get('evaluator'):<16} "
                  f"score={report.scores[i]:.2f}  {report.reasons[i]}")

    pass_rate = sum(report.test_passes) / len(report.test_passes)
    print(f"\nOverall score: {report.overall_score:.2f}   "
          f"Checks passed: {sum(report.test_passes)}/{len(report.test_passes)} "
          f"({pass_rate:.0%})")


if __name__ == "__main__":
    main()
