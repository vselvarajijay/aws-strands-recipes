"""Shared model factory for the recipes.

Every recipe builds its Strands model through :func:`build_model` so that the
provider configuration lives in exactly one place. We use the Anthropic API
provider; the underlying Anthropic SDK reads ``ANTHROPIC_API_KEY`` from the
environment automatically, so all we supply here is the model id and limits.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from strands.models.anthropic import AnthropicModel

# Load .env once, when this module is first imported.
load_dotenv()

# Sensible default. Override per-run with the STRANDS_MODEL env var (see
# .env.example) — e.g. claude-opus-4-8 for maximum capability.
DEFAULT_MODEL = "claude-sonnet-4-6"


def build_model(
    *,
    model_id: str | None = None,
    max_tokens: int = 4096,
    **params: object,
) -> AnthropicModel:
    """Return an ``AnthropicModel`` configured from the environment.

    Args:
        model_id: Explicit model id. Defaults to ``STRANDS_MODEL`` if set,
            otherwise :data:`DEFAULT_MODEL`.
        max_tokens: Maximum tokens for a single model response.
        **params: Extra Anthropic request params (passed through as ``params``).
    """
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add "
            "your key, or export ANTHROPIC_API_KEY in your shell."
        )

    resolved = model_id or os.getenv("STRANDS_MODEL") or DEFAULT_MODEL
    return AnthropicModel(
        model_id=resolved,
        max_tokens=max_tokens,
        params=params or None,
    )
