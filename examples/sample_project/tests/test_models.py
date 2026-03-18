"""Tests for the sample models module."""

from examples.sample_project.models import Report


def test_report_summary() -> None:
    r = Report(title="Test", stats={"total": 10, "count": 3})
    assert r.summary() == "Test: 3 items, total=10"


def test_report_summary_empty_stats() -> None:
    r = Report(title="Empty")
    assert "0 items" in r.summary()


def test_report_is_empty_true() -> None:
    r = Report(title="Empty")
    assert r.is_empty() is True


def test_report_is_empty_false() -> None:
    r = Report(title="Full", stats={"count": 5})
    assert r.is_empty() is False
