# Recipe 01 — SOP Agent

An agent that executes a **Standard Operating Procedure**: you give it a
procedure written as plain-language steps plus a scenario, and it works through
the steps in order, calling tools to actually perform each one.

## What it shows

- Driving an agent's behavior with an SOP loaded from a markdown file (swap in
  your own without editing code).
- Giving the agent tools so each step does real work — and printing tool calls
  so you can watch the procedure being followed.
- A simple, single-agent pattern with no orchestration. (Recipe 02 adds a
  supervisor that verifies each step.)

## Files

| File | Purpose |
| --- | --- |
| `sops/incident_triage.md` | Example SOP — a 6-step production incident triage. |
| `agent.py` | The SOP agent and its (mock) tools. |
| `main.py` | Loads the SOP + scenario and runs the agent. |

## Run it

From the repo root (after completing the setup in the top-level README):

```bash
uv run recipes/01-sop-agent/main.py
```

Use your own procedure:

```bash
uv run recipes/01-sop-agent/main.py path/to/your_sop.md
```

## How it works

`agent.py` builds a `strands.Agent` with:

- a **system prompt** instructing it to follow the SOP one step at a time and
  record a finding for each step, and
- a set of `@tool` functions (`check_service_health`, `search_logs`,
  `page_oncall`, `record_finding`) that stand in for a real ops stack.

`main.py` reads the SOP markdown, appends it to the scenario, and calls the
agent. The agent decides which tool to use for each step and produces a final
`TRIAGE SUMMARY`.

The tools here are mocks that return canned data — replace their bodies with
real integrations to make this useful.
