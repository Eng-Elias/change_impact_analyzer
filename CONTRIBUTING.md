# Contributing to Change Impact Analyzer

Thank you for your interest in contributing! This guide covers everything you
need to get started.

## Table of Contents

- [Development Environment](#development-environment)
- [Code Style](#code-style)
- [Testing](#testing)
- [Pull Request Process](#pull-request-process)
- [Reporting Issues](#reporting-issues)
- [Code of Conduct](#code-of-conduct)

---

## Development Environment

### Prerequisites

- Python 3.11 or later
- Git

### Setup

1. **Fork and clone** the repository:

   ```bash
   git clone https://github.com/<your-username>/change_impact_analyzer.git
   cd change_impact_analyzer
   ```

2. **Install in editable mode** with dev dependencies:

   ```bash
   python -m pip install --upgrade pip
   pip install -e ".[dev]"
   ```

3. **Install pre-commit hooks** (runs Black, Ruff, mypy, and a quick test on
   every commit):

   ```bash
   pre-commit install
   ```

4. **Verify everything works**:

   ```bash
   pytest                          # run the full test suite
   ruff check .                    # lint
   black --check src/ tests/       # format check
   mypy src/cia/                   # type check
   ```

   Or run all checks at once via tox:

   ```bash
   pip install tox
   tox -e all
   ```

### Project Layout

```
src/cia/
├── analyzer/       # Change detection, impact analysis, test prediction
├── config.py       # Configuration management (.ciarc, env vars)
├── cli.py          # Click-based CLI
├── git/            # Git integration and hook management
├── graph/          # Dependency and call graphs (NetworkX)
├── parser/         # AST parsing (astroid)
├── report/         # JSON, Markdown, HTML reporters
└── risk/           # Risk scoring engine
tests/
├── test_analyzer/  # Analyzer tests
├── test_ci/        # CI/CD config validation tests
├── test_git/       # Git integration tests
├── test_graph/     # Graph tests
├── test_parser/    # Parser tests
├── test_report/    # Reporter tests
├── test_risk/      # Risk scorer tests
├── test_cli.py     # CLI command tests
└── test_config.py  # Configuration module tests
```

---

## Code Style

| Tool | Purpose | Config |
|------|---------|--------|
| **Black** | Code formatting | `pyproject.toml` — line length 88, target Python 3.11 |
| **Ruff** | Fast linting (replaces flake8 + isort) | `pyproject.toml` — E, F, W, I, N, UP, B, SIM rules |
| **mypy** | Static type checking | `pyproject.toml` — strict mode, `disallow_untyped_defs` |

### Key conventions

- **Type annotations** are required on all function signatures.
- **Docstrings** are required on all public classes and functions.
- **Imports** must be sorted by `ruff` / `isort` rules (`I` rule set).
- Keep line length at or below **88 characters**.
- Use `from __future__ import annotations` at the top of every module.

To auto-format your code:

```bash
black src/ tests/
ruff check --fix src/ tests/
```

---

## Testing

### Running tests

```bash
# Full suite with coverage
pytest

# Specific test file
pytest tests/test_cli.py -v

# Specific test class or method
pytest tests/test_cli.py::TestAnalyzeCommand::test_default_json -v

# With coverage report
pytest --cov=src/cia --cov-report=html
```

### Writing tests

- Place tests in the appropriate `tests/test_*` subdirectory.
- Mirror the source structure (e.g. `src/cia/risk/` → `tests/test_risk/`).
- Use `pytest` fixtures; shared fixtures go in `conftest.py`.
- Use `tmp_path` for temporary files and `CliRunner` for CLI tests.
- **Every new feature or bug fix must include tests.**
- Target **70%+ coverage** for new modules (the project maintains >90% overall).

### Test matrix

The CI pipeline tests on:

- **Python**: 3.11, 3.12
- **OS**: Ubuntu, macOS, Windows

---

## Pull Request Process

1. **Create a feature branch** from `main`:

   ```bash
   git checkout -b feature/short-description
   ```

2. **Make focused changes** — one logical change per PR.

3. **Ensure all checks pass** locally:

   ```bash
   pytest
   ruff check .
   black --check src/ tests/
   mypy src/cia/
   ```

4. **Write a clear commit message** following
   [Conventional Commits](https://www.conventionalcommits.org/):

   ```
   feat: add --dry-run flag to install-hook command
   fix: handle empty diff in change detector
   docs: update configuration guide
   test: add coverage for config --edit error path
   ```

5. **Push and open a PR** against `main`.

6. **Fill in the PR description**:
   - What does this PR do?
   - How was it tested?
   - Related issue number (e.g. `Closes #42`).

7. **Address review feedback** — the CIA self-analysis bot will post an
   impact report on your PR automatically.

### What we look for in review

- Tests for new/changed behaviour.
- No decrease in coverage.
- Documentation updated if user-facing behaviour changes.
- Clean commit history (squash if needed).

---

## Reporting Issues

### Bug reports

Please include:

- **Python version** (`python --version`)
- **OS and version** (e.g. Ubuntu 22.04, Windows 11, macOS 14)
- **CIA version** (`cia version`)
- **Steps to reproduce** — minimal example
- **Expected vs actual behaviour**
- **Full error output** (traceback, if any)

### Feature requests

- Describe the **problem** you are trying to solve.
- Propose a **solution** if you have one.
- Note any **alternatives** you have considered.

---

## Code of Conduct

Please read and follow our [Code of Conduct](CODE_OF_CONDUCT.md). We are
committed to providing a welcoming and inclusive experience for everyone.
