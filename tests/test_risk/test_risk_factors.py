"""Comprehensive tests for risk_factors module."""

from __future__ import annotations

import pytest

from cia.risk.risk_factors import (
    DEFAULT_WEIGHTS,
    RiskFactor,
    RiskFactors,
    RiskFactorType,
    RiskLevel,
    RiskScore,
    score_to_level,
)


# ==================================================================
# RiskLevel enum
# ==================================================================


class TestRiskLevel:
    def test_values(self) -> None:
        assert RiskLevel.LOW == "low"
        assert RiskLevel.MEDIUM == "medium"
        assert RiskLevel.HIGH == "high"
        assert RiskLevel.CRITICAL == "critical"

    def test_is_string(self) -> None:
        assert isinstance(RiskLevel.LOW, str)


# ==================================================================
# RiskFactorType enum
# ==================================================================


class TestRiskFactorType:
    def test_all_types(self) -> None:
        expected = {"complexity", "churn", "dependents", "test_coverage", "change_size", "critical_path"}
        actual = {ft.value for ft in RiskFactorType}
        assert actual == expected

    def test_is_string(self) -> None:
        assert isinstance(RiskFactorType.COMPLEXITY, str)


# ==================================================================
# RiskFactor dataclass
# ==================================================================


class TestRiskFactor:
    def test_weighted_score(self) -> None:
        rf = RiskFactor(
            name="test", factor_type=RiskFactorType.COMPLEXITY,
            description="desc", weight=0.5, value=60.0,
        )
        assert rf.weighted_score == pytest.approx(30.0)

    def test_zero_value(self) -> None:
        rf = RiskFactor(
            name="test", factor_type=RiskFactorType.CHURN,
            description="desc", weight=0.25, value=0.0,
        )
        assert rf.weighted_score == 0.0

    def test_full_value(self) -> None:
        rf = RiskFactor(
            name="test", factor_type=RiskFactorType.CHANGE_SIZE,
            description="desc", weight=1.0, value=100.0,
        )
        assert rf.weighted_score == pytest.approx(100.0)


# ==================================================================
# RiskScore dataclass
# ==================================================================


class TestRiskScore:
    def test_defaults(self) -> None:
        rs = RiskScore()
        assert rs.overall_score == 0.0
        assert rs.level == RiskLevel.LOW
        assert rs.factor_scores == {}
        assert rs.explanations == []
        assert rs.suggestions == []

    def test_with_values(self) -> None:
        rs = RiskScore(
            overall_score=55.0,
            level=RiskLevel.HIGH,
            factor_scores={"complexity": 80.0},
            explanations=["High complexity"],
            suggestions=["Review carefully"],
        )
        assert rs.overall_score == 55.0
        assert rs.level == RiskLevel.HIGH
        assert len(rs.factor_scores) == 1
        assert len(rs.explanations) == 1
        assert len(rs.suggestions) == 1


# ==================================================================
# score_to_level
# ==================================================================


class TestScoreToLevel:
    @pytest.mark.parametrize("score,expected", [
        (0.0, RiskLevel.LOW),
        (10.0, RiskLevel.LOW),
        (25.0, RiskLevel.LOW),
        (26.0, RiskLevel.MEDIUM),
        (50.0, RiskLevel.MEDIUM),
        (51.0, RiskLevel.HIGH),
        (75.0, RiskLevel.HIGH),
        (76.0, RiskLevel.CRITICAL),
        (100.0, RiskLevel.CRITICAL),
    ])
    def test_boundaries(self, score: float, expected: RiskLevel) -> None:
        assert score_to_level(score) == expected


# ==================================================================
# DEFAULT_WEIGHTS
# ==================================================================


class TestDefaultWeights:
    def test_all_factor_types_present(self) -> None:
        for ft in RiskFactorType:
            assert ft in DEFAULT_WEIGHTS

    def test_weights_sum_to_one(self) -> None:
        total = sum(DEFAULT_WEIGHTS.values())
        assert total == pytest.approx(1.0)

    def test_all_positive(self) -> None:
        assert all(w > 0 for w in DEFAULT_WEIGHTS.values())


# ==================================================================
# RiskFactors registry
# ==================================================================


class TestRiskFactors:
    def test_default_construction(self) -> None:
        rf = RiskFactors()
        assert len(rf.factors) == len(RiskFactorType)

    def test_custom_weights(self) -> None:
        custom = {ft: 1.0 / len(RiskFactorType) for ft in RiskFactorType}
        rf = RiskFactors(weights=custom)
        for f in rf.factors:
            assert f.weight == pytest.approx(1.0 / len(RiskFactorType))

    def test_get_factor_by_name(self) -> None:
        rf = RiskFactors()
        f = rf.get_factor("complexity")
        assert f is not None
        assert f.factor_type == RiskFactorType.COMPLEXITY

    def test_get_factor_by_type(self) -> None:
        rf = RiskFactors()
        f = rf.get_factor(RiskFactorType.CHURN)
        assert f is not None
        assert f.name == "churn"

    def test_get_factor_missing(self) -> None:
        rf = RiskFactors()
        assert rf.get_factor("nonexistent") is None

    def test_set_value(self) -> None:
        rf = RiskFactors()
        rf.set_value("complexity", 75.0)
        f = rf.get_factor("complexity")
        assert f is not None
        assert f.value == 75.0

    def test_set_value_clamped_high(self) -> None:
        rf = RiskFactors()
        rf.set_value("churn", 200.0)
        f = rf.get_factor("churn")
        assert f is not None
        assert f.value == 100.0

    def test_set_value_clamped_low(self) -> None:
        rf = RiskFactors()
        rf.set_value("churn", -10.0)
        f = rf.get_factor("churn")
        assert f is not None
        assert f.value == 0.0

    def test_set_value_missing_factor(self) -> None:
        rf = RiskFactors()
        rf.set_value("nonexistent", 50.0)  # should not raise

    def test_total_score_all_zero(self) -> None:
        rf = RiskFactors()
        assert rf.total_score() == 0.0

    def test_total_score(self) -> None:
        rf = RiskFactors()
        rf.set_value("complexity", 100.0)
        expected = DEFAULT_WEIGHTS[RiskFactorType.COMPLEXITY] * 100.0
        assert rf.total_score() == pytest.approx(expected)

    def test_total_score_all_max(self) -> None:
        rf = RiskFactors()
        for f in rf.factors:
            rf.set_value(f.name, 100.0)
        assert rf.total_score() == pytest.approx(100.0)
