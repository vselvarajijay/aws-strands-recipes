"""The SOP for Recipe 02, modeled as structured steps.

Recipe 01 fed the SOP to the agent as free-form markdown. Here the supervisor
needs to check each step against concrete, per-step exit criteria, so we model
the procedure as a list of ``Step`` objects. Each step carries the instruction
the worker acts on and the exit criteria the supervisor grades against.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Step:
    number: int
    title: str
    instruction: str
    exit_criteria: str


INCIDENT_TRIAGE: list[Step] = [
    Step(
        number=1,
        title="Acknowledge the alert",
        instruction=(
            "Acknowledge that triage has started and record the affected "
            "service name to the incident timeline."
        ),
        exit_criteria=(
            "A finding was recorded that names the affected service and states "
            "that triage has started."
        ),
    ),
    Step(
        number=2,
        title="Check service health",
        instruction=(
            "Look up the current health of the affected service and record the "
            "error rate and latency."
        ),
        exit_criteria=(
            "The check_service_health tool was called for the affected service "
            "AND a finding records concrete error-rate and latency numbers."
        ),
    ),
    Step(
        number=3,
        title="Search recent logs",
        instruction=(
            "Search the last 15 minutes of logs for the affected service and "
            "record the single most common error signature."
        ),
        exit_criteria=(
            "The search_logs tool was called for the affected service AND a "
            "finding names a specific dominant error signature."
        ),
    ),
    Step(
        number=4,
        title="Assess severity",
        instruction=(
            "Classify the incident as SEV1, SEV2, or SEV3 based on the health "
            "metrics and logs, and record the severity."
        ),
        exit_criteria=(
            "A finding records a severity of exactly SEV1, SEV2, or SEV3 AND "
            "includes a one-sentence justification that references the metrics "
            "or logs gathered in earlier steps. A severity with no justification "
            "does NOT satisfy this step."
        ),
    ),
    Step(
        number=5,
        title="Escalate if needed",
        instruction=(
            "If the incident is SEV1 or SEV2, page the on-call engineer for the "
            "service. If it is SEV3, do not page — record that no escalation was "
            "needed."
        ),
        exit_criteria=(
            "For SEV1/SEV2: the page_oncall tool was called for the service. "
            "For SEV3: a finding states no escalation was needed. The action "
            "must match the severity assessed in step 4."
        ),
    ),
    Step(
        number=6,
        title="Write the summary",
        instruction=(
            "Record a short triage summary: what happened, the severity, and "
            "the action taken."
        ),
        exit_criteria=(
            "A finding records a summary covering all three of: what happened, "
            "the severity, and the action taken."
        ),
    ),
]
