# Recipe 06 — Trajectory Evaluation (did it use the right tools?)

Recipes 04 and 05 judged the agent's final text. A tool-using agent, though, can
reach a right-looking answer the *wrong way*: refunding an order without looking
it up first, using an expensive tool where a cheap one would do, or calling
nothing and hallucinating the result. To catch that, evaluate the **trajectory** —
the ordered sequence of tools the agent actually called.

## The flow

```
run_agent(case)         runs the agent, then extracts the tool trajectory
   │                    from agent.messages and returns {output, trajectory}
   ▼
Experiment maps trajectory → actual_trajectory on each case, then scores with:
   • TrajectoryMatches   custom, deterministic — expected tools in order? (no model)
   • TrajectoryEvaluator LLM judge — was the tool use appropriate? (nuance)
```

Each `Case` carries its **own** `expected_trajectory`, so different requests
expect different tool paths — something a single global `ToolCalled(name)` check
(recipe 05) can't express. Use `ToolCalled` when every case must hit the same
tool; use a trajectory evaluator for per-case expectations.

## Files

| File | Purpose |
| --- | --- |
| `main.py` | Three custom tools, a store-ops agent, and two trajectory evaluators. |

## Run it

```bash
uv run recipes/06-eval-trajectory/main.py
```

## Capturing the trajectory

```python
used = tools_use_extractor.extract_agent_tools_used_from_messages(agent.messages)
trajectory = [step["name"] for step in used]        # ordered list of tool names
return {"output": str(response), "trajectory": trajectory}
```

The extractor returns rich dicts (`name`, `input`, `result`, …). We reduce to
the ordered list of **names** for two reasons: deterministic name-matching needs
plain strings, and a short trajectory keeps the LLM judge's context small (the
upstream docs' "prevent context overflow" advice). The `{output, trajectory}`
dict maps onto the case's `actual_output` and `actual_trajectory`.

## The interesting case: order matters

The agent's rule is *never refund without looking the order up first*. The
`refund-after-lookup` case encodes that as `expected_trajectory=["get_order",
"issue_refund"]`. A plain "was `issue_refund` called?" check would pass even if
the agent refunded blindly — the trajectory check only passes when `get_order`
comes **first**.

## Two evaluators, two jobs

- **`TrajectoryMatches`** (custom, deterministic): passes when the expected tool
  names appear in the actual trajectory *in order* (extra steps allowed). It's an
  in-order subsequence match, written out in `main.py` so you can see exactly
  what it checks — fast, free, and respects each case's own expectation.
- **`TrajectoryEvaluator`** (LLM judge): scores *appropriateness* against a
  rubric — right tools, right order, no waste — for the nuance a strict matcher
  misses. We feed it short tool descriptions via
  `extract_tools_description(agent, is_short=True)` +
  `update_trajectory_description(...)` so it can reason about tool choice. Its
  system prompt also exposes `exact_match_scorer` / `in_order_match_scorer` /
  `any_order_match_scorer` as tools the judge can call to seed its score.

## When to use which trajectory check

| Need | Use |
| --- | --- |
| Every case must call one specific tool | `ToolCalled("name")` (recipe 05) |
| Per-case expected tool sequence, exact rule | custom `TrajectoryMatches` (this recipe) |
| "Was the tool use *sensible*?" | `TrajectoryEvaluator` (this recipe) |

## Next

[Recipe 07](../07-eval-agent-suite/) combines output, deterministic, and custom
evaluators into one suite over a real agent from recipe 01.
