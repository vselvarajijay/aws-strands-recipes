# Recipe 02 — Supervised SOP Agent

The SOP agent from Recipe 01, wrapped in a **harness**: a second agent watches
the worker's progress and verifies that each step actually meets its exit
criteria before the procedure is allowed to advance. If a step falls short, the
supervisor sends it back with feedback and the worker retries.

## What it shows

- A two-agent **worker + supervisor** pattern (an evaluator / gate loop).
- Executing a procedure **one step at a time** with a persistent worker agent.
- Using **structured output** (a Pydantic model) so the supervisor returns a
  machine-checkable verdict, not prose.
- Gating progress: a step must pass review before the next begins; a step that
  fails `MAX_ATTEMPTS` times aborts the run for a human to take over.

## Files

| File | Purpose |
| --- | --- |
| `sop.py` | The SOP as structured `Step`s, each with an instruction and **exit criteria**. |
| `worker.py` | The worker agent + tools; executes one step per call. |
| `supervisor.py` | The supervisor agent; grades a step against its exit criteria (`StepVerdict`). |
| `main.py` | The supervision loop that ties them together. |

## Run it

From the repo root (after completing the setup in the top-level README):

```bash
uv run recipes/02-sop-supervised/main.py
```

## How it works

For each step in the SOP:

1. **Worker attempts the step.** A single `strands.Agent` is reused across
   steps so it keeps the full history of what it found earlier. It's told to do
   *only* the current step and to end with a `RESULT:` line.
2. **Supervisor reviews.** A separate agent compares the worker's reported
   result to the step's `exit_criteria` and returns a `StepVerdict`
   (`satisfied`, `reason`, `guidance`) via Strands' `structured_output`.
3. **Gate.** If satisfied, advance to the next step. If not, feed the
   supervisor's `guidance` back to the worker and retry, up to `MAX_ATTEMPTS`.

Because the exit criteria are explicit (e.g. step 4 requires a severity *and* a
justification that references earlier metrics), the supervisor has a concrete
bar to hold the worker to — that's what makes the gate meaningful rather than a
rubber stamp.

## Why the SOP is structured here

Recipe 01 passes the SOP as free-form markdown. This recipe models it as a list
of `Step` objects so the supervisor can grade each step against its own exit
criteria. In a production system you might parse those steps out of a document;
here they're defined directly in `sop.py` to keep the harness easy to follow.
