"""Recipe 10 — snapshots: checkpoint, branch, and restore agent state.

A *snapshot* captures an agent's state (messages, state, system prompt, ...) at a
point in time as a JSON-serializable object. You can save it, restore it later,
or load it into a *different* agent — which is what makes conversation branching
and workflow recovery possible.

This recipe walks the two headline use cases from the docs:

  1. Branching  — establish shared context once, snapshot it, then fork two
                  independent conversations that both start from that checkpoint.
  2. Durability — write a snapshot to disk as JSON and reload it into a brand-new
                  Agent in a way that would survive a process restart.

Run from the repo root:

    uv run recipes/10-agent-snapshots/main.py

Docs: https://strandsagents.com/docs/user-guide/concepts/agents/snapshots/
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from strands import Agent, Snapshot

# Make the repo root importable so `shared` resolves when run directly.
sys.path.append(str(Path(__file__).resolve().parents[2]))

from shared.model import build_model  # noqa: E402

SYSTEM_PROMPT = (
    "You are a concise travel planner. Keep every reply to 2-3 short sentences. "
    "Remember the traveler's stated preferences and honor them in every suggestion."
)

# The shared context we want both branches to inherit.
SETUP = (
    "I'm planning a 3-day trip to Kyoto in spring. I'm budget-conscious and I "
    "love street food and quiet temples. Note my preferences — don't suggest "
    "anything yet."
)


def rule(title: str) -> None:
    print("\n" + "=" * 64 + f"\n{title}\n" + "=" * 64)


def main() -> None:
    # 1. Establish shared context on a base agent, then checkpoint it. ---------
    rule("1. Build shared context, then take a snapshot")
    base = Agent(model=build_model(), system_prompt=SYSTEM_PROMPT)
    base(SETUP)  # streams to stdout

    # `preset="session"` captures messages, state, conversation manager state,
    # interrupt state and model state — everything needed to resume the session.
    checkpoint = base.take_snapshot(
        preset="session",
        app_data={"label": "kyoto-context", "traveler": "Alex"},
    )
    print(
        f"\n[snapshot] schema={checkpoint.schema_version} "
        f"created_at={checkpoint.created_at} "
        f"label={checkpoint.app_data['label']!r} "
        f"messages_captured={len(checkpoint.data.get('messages', []))}"
    )

    # 2. Branch: two fresh agents fork from the SAME checkpoint. --------------
    # Each is an independent Agent, so the two conversations never see each
    # other — but both remember the traveler's preferences from the snapshot.
    rule("2a. Branch A — food-first itinerary")
    branch_a = Agent(model=build_model(), system_prompt=SYSTEM_PROMPT)
    branch_a.load_snapshot(checkpoint)
    branch_a("Plan a food-first day 1. Lean into street food.")

    rule("2b. Branch B — temples-and-gardens itinerary")
    branch_b = Agent(model=build_model(), system_prompt=SYSTEM_PROMPT)
    branch_b.load_snapshot(checkpoint)
    branch_b("Plan a temples-and-gardens day 1. Keep it calm and quiet.")

    # 3. Durability: serialize to disk and reload into a new agent. -----------
    # `to_dict()` yields plain JSON; `Snapshot.from_dict()` rebuilds it. In a
    # real system this file could be written now and read after a restart.
    rule("3. Save to disk, reload into a new agent, and continue")
    path = Path(tempfile.gettempdir()) / "kyoto-checkpoint.json"
    path.write_text(json.dumps(checkpoint.to_dict(), indent=2))
    print(f"[disk] wrote {path} ({path.stat().st_size} bytes)")

    restored = Snapshot.from_dict(json.loads(path.read_text()))
    resumed = Agent(model=build_model(), system_prompt=SYSTEM_PROMPT)
    resumed.load_snapshot(restored)
    # It still remembers the preferences captured before serialization.
    resumed("Remind me: what did I say I care about, and where am I going?")

    print(
        "\nDone. Both branches and the reloaded agent shared one checkpoint — "
        "yet each conversation evolved independently."
    )


if __name__ == "__main__":
    main()
