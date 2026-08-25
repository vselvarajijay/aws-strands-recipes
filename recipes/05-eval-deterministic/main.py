"""Recipe 05 — deterministic evaluators: a fast, free CI gate.

Recipe 04 used an LLM judge. That's the right tool for "is this answer *good*?" —
a fuzzy, semantic question. But a lot of what you want to guarantee about an agent
isn't fuzzy at all:

    * the reply must start with the approved greeting
    * it must contain the ticket reference
    * it must never contain a forbidden phrase, and must stay under a length cap
    * a known input must produce an exact, unchanged canned response

Those are *deterministic* checks. Running an LLM to answer them would be slow,
costly, and — worst of all — non-deterministic, which is poison for a regression
gate. Strands ships deterministic evaluators for exactly this:

    Equals(value)             actual output equals value (exact)
    StartsWith(value)         actual output starts with value
    Contains(value)           value appears in the actual output
    StateEquals(name, value)  a named piece of agent state equals value
    ToolCalled(tool_name)     a tool appears in the trajectory (see recipe 06)

They call no model, so this whole recipe runs with **no ANTHROPIC_API_KEY and no
network** — the kind of check you run on every commit for free. You can also
write your own deterministic evaluator by subclassing ``Evaluator``; we do that
below with a policy check, the sort of guardrail you'd genuinely want gating a
release.

Run from the repo root:

    uv run recipes/05-eval-deterministic/main.py
"""

from __future__ import annotations

import sys

from strands_evals import Case, Experiment
from strands_evals.evaluators import Contains, Equals, Evaluator, StartsWith
from strands_evals.types import EvaluationData, EvaluationOutput

# NB: no `shared.model` import — this recipe never builds a model.


# --- The system under test --------------------------------------------------
# The "agent" here is a deterministic template layer: the fast-path responder
# many real agents put in front of the LLM for known ticket types. It's a pure
# function, which is precisely why we can pin its behavior with exact checks.
GREETING = "Hi there,"

CANNED = {
    "password_reset": (
        f"{GREETING}\n\n"
        "You can reset your password from the login screen using 'Forgot "
        "password'. The reset link is valid for 30 minutes.\n\n"
        "Reference: {ticket}\n"
        "— Support"
    ),
    "refund_status": (
        f"{GREETING}\n\n"
        "Refunds are processed within 5-7 business days and appear on the "
        "original payment method.\n\n"
        "Reference: {ticket}\n"
        "— Support"
    ),
}


def draft_reply(case: Case) -> str:
    """Render the canned reply for a ticket. `input` is {category, ticket}."""
    category = case.input["category"]
    ticket = case.input["ticket"]
    return CANNED[category].format(ticket=ticket)


# --- A custom deterministic evaluator ---------------------------------------
# Subclass Evaluator and implement evaluate(): read whatever you need off the
# EvaluationData (here just actual_output), return a list of EvaluationOutput.
# One evaluator can return several outputs, but one is the common case.
#
# This is a release guardrail: replies must not contain forbidden phrases and
# must stay within a length budget. Exactly the sort of rule you never want to
# regress, and which no LLM judgment is needed to enforce.
class PolicyCheck(Evaluator[dict, str]):
    """Fail any reply that uses a forbidden phrase or exceeds max_length."""

    FORBIDDEN = ("guarantee", "lawsuit", "as an ai")

    def __init__(self, max_length: int = 500, name: str | None = None):
        super().__init__(name=name)
        self.max_length = max_length

    def evaluate(self, evaluation_case: EvaluationData[dict, str]) -> list[EvaluationOutput]:
        text = (evaluation_case.actual_output or "").lower()

        hits = [word for word in self.FORBIDDEN if word in text]
        too_long = len(text) > self.max_length

        if hits:
            return [EvaluationOutput(
                score=0.0, test_pass=False, label="forbidden_phrase",
                reason=f"forbidden phrase(s) present: {', '.join(hits)}",
            )]
        if too_long:
            return [EvaluationOutput(
                score=0.0, test_pass=False, label="too_long",
                reason=f"reply is {len(text)} chars, over the {self.max_length} limit",
            )]
        return [EvaluationOutput(
            score=1.0, test_pass=True, label="ok",
            reason="within length budget and free of forbidden phrases",
        )]


# --- Cases ------------------------------------------------------------------
# expected_output is the exact string we expect back — Equals matches it
# character-for-character (contrast recipe 04, where the judge matched meaning).
CASES = [
    Case[dict, str](
        name="password-reset",
        input={"category": "password_reset", "ticket": "T-1001"},
        expected_output=CANNED["password_reset"].format(ticket="T-1001"),
        metadata={"category": "auth"},
    ),
    Case[dict, str](
        name="refund-status",
        input={"category": "refund_status", "ticket": "T-2002"},
        expected_output=CANNED["refund_status"].format(ticket="T-2002"),
        metadata={"category": "billing"},
    ),
]


def main() -> None:
    # A stack of deterministic evaluators — every one runs against every case.
    #   Equals       — the canned reply hasn't drifted from its approved text
    #   StartsWith   — every reply opens with the approved greeting
    #   Contains     — the ticket reference is present (input flows into output)
    #   PolicyCheck  — our custom guardrail
    evaluators = [
        Equals(),
        StartsWith(GREETING),
        Contains("Reference:"),
        PolicyCheck(max_length=500),
    ]

    experiment = Experiment[dict, str](cases=CASES, evaluators=evaluators)

    print("Running deterministic checks (no model, no network)...\n" + "=" * 60)
    report = experiment.run_evaluations(draft_reply)
    report.display(include_actual_output=True)

    # Each (case x evaluator) pair is one row in these parallel lists.
    print("=" * 60)
    for i, row in enumerate(report.cases):
        mark = "PASS" if report.test_passes[i] else "FAIL"
        print(f"  [{mark}] {row.get('name'):<16} {row.get('evaluator'):<12} "
              f"{report.reasons[i]}")

    # The CI gate: exit non-zero if anything failed, so a pipeline step goes red.
    # Everything here passes today; edit a CANNED string, drop the greeting, or
    # add a FORBIDDEN word to a reply and re-run to watch the gate catch it.
    failed = report.test_passes.count(False)
    total = len(report.test_passes)
    print(f"\n{total - failed}/{total} checks passed.")
    if failed:
        print(f"GATE: FAILED — {failed} check(s) red. Exiting non-zero.")
        sys.exit(1)
    print("GATE: PASSED — safe to ship.")


if __name__ == "__main__":
    main()
