# SOP: Production Incident Triage

**Purpose:** Triage an incoming production alert and decide whether to escalate.

Follow every step in order. Do not skip a step, and do not move on until the
current step is complete.

## Steps

1. **Acknowledge the alert.** Record that triage has started for the given
   alert, including the affected service name.
2. **Check service health.** Look up the current health of the affected service
   and note the error rate and latency.
3. **Search recent logs.** Search the last 15 minutes of logs for the affected
   service and identify the most common error signature.
4. **Assess severity.** Based on the health metrics and logs, classify the
   incident as SEV1 (critical), SEV2 (major), or SEV3 (minor). Record the
   severity and a one-sentence justification.
5. **Escalate if needed.** If the incident is SEV1 or SEV2, page the on-call
   engineer for the service. If it is SEV3, do not page — just record that no
   escalation was needed.
6. **Write the summary.** Record a short triage summary: what happened, the
   severity, and the action taken.

## Definition of done

All six steps have been completed and a triage summary has been recorded.
