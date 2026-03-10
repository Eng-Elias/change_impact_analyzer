# Contributing to Change Impact Analyzer

Thank you for your interest in contributing! This document provides guidelines for contributing to CIA.

## Getting Started

1. Fork the repository.
2. Clone your fork:
   ```bash
   git clone https://github.com/<your-username>/change_impact_analyzer.git
   cd change_impact_analyzer
   ```
3. Install development dependencies:
   ```bash
   pip install -e ".[dev]"
   pre-commit install
   ```

## Development Workflow

1. Create a feature branch from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```
2. Make your changes.
3. Ensure all tests pass:
   ```bash
   pytest
   ```
4. Ensure code quality:
   ```bash
   ruff check src/ tests/
   black --check src/ tests/
   mypy src/cia/
   ```
5. Commit your changes with a clear message.
6. Push to your fork and open a Pull Request.

## Code Style

- We use **Black** for formatting (line length 88).
- We use **Ruff** for linting.
- We use **mypy** for static type checking.
- All public functions and classes must have docstrings.
- Type annotations are required for all function signatures.

## Testing

- Write tests for all new features and bug fixes.
- Place tests in the appropriate `tests/test_*` subdirectory.
- Use `pytest` fixtures from `tests/conftest.py` where applicable.
- Aim for high test coverage.

## Pull Request Guidelines

- Keep PRs focused on a single concern.
- Include tests for new functionality.
- Update documentation if applicable.
- Reference any related issues.

## Reporting Issues

- Use GitHub Issues to report bugs or request features.
- Include steps to reproduce for bug reports.
- Include Python version and OS information.

## Code of Conduct

Please read and follow our [Code of Conduct](CODE_OF_CONDUCT.md).
