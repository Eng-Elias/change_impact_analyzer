"""Sample models module.

Provides data structures used by :mod:`main` and :mod:`utils`.
Changing this module affects both ``main`` and any test that
imports it — a good example of transitive impact.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Report:
    """A simple report wrapping computed statistics."""

    title: str
    stats: dict[str, Any] = field(default_factory=dict)

    def summary(self) -> str:
        """Return a one-line summary string."""
        total = self.stats.get("total", 0)
        count = self.stats.get("count", 0)
        return f"{self.title}: {count} items, total={total}"

    def is_empty(self) -> bool:
        """Check whether the report contains any data."""
        return self.stats.get("count", 0) == 0
