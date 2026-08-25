# Recipe 01 — SOP Agent

An agent that runs a **Standard Operating Procedure**. The SOP is a markdown
file used as the agent's system prompt; you kick it off with a single prompt and
the agent works through the steps and produces the report.

This mirrors the [strands-agents/agent-sop](https://github.com/strands-agents/agent-sop)
pattern: the SOP *is* the agent's instructions.

## Files

| File | Purpose |
| --- | --- |
| `sop.md` | The SOP — an incident-triage procedure. Edit this to change behavior. |
| `main.py` | Loads `sop.md` as the system prompt and runs the agent on an incident. |

## Run it

From the repo root (after completing the setup in the top-level README):

```bash
uv run recipes/01-sop-agent/main.py
```

## How it works

```python
SOP = (HERE / "sop.md").read_text()
agent = Agent(model=build_model(), system_prompt=SOP)
agent(f"Start the incident triage SOP.\n\n{INCIDENT}")
```

The SOP defines six numbered steps and an output format (each step under a
`Step N: <title>` heading, ending with a `TRIAGE SUMMARY`). The incident
telemetry is passed in the kickoff message, so the agent has real data to reason
over — no external tools required.

To use your own procedure, replace `sop.md`. To triage a different incident,
edit the `INCIDENT` string in `main.py`.

Recipe 02 runs this same SOP and then adds a second agent that **verifies** each
step actually went through.
