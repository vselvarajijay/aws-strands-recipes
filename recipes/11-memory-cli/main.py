"""Recipe 11 — an agent that remembers across CLI runs.

Each time you run this script it's a brand-new process — a fresh agent with no
conversation history. What carries over is *memory*: facts the agent decided
were worth keeping, saved to a local JSON file. On the next run those relevant
facts are read back and injected into context, so the agent answers as if it
never forgot.

Strands wires this up with a `MemoryManager` over a `TestMemoryStore`:

  - The store is a zero-infrastructure JSON file on disk (persists by default).
  - `add_tool_config=True` gives the agent an `add_memory` tool, so it can
    choose to save durable facts ("my name is Vijay", "I prefer metric units").
  - `injection=True` auto-searches your message against the store each turn and
    injects the matching memories into the prompt before the model runs.

Run it once to teach it something, then again in a *separate* invocation to see
it recall — that second run is the whole point.

    uv run recipes/11-memory-cli/main.py "My name is Vijay and I prefer metric units."
    uv run recipes/11-memory-cli/main.py "What's my name, and which units do I like?"

With no message it prints this usage and the memories saved so far.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from strands import Agent
from strands.memory import MemoryManager
from strands.vended_memory_stores.test_memory_store import TestMemoryStore

# Make the repo root importable so `shared` resolves when run directly.
sys.path.append(str(Path(__file__).resolve().parents[2]))

from shared.model import build_model  # noqa: E402

HERE = Path(__file__).resolve().parent
# Keep the memory file next to the recipe so it's easy to inspect (and .gitignored).
MEMORY_FILE = HERE / ".memory" / "notes.json"

SYSTEM_PROMPT = """\
You are a helpful personal assistant with long-term memory.

When the user tells you a durable fact about themselves — their name, their
preferences, ongoing projects — save it with the add_memory tool so you'll have
it in future conversations. Don't save small talk or one-off questions.

Any memories relevant to the user's message are provided to you automatically —
use them to answer. If nothing relevant is available, say so plainly instead of
guessing.
"""


def build_agent() -> Agent:
    """An agent whose memory lives in a local JSON file (survives restarts)."""
    store = TestMemoryStore(name="personal-assistant", path=str(MEMORY_FILE))
    memory = MemoryManager(
        stores=[store],
        add_tool_config=True,  # let the agent save memories on its own
        # Auto-inject memories that match the user's message. We leave the
        # search_memory tool OFF (search_tool_config=False) so the agent can't
        # fragment recall into narrow queries that miss — injection uses the
        # whole message, which the lexical store matches far more reliably.
        search_tool_config=False,
        injection=True,
    )
    return Agent(model=build_model(), system_prompt=SYSTEM_PROMPT, memory_manager=memory)


def print_usage_and_memories() -> None:
    print(__doc__.strip())
    print("\n" + "=" * 60)
    if MEMORY_FILE.exists():
        entries = json.loads(MEMORY_FILE.read_text())
        print(f"Memories saved so far ({len(entries)}) in {MEMORY_FILE}:")
        for e in entries:
            print(f"  • {e['content']}")
    else:
        print("No memories saved yet — teach it something with a first run.")


def main() -> None:
    message = " ".join(sys.argv[1:]).strip()
    if not message:
        print_usage_and_memories()
        return

    agent = build_agent()
    print(f"You: {message}\n" + "-" * 60)
    agent(message)  # streams the reply (and any tool calls) to stdout
    print()


if __name__ == "__main__":
    main()
