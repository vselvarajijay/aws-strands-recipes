# Recipe 10 — Agent Snapshots

A **snapshot** captures an agent's state — messages, state, system prompt, and
more — at a point in time as a JSON-serializable object. You can save it, restore
it later, or load it into a *different* agent. That's what makes **conversation
branching** and **workflow recovery** possible.

This recipe demonstrates both headline use cases from the
[snapshots docs](https://strandsagents.com/docs/user-guide/concepts/agents/snapshots/):

1. **Branching** — establish shared context once, snapshot it, then fork two
   independent conversations that both start from that checkpoint.
2. **Durability** — write a snapshot to disk as JSON and reload it into a
   brand-new `Agent`, in a way that would survive a process restart.

## Files

| File | Purpose |
| --- | --- |
| `main.py` | Builds context, snapshots it, branches two agents from the checkpoint, then round-trips a snapshot through disk. |

## Run it

From the repo root (after completing the setup in the top-level README):

```bash
uv run recipes/10-agent-snapshots/main.py
```

## How it works

Take a snapshot with a preset (`"session"` is the only preset today, capturing
everything needed to resume a session), optionally tagging it with your own
`app_data`:

```python
checkpoint = base.take_snapshot(
    preset="session",
    app_data={"label": "kyoto-context", "traveler": "Alex"},
)
```

**Branch** by loading the same checkpoint into fresh agents. Each is independent,
so the two conversations never see each other — but both inherit the context
captured in the snapshot:

```python
branch_a = Agent(model=build_model(), system_prompt=SYSTEM_PROMPT)
branch_a.load_snapshot(checkpoint)          # food-first thread
branch_a("Plan a food-first day 1.")

branch_b = Agent(model=build_model(), system_prompt=SYSTEM_PROMPT)
branch_b.load_snapshot(checkpoint)          # temples thread
branch_b("Plan a temples-and-gardens day 1.")
```

**Persist** with `to_dict()` / `Snapshot.from_dict()` — plain JSON, so it drops
straight into a file, database, or cache:

```python
path.write_text(json.dumps(checkpoint.to_dict(), indent=2))
restored = Snapshot.from_dict(json.loads(path.read_text()))
resumed.load_snapshot(restored)
```

## Notes

- `load_snapshot` only restores fields present in the snapshot. Fields that
  weren't captured keep the agent's current value — so `include`/`exclude` let
  you snapshot, say, only `["messages", "state"]`.
- **Security:** snapshots are restored verbatim and their messages reach the
  model (tool-call blocks can execute on the next turn). Load snapshots only
  from a source you control.
