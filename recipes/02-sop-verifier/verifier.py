"""The verifier agent for Recipe 02.

A second agent reads the SOP and the transcript the SOP agent produced, and
checks — step by step — whether each step actually went through. It returns a
structured report (via Strands' ``structured_output``) so the result is
machine-checkable, not prose.
"""

from __future__ import annotations

import sys
from pathlib import Path

from pydantic import BaseModel, Field
from strands import Agent

sys.path.append(str(Path(__file__).resolve().parents[2]))

from shared.model import build_model  # noqa: E402


class StepCheck(BaseModel):
    """Whether one SOP step was completed in the transcript."""

    step: str = Field(description="The step title or number, e.g. '4. Classify severity'.")
    completed: bool = Field(description="True if the transcript clearly performed this step.")
    note: str = Field(description="Brief evidence or the reason it's missing.")


class VerificationReport(BaseModel):
    """The verifier's judgment of the whole run."""

    all_steps_completed: bool = Field(
        description="True only if every SOP step was completed."
    )
    checks: list[StepCheck] = Field(description="One entry per SOP step, in order.")


SYSTEM_PROMPT = """\
You are a verifier. You are given a Standard Operating Procedure (SOP) and a
transcript produced by an agent that was supposed to follow it.

For each step in the SOP, decide whether the transcript actually performed that
step. Judge only against what the SOP asks for:
- completed=true only if the transcript clearly did what the step requires.
- If a step is missing, skipped, or only partially done, mark completed=false
  and say what's missing.
Return one check per SOP step, in order, plus an overall verdict.
"""


def build_verifier() -> Agent:
    """Construct the verifying agent (no tools; structured output only)."""
    return Agent(
        model=build_model(max_tokens=2048),
        system_prompt=SYSTEM_PROMPT,
        name="sop-verifier",
        description="Verifies that an SOP transcript completed every step.",
    )


def verify_run(verifier: Agent, sop_text: str, transcript: str) -> VerificationReport:
    """Check a transcript against the SOP and return a structured report."""
    prompt = (
        f"=== SOP ===\n{sop_text}\n\n"
        f"=== TRANSCRIPT ===\n{transcript}\n\n"
        "Did the agent complete every step of the SOP?"
    )
    return verifier.structured_output(VerificationReport, prompt)
