"""Definitions and weights for risk factors used in impact scoring."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RiskLevel(Enum):
    """Risk level categories."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class RiskFactor:
    """A single risk factor contributing to the overall risk score."""

    name: str
    description: str
    weight: float
    value: float = 0.0

    @property
    def weighted_score(self) -> float:
        """Calculate the weighted score for this factor."""
        return self.weight * self.value


class RiskFactors:
    """Registry of risk factors used in impact analysis."""

    def __init__(self) -> None:
        self._factors: list[RiskFactor] = self._default_factors()

    @staticmethod
    def _default_factors() -> list[RiskFactor]:
        """Return the default set of risk factors."""
        return [
            RiskFactor(
                name="dependency_count",
                description="Number of modules depending on the changed code",
                weight=0.25,
            ),
            RiskFactor(
                name="transitive_reach",
                description="Number of transitively affected modules",
                weight=0.20,
            ),
            RiskFactor(
                name="change_size",
                description="Number of lines changed",
                weight=0.15,
            ),
            RiskFactor(
                name="symbol_complexity",
                description="Complexity of affected symbols",
                weight=0.15,
            ),
            RiskFactor(
                name="centrality",
                description="Graph centrality of the changed node",
                weight=0.15,
            ),
            RiskFactor(
                name="churn_rate",
                description="Historical frequency of changes to this code",
                weight=0.10,
            ),
        ]

    @property
    def factors(self) -> list[RiskFactor]:
        """Return all registered risk factors."""
        return self._factors

    def get_factor(self, name: str) -> RiskFactor | None:
        """Get a risk factor by name."""
        for factor in self._factors:
            if factor.name == name:
                return factor
        return None

    def set_value(self, name: str, value: float) -> None:
        """Set the value for a specific risk factor."""
        factor = self.get_factor(name)
        if factor is not None:
            factor.value = max(0.0, min(1.0, value))

    def total_score(self) -> float:
        """Calculate the total risk score across all factors."""
        return sum(f.weighted_score for f in self._factors)
