# Recipe 08 — Tool Simulation (evaluate without a backend)

Real agents call tools that hit live infrastructure — order databases, shipping
APIs, payment gateways, hardware. You can't stand all that up just to run an
eval, and even if you could, you'd want its responses **controllable** so each
test exercises a specific scenario.

Tool simulation solves this. `ToolSimulator` replaces a tool's real
implementation with an **LLM-backed stand-in**: you declare the tool's signature,
its output schema, and a plain-English description of the world it operates in,
and the simulator generates schema-valid responses on every call — no backend.

From there it's the same eval machinery as recipes 04–07: a task runs the agent
over each `Case`, and an `OutputEvaluator` judges the answer.

## The mental model

```
@tool_simulator.tool(output_schema=..., share_state_id=..., initial_state_description=...)
def get_order(order_id): ...        # NO body — the simulator produces the return value

tool_simulator.get_tool("get_order")  # an LLM-backed tool that drops into a normal Agent
```

- **`output_schema` (a Pydantic model) is mandatory.** It's what makes a
  simulated tool trustworthy: every response is forced to match your fields and
  types, so the agent gets the same well-formed shape a real service would return
  — never a paragraph it has to parse.
- **`share_state_id` + `initial_state_description` seed a shared world.** Tools in
  the same state group draw from one seeded backend, so their answers stay
  mutually consistent across calls: look up an order, then check its item's stock,
  and the SKU and stock level tell *one coherent story*.

## Files

| File | Purpose |
| --- | --- |
| `main.py` | Two simulated store tools sharing a seeded backend, an agent that uses them, and an `OutputEvaluator` over three cases. |

## Run it

```bash
uv run recipes/08-eval-tool-simulation/main.py
```

You'll see the eval report and per-case breakdown, then a dump of every tool call
the **simulated backend** recorded during the run — a handy debugging view.

## How it works

```python
tool_simulator = ToolSimulator(model=build_model())   # runs on Anthropic, not Bedrock

@tool_simulator.tool(
    share_state_id="store_backend",
    initial_state_description=STORE_STATE,   # seeds the world once
    output_schema=OrderStatus,               # forces schema-valid responses
)
def get_order(order_id: str) -> dict: ...    # no body

agent = Agent(tools=[tool_simulator.get_tool("get_order"), ...], ...)
```

The simulator defaults to **Bedrock** if you don't pass a model; we pass
`build_model()` so the agent, the LLM judge, *and* the simulated tools all run on
one `ANTHROPIC_API_KEY` — nothing else to configure.

## Shared state is the point

`get_order` and `check_inventory` share the `store_backend` state group, seeded
with a specific scenario (order `O-1001` is a `BLUE-WIDGET`, delayed;
`BLUE-WIDGET` is out of stock). When a case asks for a replacement of a delayed
item, the agent calls **both** tools — and because they share state, the "item is
out of stock" answer stays consistent with the "this order is for that item"
answer. That coherence across calls is what a pile of independent canned strings
(recipe 06) can't give you.

Inspect it after a run:

```python
state = tool_simulator.get_state("store_backend")
for call in state["previous_calls"]:
    print(call["tool_name"], call["parameters"], "->", call["response"])
```

## Simulated tools vs. canned tools (recipe 06)

Recipe 06's tools returned hard-coded strings — fine when the data is trivial and
fixed. Reach for **simulation** when you want a *seeded, self-consistent world*
without writing the backend: many entities, cross-tool consistency, or scenarios
you'd rather describe in prose than hand-code. The scores reflect the agent's
actual answers, so they can vary run to run — that's a real eval, not a fixture.

## Next

- [04 — Output evaluation](../04-eval-output/): the LLM-as-judge this recipe reuses.
- [06 — Trajectory evaluation](../06-eval-trajectory/): checking *which* tools ran.
- [07 — Agent eval suite](../07-eval-agent-suite/): deterministic + LLM evaluators
  combined over a real agent.
