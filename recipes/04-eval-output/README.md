# Recipe 04 — Output Evaluation (LLM-as-judge)

The foundational eval: score an agent's **answers** against a rubric you write,
graded by a second model acting as judge. Use this when what you care about is
the quality of the final text — correctness, relevance, clarity.

This is the first of four evaluation recipes (04–07). It introduces the pieces
the others build on: `Case`, a task function, an evaluator, and an `Experiment`.

## The mental model

```
Case         one test: an input, and optionally an expected_output (a reference)
task(case)   runs your agent on the case, returns its answer as text
Evaluator    scores the answer — here an LLM judge grading against your rubric
Experiment   runs every case through the task, then every evaluator, → a report
```

The judge is itself a Strands model, built with the same `shared/model.py`
factory as every other recipe — so this runs on one `ANTHROPIC_API_KEY`, no
Bedrock setup, even though the upstream eval docs default to Bedrock.

## Files

| File | Purpose |
| --- | --- |
| `main.py` | Three Q&A cases, an `OutputEvaluator` with a rubric, and the report. |

## Run it

```bash
uv run recipes/04-eval-output/main.py
```

You'll see a summary table, then a per-case breakdown with the judge's full
reasoning for each score, and an overall score + pass rate.

## How it works

```python
def answer_question(case: Case) -> str:
    agent = Agent(model=build_model(), system_prompt=..., callback_handler=None)
    return str(agent(case.input))            # a fresh agent per case = clean-room tests

evaluator = OutputEvaluator(rubric=RUBRIC, model=build_model(), include_inputs=True)
report = Experiment(cases=CASES, evaluators=[evaluator]).run_evaluations(answer_question)
report.display(include_actual_output=True, include_expected_output=True)
```

Two things worth internalizing:

- **`expected_output` is a reference, not a string match.** The judge compares
  *meaning*, so an expected `"Paris"` is satisfied by `"The capital of France is
  Paris."` If you want exact-string matching, that's the deterministic `Equals`
  evaluator in [recipe 05](../05-eval-deterministic/).
- **The rubric is the whole game.** It defines what "good" means and how to map
  it onto a 0.0–1.0 score. Spell out what each score level means; a vague rubric
  produces noisy scores. `include_inputs=True` lets the judge see the original
  question so it can tell whether the answer is on-topic.

## `display()` vs `run_display()`

`report.display(...)` renders a static table — use it in scripts and CI.
`report.run_display(...)` is the same table but **interactive** (it waits for
keypresses to expand rows), so only use it at a real terminal.

## Reading results in code

`EvaluationReport` exposes parallel lists indexed by case: `report.scores`,
`report.test_passes`, `report.reasons`, plus `report.overall_score`. The
per-case breakdown in `main.py` is built from those — the same handles you'd use
to gate a build (see [recipe 05](../05-eval-deterministic/) for a CI gate).

## Next

- [05 — Deterministic evaluators](../05-eval-deterministic/): fast, no-LLM checks
  for CI.
- [06 — Trajectory evaluation](../06-eval-trajectory/): did the agent use the
  right *tools*?
- [07 — Agent eval suite](../07-eval-agent-suite/): a combined suite over a real
  agent from recipe 01.
