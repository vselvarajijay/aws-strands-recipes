"""The supervisor agent for Recipe 02 — the harness.

The supervisor watches the worker's progress and gates it: after each attempt
at a step, it checks the worker's reported result against that step's exit
criteria and returns a structured verdict. If the step isn't satisfied, its
feedback is handed back to the worker for another attempt. This is what ensures
each step actually goes through before the procedure advances.
"""

from __future__ import annotations

import sys
from pathlib import Path

from pydantic import BaseModel, Field
from strands import Agent

sys.path.append(str(Path(__file__).resolve().parents[2]))

from shared.model import build_model  # noqa: E402

from sop import Step  # noqa: E402


class StepVerdict(BaseModel):
    """The supervisor's structured judgment of one step attempt."""

    satisfied: bool = Field(
        description="True only if the step's exit criteria are fully met."
    )
    reason: str = Field(
        description="One or two sentences explaining the verdict."
    )
    guidance: str = Field(
        default="",
        description=(
            "If not satisfied, concrete feedback telling the worker what to fix. "
            "Empty when satisfied."
        ),
    )


SYSTEM_PROMPT = """\
You are a supervisor overseeing an agent that executes an SOP one step at a time.

Your job is quality control: given a step's exit criteria and the worker's
reported result, decide whether the exit criteria are FULLY met.

Be strict but fair:
- Mark satisfied=true only if every part of the exit criteria is clearly met.
- If anything is missing, vague, or unsupported, mark satisfied=false and give
  specific, actionable guidance for the retry.
- Judge only against the stated exit criteria — do not invent new requirements.
"""


def build_supervisor() -> Agent:
    """Construct the supervising agent (no tools; structured output only)."""
    return Agent(
        model=build_model(max_tokens=1024),
        system_prompt=SYSTEM_PROMPT,
        name="sop-supervisor",
        description="Verifies each SOP step meets its exit criteria.",
    )


def review_step(supervisor: Agent, step: Step, worker_result: str) -> StepVerdict:
    """Grade one step attempt against its exit criteria."""
    prompt = (
        f"Step {step.number}: {step.title}\n"
        f"Exit criteria: {step.exit_criteria}\n\n"
        f"Worker's reported result:\n{worker_result}\n\n"
        "Are the exit criteria fully met?"
    )
    return supervisor.structured_output(StepVerdict, prompt)
