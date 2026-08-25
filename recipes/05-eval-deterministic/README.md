# Recipe 05 — Deterministic Evaluators (a free CI gate)

Recipe 04 used an LLM judge to answer a fuzzy question ("is this answer *good*?").
A lot of what you want to guarantee about an agent isn't fuzzy — it's exact:

- the reply **starts with** the approved greeting
- it **contains** the ticket reference
- it **never contains** a forbidden phrase and stays under a length cap
- a known input produces an **exact, unchanged** canned response

Those are deterministic checks. Answering them with an LLM would be slow, costly,
and non-deterministic — poison for a regression gate. So this recipe uses
Strands' deterministic evaluators, which call **no model**: the whole thing runs
with **no `ANTHROPIC_API_KEY` and no network**, the kind of check you run on
every commit for free.

## Built-in deterministic evaluators

| Evaluator | Passes when… |
| --- | --- |
| `Equals(value)` | actual output equals `value` exactly |
| `StartsWith(value)` | actual output starts with `value` |
| `Contains(value)` | `value` appears in the actual output |
| `StateEquals(name, value)` | a named piece of agent state equals `value` |
| `ToolCalled(tool_name)` | a tool appears in the trajectory (see [recipe 06](../06-eval-trajectory/)) |

`Equals` here is exact-string matching — the deterministic counterpart to recipe
04's semantic `expected_output`.

## Files

| File | Purpose |
| --- | --- |
| `main.py` | A deterministic reply layer, a stack of built-in checks, a custom `PolicyCheck`, and a CI gate. |

## Run it

```bash
uv run recipes/05-eval-deterministic/main.py
echo $?     # 0 when green, 1 when any check fails
```

No key needed — it never builds a model.

## The system under test

The "agent" is a deterministic template layer — the fast-path responder many
real agents put in front of the LLM for known ticket types. Because it's a pure
function, we can pin its behavior with exact checks and catch any drift.

## Writing a custom evaluator

Subclass `Evaluator`, implement `evaluate()`, return a list of `EvaluationOutput`:

```python
class PolicyCheck(Evaluator[dict, str]):
    FORBIDDEN = ("guarantee", "lawsuit", "as an ai")

    def evaluate(self, evaluation_case: EvaluationData[dict, str]) -> list[EvaluationOutput]:
        text = (evaluation_case.actual_output or "").lower()
        hits = [w for w in self.FORBIDDEN if w in text]
        if hits:
            return [EvaluationOutput(score=0.0, test_pass=False,
                                     reason=f"forbidden: {', '.join(hits)}")]
        return [EvaluationOutput(score=1.0, test_pass=True, reason="clean")]
```

`evaluate()` reads whatever it needs off the `EvaluationData` (here just
`actual_output`) and is plain synchronous Python — no model call. This is the
same interface the built-in deterministic evaluators implement.

## The CI gate

`main.py` ends by exiting non-zero if any check failed:

```python
failed = report.test_passes.count(False)
if failed:
    sys.exit(1)   # pipeline step goes red
```

Everything passes today. To watch the gate catch a regression, edit a `CANNED`
string, drop the greeting, or add a forbidden word to a reply — then re-run and
check `echo $?`.

## When to use which

| Question | Use |
| --- | --- |
| "Is the answer good / correct / relevant?" (fuzzy) | LLM judge — [recipe 04](../04-eval-output/) |
| "Does the output match this rule exactly?" (crisp) | deterministic — this recipe |
| "Did the agent call the right tools?" | trajectory — [recipe 06](../06-eval-trajectory/) |

In practice you combine them: [recipe 07](../07-eval-agent-suite/) runs
deterministic *and* LLM evaluators over one real agent.
