"""Sample main module.

Demonstrates a simple application entry point that depends on
:mod:`utils` and :mod:`models`.  Changing any of these modules
will show up in CIA's impact analysis.
"""

from examples.sample_project import models, utils


def main() -> None:
    """Entry point for the sample project."""
    data = [1, 2, 3, 4, 5]
    if not utils.validate_input(data):
        print("Invalid input")
        return

    result = utils.process_data(data)
    report = models.Report(title="Sample Run", stats=result)
    print(report.summary())


def run_pipeline(raw: list) -> models.Report:
    """Higher-level pipeline that CIA can trace through the call graph."""
    clean = [x for x in raw if utils.validate_input([x])]
    stats = utils.process_data(clean)
    return models.Report(title="Pipeline", stats=stats)


if __name__ == "__main__":
    main()
