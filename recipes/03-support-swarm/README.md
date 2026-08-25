# Recipe 03 — A Support Swarm that Self-Organizes

A team of **specialized agents** that decide among themselves how to work an
enterprise support case — no central router you have to write.

The first two recipes drive a single agent through a fixed procedure. Operations
work isn't that tidy: when a case comes in, *who* needs to touch it and in *what
order* depends on what the case turns out to be. A billing question goes one way;
a production outage on a renewal-risk account goes another and needs several
hands.

A [Strands Swarm](https://strandsagents.com/docs/user-guide/concepts/multi-agent/swarm/)
models this directly. You give it a team and a case. Every agent gets a
`handoff_to_agent` tool for free and the team **shares one working context**, so
each agent decides — from what it has learned — whether to finish the case or
hand off to a teammate. The swarm ends when an agent stops handing off (resolved)
or a safety limit trips.

## The team

| Agent | Owns | Entry point? |
| --- | --- | --- |
| `triage` | First-line classification and routing | **yes** |
| `technical_support` | Diagnosis, root cause, workarounds (has a `search_runbooks` tool) | |
| `account_manager` | Entitlements, SLA/credits, the customer-facing reply (has a `lookup_account` tool) | |
| `escalation_manager` | SEV1 / at-risk incident command: paging, comms cadence, credits | |

The case starts at `triage`. Everything after that is the agents' call.

## Files

| File | Purpose |
| --- | --- |
| `main.py` | Defines the four specialists, their tools, and the swarm; runs a case and renders the path. |

The agents' role prompts live inline in `main.py` as `*_PROMPT` constants — edit
them to change how the team divides the work and when it hands off.

## Run it

```bash
uv run recipes/03-support-swarm/main.py
```

It works one urgent case (a production webhook outage on a top-tier account that's
also up for renewal) and prints the **handoff path** the swarm chose plus the
final customer reply. Because agents decide routing at runtime, the exact path
varies between runs — that's the point.

## How it works

Build named agents, then wrap them in a `Swarm`:

```python
from strands import Agent
from strands.multiagent import Swarm

triage = Agent(name="triage", model=model, system_prompt=TRIAGE_PROMPT)
technical_support = Agent(name="technical_support", model=model,
                          system_prompt=TECH_PROMPT, tools=[search_runbooks])
# ...account_manager, escalation_manager...

swarm = Swarm(
    [triage, technical_support, account_manager, escalation_manager],
    entry_point=triage,
    max_handoffs=10,
    max_iterations=10,
    execution_timeout=300.0,
    node_timeout=120.0,
    repetitive_handoff_detection_window=6,   # look at the last 6 hops...
    repetitive_handoff_min_unique_agents=3,  # ...they must include >=3 agents
)

result = swarm(CASE)   # blocks until resolved or a limit trips
```

Two ideas do the heavy lifting:

- **The `name` is the address.** Strands auto-injects a `handoff_to_agent` tool
  into every agent; an agent hands off by naming a teammate. So the *routing
  logic lives in the prompts*, not in your code — each prompt says what that agent
  owns and **when to hand off**. That's what keeps the team from ping-ponging or
  trying to do everything at once.
- **Shared context.** A handoff carries the accumulated history, so the next
  agent picks up where the last left off instead of starting cold.

Reading the result:

```python
result.status                       # COMPLETED / FAILED / ...
result.node_history                 # ordered agents that took control = the path
result.execution_count              # how many agent turns ran
result.results[node_id].result      # a given agent's output (AgentResult)
```

`node_history` is the swarm's self-chosen route — printing it is the clearest way
to *see* the team organize itself.

## Safety rails

A team of agents can loop. The constructor limits are the guardrails:

- `max_handoffs` / `max_iterations` — hard caps on hops and total turns.
- `execution_timeout` / `node_timeout` — wall-clock limits for the whole run and
  for any single agent.
- `repetitive_handoff_detection_window` + `repetitive_handoff_min_unique_agents` —
  ping-pong detection: if the last *window* hops don't involve at least *N*
  distinct agents, the swarm stops instead of bouncing A→B→A→B forever.

## What to try next

- **Change the case.** Edit `CASE` in `main.py` to a plain billing question and
  watch the swarm route to `account_manager` and finish — never engaging
  escalation.
- **Watch it live.** Swap the blocking `swarm(CASE)` for streaming to see handoffs
  as they happen:

  ```python
  async for event in swarm.stream_async(CASE):
      if event.get("type") == "multiagent_handoff":
          print(f"handoff: {event['from_node_ids']} -> {event['to_node_ids']}")
  ```

- **Add a specialist.** Drop in a `security_response` agent for suspected-breach
  cases and give the other prompts permission to hand off to it.
- **Give tools teeth.** `search_runbooks` and `lookup_account` are mocked — wire
  them to your real knowledge base and CRM.
