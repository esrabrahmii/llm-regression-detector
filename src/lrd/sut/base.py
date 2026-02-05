"""SUT (System-Under-Test) base — anything that takes an `input` string and
returns an output string. Concrete implementations adapt different LLM
features (the agent's planner, a generic Groq prompt, an HTTP endpoint, ...).
"""
from __future__ import annotations

from typing import Protocol


class SUT(Protocol):
    name: str

    def call(self, input: str) -> str: ...
