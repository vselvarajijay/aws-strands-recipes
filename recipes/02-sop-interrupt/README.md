# Recipe 02 — SOP Agent with a Human-in-the-Loop Interrupt

An SOP agent that **pauses for a human** before taking a high-impact action.

This builds on [recipe 01](../01-sop-agent/): the SOP is still a markdown system
prompt the agent works through step by step. The new part is escalation. When the
agent classifies an incident as SEV1/SEV2, the SOP requires it to page the
on-call engineer — but paging a human is high-impact, so the agent isn't allowed
to do it on its own. It calls the `escalate_to_oncall` tool, which **raises an
interrupt**: the run suspends mid-tool-call, a human approves or denies, and the
run resumes with that decision as the tool's result.

This is the [Strands interrupts](https://strandsagents.com/docs/user-guide/concepts/interrupts/)
feature — the SDK's built-in mechanism for human-in-the-loop workflows.

## Files

| File | Purpose |
| --- | --- |
| `sop.md` | The SOP — triage with a human-approved escalation step. Edit to change behavior. |
| `main.py` | Defines the `escalate_to_oncall` tool that interrupts, runs the agent, and drives the resume loop. |

## Run it

This recipe is **interactive** — it reads your approval from stdin:

```bash
uv run recipes/02-sop-interrupt/main.py
```

When the agent reaches escalation it prints the context and waits. Type `y` to
approve the page, or `n` (or any instruction) to deny it, and watch the SOP
finish accordingly.

## How it works

A tool raises an interrupt through its `ToolContext`. The first time
`interrupt(...)` is called it *raises out* of the tool and pauses the whole run;
when you resume with a response, the same call *returns* that response instead —
so control lands right back inside the tool and continues.

```python
@tool(context=True)
def escalate_to_oncall(service, severity, summary, tool_context: ToolContext) -> str:
    decision = tool_context.interrupt(
        "escalation-approval",
        reason={"service": service, "severity": severity, "summary": summary},
    )
    ...
```

The run stops with `stop_reason == "interrupt"`. You answer each pending
interrupt and resume the **same run** by passing the responses back into the
agent, keyed by interrupt id:

```python
result = agent(f"Start the incident triage SOP.\n\n{INCIDENT}")

while result.stop_reason == "interrupt":
    responses = []
    for interrupt in result.interrupts:
        answer = ask_human(interrupt.reason)          # interrupt.reason is the JSON you passed
        responses.append({
            "interruptResponse": {"interruptId": interrupt.id, "response": answer}
        })
    result = agent(responses)                          # resume; the tool call returns `answer`
```

Two things make this work:

- **`context=True`** injects a `ToolContext` (the parameter must be named
  `tool_context`) so the tool can call `interrupt(...)`.
- **The resume message** is a list of `interruptResponse` items, each echoing the
  `interruptId` from `result.interrupts` and carrying the human's `response`.

## What to try next

- **Deny the page:** type `n` and see the summary record escalation as denied.
- **Change severity:** edit `INCIDENT` in `main.py` to healthy metrics so the
  agent classifies SEV3 — it then finishes without ever interrupting.
- **Persist across restarts:** add a `session_manager` (e.g.
  `FileSessionManager`) so an interrupt can be answered in a *later* process.
