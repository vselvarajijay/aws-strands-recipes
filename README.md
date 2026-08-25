# AWS Strands Recipes

Small, self-contained, runnable examples for building agents with the
[AWS Strands Agents](https://github.com/strands-agents/sdk-python) SDK.

Each recipe lives in its own folder under `recipes/`, has its own README, and
runs on its own. They share one dependency set and one model configuration.

## Recipes

| # | Recipe | What it shows |
| --- | --- | --- |
| 01 | [SOP Agent](recipes/01-sop-agent/) | An agent that runs a Standard Operating Procedure defined as a markdown system prompt. |

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
    └── 01-sop-agent/
```

## Adding a recipe

Create `recipes/NN-your-recipe/` with a `main.py` and a `README.md`, build your
model via `from shared.model import build_model`, and add a row to the table
above.
