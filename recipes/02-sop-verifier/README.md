# Recipe 02 — SOP Verifier

Takes the SOP agent from Recipe 01 and adds a **harness**: after the SOP agent
runs, a second agent reads the transcript and verifies — step by step — that the
procedure actually went through, returning a structured report.

## What it shows

- A two-agent **doer + verifier** pattern.
- Reusing Recipe 01's `sop.md` unchanged (single source of truth for the SOP).
- **Structured output** (a Pydantic model) so the verifier returns a
  machine-checkable per-step report, not prose.

## Files

| File | Purpose |
| --- | --- |
| `main.py` | Runs the SOP agent, then verifies the transcript. |
| `verifier.py` | The verifier agent + its `VerificationReport` output schema. |

The SOP itself lives in `../01-sop-agent/sop.md`.

## Run it

From the repo root (after completing the setup in the top-level README):

```bash
uv run recipes/02-sop-verifier/main.py
```

## How it works

1. **Run the SOP agent** — the same setup as Recipe 01 (`sop.md` as the system
   prompt, the incident as the kickoff), run silently to capture its transcript.
2. **Verify** — a second agent reads the SOP and the transcript and, via
   `verifier.structured_output(VerificationReport, ...)`, returns one
   `StepCheck` (`step`, `completed`, `note`) per SOP step plus an overall
   verdict.
3. **Report** — print ✅/❌ per step and an overall pass/fail.

Because the SOP defines discrete numbered steps, the verifier has a concrete
checklist to hold the transcript against. Try deleting a step from
`../01-sop-agent/sop.md` (or making the incident ambiguous) to watch the
verifier flag the gap.
