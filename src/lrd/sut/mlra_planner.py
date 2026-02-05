"""SUT adapter for ml-research-agent's planner.

We import the planner module from the sibling project (path configurable via
MLRA_PATH env var, default '../ml-research-agent'). The planner is a generator
that streams tokens; we collect them into a single output string.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from lrd.config import settings


class MlraPlannerSUT:
    name = "mlra-planner"

    def __init__(self, mlra_path: str | None = None):
        path = mlra_path or settings.mlra_path
        # Normalise relative to the LRD project root
        root = Path(__file__).resolve().parent.parent.parent.parent
        full = (root / path).resolve()
        if not (full / "src" / "mlra").exists():
            raise FileNotFoundError(
                f"ml-research-agent not found at {full}/src/mlra. "
                f"Set MLRA_PATH in .env to point at the project."
            )
        # Add to sys.path so we can import its planner
        src = str(full / "src")
        if src not in sys.path:
            sys.path.insert(0, src)
        # Also export GROQ_API_KEY from our settings (mlra reads its own .env
        # but if it has none, env is a clean fallback)
        if settings.groq_api_key and not os.environ.get("GROQ_API_KEY"):
            os.environ["GROQ_API_KEY"] = settings.groq_api_key
        if settings.groq_model and not os.environ.get("GROQ_MODEL"):
            os.environ["GROQ_MODEL"] = settings.groq_model

    def call(self, input: str) -> str:
        from mlra.agent.planner import stream_plan  # type: ignore

        return "".join(stream_plan(input))
