"""Prompt-library identifier parsing shared by workflow display and registry APIs."""

from __future__ import annotations

import re
from dataclasses import dataclass

_PROMPT_ID_PATTERN = re.compile(r"^\s*(?P<source>.+?)\s*-\s*(?P<index>\d+)\s*$")


@dataclass(frozen=True, slots=True)
class PromptIdentifier:
    """A prompt-library identity while preserving the author's index padding."""

    source: str
    index: str

    @property
    def source_key(self) -> str:
        return self.source.casefold()

    @property
    def index_key(self) -> str:
        """Return a canonical numeric key without losing arbitrary precision."""

        return self.index.lstrip("0") or "0"

    @property
    def index_value(self) -> int:
        """Return a Python integer for callers that explicitly need arithmetic."""

        return int(self.index)

    @property
    def display(self) -> str:
        return f"{self.source} - {self.index}"


def parse_prompt_id(value: object) -> PromptIdentifier | None:
    """Parse the Xanta-style ``source - index`` identifier.

    The separator is the final hyphen before a numeric suffix, so sources may
    themselves contain hyphens. Leading zeroes remain part of ``index`` for
    display and round-tripping while ``index_key`` provides a stable
    numeric-equivalence key without imposing a database integer limit.
    """

    if not isinstance(value, str):
        return None
    match = _PROMPT_ID_PATTERN.fullmatch(value)
    if match is None:
        return None
    source = " ".join(match.group("source").split())
    if not source:
        return None
    return PromptIdentifier(source=source, index=match.group("index"))


def normalize_prompt_source(value: str) -> str:
    """Return the stable lookup key for a registry source."""

    return " ".join(value.split()).casefold()
