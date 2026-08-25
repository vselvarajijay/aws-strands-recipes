# SOP: Production Incident Triage (with human-approved escalation)

## Overview

Triage an incoming production alert using the telemetry provided in the request,
then produce a triage report. Work through every step in order and do not skip
any step.

## Steps

### 1. Acknowledge
Name the affected service and confirm that triage has started.

### 2. Assess service health
Read the provided health metrics. State the error rate and latency, and how they
compare to baseline.

### 3. Review recent logs
From the provided log summary, identify the single dominant error signature.

### 4. Classify severity
Classify the incident as SEV1, SEV2, or SEV3. Give a one-sentence justification
that references the metrics or logs above.

### 5. Decide escalation
- If SEV1 or SEV2, the incident **must** be escalated to the service's on-call
  engineer. Paging a human on-call is a high-impact action, so you may not do it
  on your own authority: call the `escalate_to_oncall` tool to request approval.
  Pass the affected service, the severity, and a one-line summary. The tool
  returns the human reviewer's decision.
  - If the decision approves the page, record that the on-call engineer was paged.
  - If the decision denies the page, do **not** treat the incident as escalated.
    Record that escalation was denied and note any instruction the reviewer gave.
- If SEV3, state that no escalation is needed and do not call the tool.

### 6. Summarize
Write a short summary: what happened, the severity, and the action actually
taken (paged / denied / no escalation), reflecting the reviewer's decision.

## Output format

Address each step under a heading of the form `Step N: <title>`. Finish with a
section titled `TRIAGE SUMMARY`.
