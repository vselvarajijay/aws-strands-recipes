# Recipe 07 — A Full Eval Suite Over a Real Agent (capstone)

Recipes 04–06 each taught one kind of evaluator in isolation. This one combines
them the way you actually would: several evaluators — deterministic **and**
LLM-judged — over the **same** agent, because different guarantees need different
tools.

The agent under test is the incident-triage SOP agent from
[recipe 01](../01-sop-agent/). We reuse its `sop.md` verbatim (read straight from
the recipe 01 folder — one source of truth), so this suite tests the real agent,
not a copy.

## What each property needs, and the cheapest tool for it

| Property of a good triage report | Evaluator | Cost |
| --- | --- | --- |
| The `TRIAGE SUMMARY` section exists | `Contains("TRIAGE SUMMARY")` | free, deterministic |
| All six SOP steps are present | `StepCoverage` (custom) | free, deterministic |
| Steps followed, severity justified, escalation consistent | `OutputEvaluator` (rubric) | LLM judge |

The deterministic checks are guardrails you never want to regress and can verify
for free. The judge handles the reasoning a regex can't — *is the severity
justified by the telemetry, and does the escalation decision follow from it?*

## Files

| File | Purpose |
| --- | --- |
| `main.py` | Runs the recipe-01 SOP agent on two incidents through three evaluators. |

## Run it

```bash
uv run recipes/07-eval-agent-suite/main.py
```

## The agent under test

Constructed exactly like recipe 01 — the SOP is the system prompt, kicked off
with the incident:

```python
SOP = (HERE.parent / "01-sop-agent" / "sop.md").read_text()

def run_triage(case: Case) -> str:
    agent = Agent(model=build_model(), system_prompt=SOP, callback_handler=None)
    return str(agent(f"Start the incident triage SOP.\n\n{case.input}"))
```

## The two cases test opposite behavior

- **`checkout-outage`** — recipe 01's own incident: 8.2% error rate, 2400ms p99,
  connection-pool timeouts. Correct triage is **SEV1/SEV2 → escalate**.
- **`slow-nightly-job`** — a genuinely minor one: an internal, no-SLA batch job a
  bit slower than usual, zero errors. Correct triage is **SEV3 → do not
  escalate**.

Testing both directions matters: an agent that escalates *everything* would pass
a single high-severity case but is still broken. The judge's rubric makes
severity↔escalation **consistency** an explicit, must-pass criterion — a SEV3
that pages on-call fails even if every step is present.

## The custom `StepCoverage` evaluator

A structural contract, verified without a model — are all six `Step N` headings
there?

```python
present = {n for n in range(1, 7) if re.search(rf"Step\s+{n}\b", text)}
missing = [n for n in range(1, 7) if n not in present]
return [EvaluationOutput(score=len(present)/6, test_pass=not missing, ...)]
```

The regex tolerates heading noise (`**Step 3:**`, `### Step 3`, `Step 3 —`) —
the step number is the stable part.

## Reading a multi-evaluator report

Every case produces one row per evaluator. `main.py` regroups the flat result
lists **by case**, so you see how each incident scored across all three checks —
the whole point of a suite. In practice you'd gate a build on
`all(report.test_passes)` (see [recipe 05](../05-eval-deterministic/) for the
exit-code pattern).

## Where to go next

- Swap in your own `sop.md` and incidents to evaluate your procedure.
- Add a `TrajectoryEvaluator` ([recipe 06](../06-eval-trajectory/)) if your agent
  uses tools.
- Explore the SDK's richer evaluators (`CorrectnessEvaluator`,
  `HelpfulnessEvaluator`, `FaithfulnessEvaluator`), the `strands-evals` CLI for
  CI, and `ExperimentGenerator` for auto-generating cases —
  see the [Strands Evaluation docs](https://strandsagents.com/).
