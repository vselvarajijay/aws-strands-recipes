# Recipe 13 — Chaos Testing

Recipes 04–08 evaluate agents under *ideal* conditions — every tool returns clean
data on demand. Production isn't ideal: APIs time out, networks drop, services
return truncated garbage. **Chaos testing** asks the questions the happy-path
evals can't — when a tool fails, does the agent fail *gracefully*? Does it tell
the user clearly? Does it still deliver the part of the goal it can?

The key move is that you inject failures **without touching your agent code**. A
`ChaosPlugin` intercepts the agent's tool calls and, per test case, either
cancels a call (`Timeout`, `NetworkError`) or corrupts its response
(`CorruptValues`, `TruncateFields`, `RemoveFields`). *Which* tool fails and *how*
is data — a `ChaosCase` — not a code change.

This is the [Strands evals chaos-testing](https://strandsagents.com/docs/user-guide/evals-sdk/chaos_testing/)
workflow, kept on a single `ANTHROPIC_API_KEY` like the other eval recipes.

## Files

| File | Purpose |
| --- | --- |
| `main.py` | A weather agent with two tools, plus a chaos experiment that breaks one tool at a time and scores how well the agent copes. |

## Run it

```bash
uv run recipes/13-eval-chaos/main.py
```

It runs 8 cases (2 requests × 3 failure modes + 2 clean baselines), scores each
with three resilience judges, and prints per-case pass/fail with the judges'
reasoning and an overall resilience score.

## How it works

The agent answers weather questions using two tools (`get_weather`,
`get_forecast`). Every request asks for **both** current conditions and the
forecast, so breaking **one** tool leaves a partial goal to salvage — the
interesting case for resilience.

```python
EFFECT_MAPS = {
    "forecast_timeout":      {"tool_effects": {"get_forecast": [Timeout()]}},
    "weather_network_error": {"tool_effects": {"get_weather":  [NetworkError()]}},
    "weather_corrupted":     {"tool_effects": {"get_weather":  [CorruptValues(corrupt_ratio=1.0)]}},
}
CHAOS_CASES = ChaosCase.expand(BASE_CASES, EFFECT_MAPS, include_no_effect_baseline=True)
```

- **Pre-hook failures** (`Timeout`, `NetworkError`) cancel the tool call outright:
  the agent sees a hard error and must react to a missing result.
- **Post-hook failures** (`CorruptValues`) let the call *succeed* but replace its
  JSON fields with garbage — the subtler, nastier test, since there's no
  exception to catch. It probes whether the agent notices bad data instead of
  confidently relaying nonsense.
- **`include_no_effect_baseline=True`** adds a clean variant per request. Those
  baseline rows are your reference: chaos rows should hold up close to them.

The task body contains **zero chaos concepts** — it just builds the agent with
`plugins=[chaos]`. The `ChaosExperiment` sets the active case before each run and
the plugin reads the failures from it. The task is wrapped in
`@eval_task(TracedHandler())`, which auto-runs the agent and captures its
execution as OpenTelemetry spans — the three chaos evaluators are **trace-level**:
they grade the whole trajectory (which tool failed, how the agent reacted), not
just the final text.

Three LLM judges score each run:

| Evaluator | Question it asks |
| --- | --- |
| `FailureCommunicationEvaluator` | Was the failure explained clearly and actionably? |
| `PartialCompletionEvaluator` | How much of the goal survived the failure? |
| `RecoveryStrategyEvaluator` | Did it retry / route around / degrade sensibly? |

All three share one `build_model()` judge; left to their defaults they'd reach for
Bedrock, so passing `model=` keeps the whole recipe on one Anthropic key. Chaos
cases share a per-case `ContextVar`, so the experiment runs serially
(`max_workers=1`).

## Make it your own

- **More failure modes:** add entries to `EFFECT_MAPS`. Each map names one tool
  and one failure; test more by adding more maps, not more effects per tool.
- **Your own agent:** swap the weather tools and system prompt. The chaos plumbing
  is unchanged — it targets tools by name.
- **Tune the bar:** the judges score resilience behavior; adjust the system prompt
  (how the agent should handle failure) and watch the scores move.
