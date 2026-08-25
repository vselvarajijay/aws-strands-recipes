# Recipe 11 — Memory Across CLI Runs

An agent that **remembers you between separate runs**. Every invocation is a
fresh process with no conversation history — what persists is *memory*: durable
facts the agent chose to save to a local JSON file and reads back next time.

This is the [Strands memory](https://strandsagents.com/docs/user-guide/concepts/memory/overview/)
concept at its simplest: no database, no cloud, just a file on disk.

## Files

| File | Purpose |
| --- | --- |
| `main.py` | A small CLI: pass a message, the agent replies and may save memories. |
| `.memory/notes.json` | Where memories live (created on first save; git-ignored). |

## Run it

Teach it something in one run, then recall it in a **separate** run — the second
invocation is the whole point:

```bash
# Run 1 — tell it a durable fact
uv run recipes/11-memory-cli/main.py "My name is Vijay and I prefer metric units."

# Run 2 — brand-new process, yet it remembers
uv run recipes/11-memory-cli/main.py "What's my name, and which units do I like?"

# No message → prints usage and everything saved so far
uv run recipes/11-memory-cli/main.py
```

Between the two runs, peek at `.memory/notes.json` — you'll see the extracted
facts as plain text.

## How it works

Three lines wire up persistence:

```python
store = TestMemoryStore(name="personal-assistant", path=".memory/notes.json")
memory = MemoryManager(stores=[store], add_tool_config=True,
                       search_tool_config=False, injection=True)
agent = Agent(model=build_model(), system_prompt=SYSTEM_PROMPT, memory_manager=memory)
```

- **`TestMemoryStore`** — a zero-infrastructure store backed by a JSON file. It
  persists to disk by default, so memories outlive the process. (Recall is
  lexical keyword matching — great for demos; use a managed vector store like
  `BedrockKnowledgeBaseStore` for production semantic search.)
- **`add_tool_config=True`** — gives the agent an `add_memory` tool so it can
  decide to save durable facts. The system prompt tells it *what's* worth saving.
- **`injection=True`** — before each model call, the manager searches the store
  with your whole message and injects the matching memories into the prompt. The
  agent answers from them without any extra tool call.
- **`search_tool_config=False`** — we deliberately turn *off* the agent's
  `search_memory` tool. Left on, the model tends to fire several narrow queries
  ("unit preferences", "projects") that the lexical store misses; injection
  matches the full message and recalls far more reliably. Flip it back on when
  you move to a semantic store and want the agent to search on demand.

The agent, not your code, decides what to remember — you just give it the store
and a nudge in the system prompt.

## Make it your own

- **Change what it remembers:** edit `SYSTEM_PROMPT` in `main.py`.
- **Separate memories per user:** use a different `path`/`name` per user id.
- **Go to production:** swap `TestMemoryStore` for `BedrockKnowledgeBaseStore`
  (semantic search, managed) — the rest of the code is unchanged.
- **Persist the whole conversation** (not just facts): reach for
  `strands.session.FileSessionManager` instead, which snapshots full message
  history across runs.
