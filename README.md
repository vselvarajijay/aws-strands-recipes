# AWS Strands Recipes

Small, self-contained, runnable examples for building agents with the
[AWS Strands Agents](https://github.com/strands-agents/sdk-python) SDK.

Each recipe lives in its own folder under `recipes/`, has its own README, and
runs on its own. They share one dependency set and one model configuration.

## Recipes

**Building agents**

| # | Recipe | What it shows |
| --- | --- | --- |
| 01 | [SOP Agent](recipes/01-sop-agent/) | An agent that runs a Standard Operating Procedure defined as a markdown system prompt. |
| 02 | [SOP Agent with Interrupt](recipes/02-sop-interrupt/) | An SOP agent that pauses for human approval before a high-impact step, using Strands interrupts (human-in-the-loop). |
| 03 | [Support Swarm](recipes/03-support-swarm/) | A swarm of specialist agents that self-organize via handoffs to work an enterprise support case — no central router. |

**Evaluating agents** (with the [`strands-agents-evals`](https://strandsagents.com/) SDK)

| # | Recipe | What it shows |
| --- | --- | --- |
| 04 | [Output Evaluation](recipes/04-eval-output/) | The foundational eval: score an agent's answers against a rubric with an LLM-as-judge. |
| 05 | [Deterministic Evaluators](recipes/05-eval-deterministic/) | Fast, no-LLM checks (`Equals`/`Contains`/custom) as a free CI gate that exits non-zero on failure. |
| 06 | [Trajectory Evaluation](recipes/06-eval-trajectory/) | Evaluate the *path*, not just the answer — did the agent call the right tools, in the right order? |
| 07 | [Agent Eval Suite](recipes/07-eval-agent-suite/) | Capstone: deterministic + LLM evaluators combined over the real recipe 01 SOP agent. |

The eval recipes reuse the same `shared/model.py` factory, so the LLM judge runs
on your `ANTHROPIC_API_KEY` — no Bedrock setup, even though the upstream eval
docs default to Bedrock. (Recipe 05 needs no key at all: it calls no model.)

## Setup

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12+.

```bash
# 1. Install dependencies (creates .venv automatically)
uv sync

# 2. Add your Anthropic API key
cp .env.example .env
# then edit .env and set ANTHROPIC_API_KEY
```

Get an API key at <https://console.anthropic.com/settings/keys>.

## Running a recipe

From the repo root:

```bash
uv run recipes/01-sop-agent/main.py
```

## Model configuration

Recipes default to `claude-sonnet-4-6` (a good balance of capability and cost).
Override the model for any run with the `STRANDS_MODEL` environment variable —
for example `claude-opus-4-8` for maximum capability or `claude-haiku-4-5` for
the fastest, cheapest option:

```bash
STRANDS_MODEL=claude-opus-4-8 uv run recipes/01-sop-agent/main.py
```

All recipes build their model through `shared/model.py`, which uses the Strands
Anthropic provider. To switch providers (e.g. Amazon Bedrock), change that one
file.

## Project layout

```
aws-strands-recipes/
├── README.md            # you are here
├── pyproject.toml       # shared dependencies
├── .env.example         # copy to .env and add your key
├── shared/
│   └── model.py         # one place that configures the model provider
└── recipes/
    ├── 01-sop-agent/
    ├── 02-sop-interrupt/
    ├── 03-support-swarm/
    ├── 04-eval-output/
    ├── 05-eval-deterministic/
    ├── 06-eval-trajectory/
    └── 07-eval-agent-suite/
```

## Adding a recipe

Create `recipes/NN-your-recipe/` with a `main.py` and a `README.md`, build your
model via `from shared.model import build_model`, and add a row to the table
above.
