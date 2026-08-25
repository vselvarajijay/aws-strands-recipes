# SOP: Production Incident Triage

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
If SEV1 or SEV2, escalate to the service's on-call engineer. If SEV3, state that
no escalation is needed. The decision must match the severity from step 4.

### 6. Summarize
Write a short summary: what happened, the severity, and the action taken.

## Output format

Address each step under a heading of the form `Step N: <title>`. Finish with a
section titled `TRIAGE SUMMARY`.
