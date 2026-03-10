"""Sample main module."""

from examples.sample_project import utils


def main():
    """Entry point for the sample project."""
    result = utils.process_data([1, 2, 3, 4, 5])
    print(f"Result: {result}")


if __name__ == "__main__":
    main()
