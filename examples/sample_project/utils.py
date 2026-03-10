"""Sample utility module."""


def process_data(data: list) -> dict:
    """Process a list of numbers and return statistics."""
    total = sum(data)
    average = total / len(data) if data else 0
    return {
        "total": total,
        "average": average,
        "count": len(data),
        "max": max(data) if data else None,
        "min": min(data) if data else None,
    }


def validate_input(data: list) -> bool:
    """Validate that input data is a non-empty list of numbers."""
    if not isinstance(data, list):
        return False
    if not data:
        return False
    return all(isinstance(x, (int, float)) for x in data)
