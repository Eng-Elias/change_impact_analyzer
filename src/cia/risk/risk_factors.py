"""Definitions and weights for risk factors used in impact scoring."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class RiskLevel(str, Enum):
    """Risk level categories with colour hints.

    - **LOW** (0–25): Safe to proceed.
    - **MEDIUM** (26–50): Review recommended.
    - **HIGH** (51–75): Thorough review required.
    - **CRITICAL** (76–100): Block commit without override.
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskFactorType(str, Enum):
    """Canonical risk-factor identifiers."""

    COMPLEXITY = "complexity"
    CHURN = "churn"
    DEPENDENTS = "dependents"
    TEST_COVERAGE = "test_coverage"
    CHANGE_SIZE = "change_size"
    CRITICAL_PATH = "critical_path"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class RiskFactor:
    """A single risk factor contributing to the overall risk score."""

    name: str
    factor_type: RiskFactorType
    description: str
    weight: float
    value: float = 0.0  # raw score 0–100

    @property
    def weighted_score(self) -> float:
        """Return the contribution of this factor (0–100 * weight)."""
        return self.weight * self.value


@dataclass
class RiskScore:
    """Result of a complete risk evaluation."""

    overall_score: float = 0.0  # 0–100
    level: RiskLevel = RiskLevel.LOW
    factor_scores: dict[str, float] = field(default_factory=dict)
    explanations: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Default weight configuration
# ---------------------------------------------------------------------------

DEFAULT_WEIGHTS: dict[str, float] = {
    RiskFactorType.COMPLEXITY: 0.05,
    RiskFactorType.CHURN: 0.05,
    RiskFactorType.DEPENDENTS: 0.50,
    RiskFactorType.TEST_COVERAGE: 0.20,
    RiskFactorType.CHANGE_SIZE: 0.10,
    RiskFactorType.CRITICAL_PATH: 0.10,
}

_FACTOR_DESCRIPTIONS: dict[str, str] = {
    RiskFactorType.COMPLEXITY: "Cyclomatic complexity of changed code",
    RiskFactorType.CHURN: "How often this file has changed recently",
    RiskFactorType.DEPENDENTS: "Number of modules depending on this",
    RiskFactorType.TEST_COVERAGE: "Test coverage of affected code",
    RiskFactorType.CHANGE_SIZE: "Number of lines added/deleted",
    RiskFactorType.CRITICAL_PATH: "Whether the code is in a critical/high-traffic path",
}


# ---------------------------------------------------------------------------
# RiskFactors registry
# ---------------------------------------------------------------------------


class RiskFactors:
    """Registry of risk factors used in impact analysis."""

    def __init__(self, weights: dict[str, float] | None = None) -> None:
        w = weights or DEFAULT_WEIGHTS
        self._factors: list[RiskFactor] = [
            RiskFactor(
                name=ft.value,
                factor_type=ft,
                description=_FACTOR_DESCRIPTIONS.get(ft, ft.value),
                weight=w.get(ft, w.get(ft.value, 0.0)),
            )
            for ft in RiskFactorType
        ]

    @property
    def factors(self) -> list[RiskFactor]:
        """Return all registered risk factors."""
        return self._factors

    def get_factor(self, name: str) -> RiskFactor | None:
        """Get a risk factor by name (or by *RiskFactorType* value)."""
        for factor in self._factors:
            if factor.name == name or factor.factor_type == name:
                return factor
        return None

    def set_value(self, name: str, value: float) -> None:
        """Set the raw score (0–100) for a factor, clamped to [0, 100]."""
        factor = self.get_factor(name)
        if factor is not None:
            factor.value = max(0.0, min(100.0, value))

    def total_score(self) -> float:
        """Return the weighted total across all factors (0–100)."""
        return sum(f.weighted_score for f in self._factors)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def score_to_level(score: float) -> RiskLevel:
    """Map a numeric 0–100 score to a *RiskLevel*."""
    if score >= 76:
        return RiskLevel.CRITICAL
    if score >= 51:
        return RiskLevel.HIGH
    if score >= 26:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW
