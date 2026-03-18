"""Tests for the sample utils module."""

from examples.sample_project.utils import process_data, validate_input


def test_process_data_basic() -> None:
    result = process_data([1, 2, 3])
    assert result["total"] == 6
    assert result["average"] == 2.0
    assert result["count"] == 3
    assert result["max"] == 3
    assert result["min"] == 1


def test_process_data_empty() -> None:
    result = process_data([])
    assert result["total"] == 0
    assert result["average"] == 0
    assert result["count"] == 0


def test_validate_input_valid() -> None:
    assert validate_input([1, 2, 3]) is True


def test_validate_input_empty() -> None:
    assert validate_input([]) is False


def test_validate_input_not_list() -> None:
    assert validate_input("hello") is False  # type: ignore[arg-type]


def test_validate_input_mixed_types() -> None:
    assert validate_input([1, "two", 3]) is False  # type: ignore[list-item]
