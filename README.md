# Change Impact Analyzer (CIA)

[![CI](https://github.com/Eng-Elias/change_impact_analyzer/actions/workflows/ci.yml/badge.svg)](https://github.com/Eng-Elias/change_impact_analyzer/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/change-impact-analyzer.svg)](https://pypi.org/project/change-impact-analyzer/)
[![codecov](https://codecov.io/gh/Eng-Elias/change_impact_analyzer/branch/main/graph/badge.svg)](https://codecov.io/gh/Eng-Elias/change_impact_analyzer)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

**Predict the impact of code changes before you commit** — CIA statically analyses Python projects, builds dependency and call graphs, and scores the risk of every change so regressions are caught early.

---

## Installation

```bash
pip install change-impact-analyzer
```

For development:

```bash
git clone https://github.com/Eng-Elias/change_impact_analyzer.git
cd change_impact_analyzer
pip install -e ".[dev]"
```

## Quick Start

```bash
# 1. Initialise a configuration file (optional)
cia init

# 2. Stage some changes, then analyse them
git add -p
cia analyze --format markdown --explain

# 3. Install the pre-commit hook for automatic checks
cia install-hook --block-on high

# 4. View affected tests only
cia analyze --test-only

# 5. Generate all report formats at once
cia analyze --format all --output report
```

## Key Features

| Feature | Description |
|---|---|
| **Static Analysis** | Parses Python source with `astroid` to extract functions, classes, methods, and imports. |
| **Dependency Graph** | Builds module-level import graphs with NetworkX for transitive impact tracking. |
| **Call Graph** | Constructs function/method call graphs for fine-grained ripple-effect analysis. |
| **Change Detection** | Analyses Git diffs (staged, unstaged, or commit ranges) to locate modified symbols. |
| **Impact Analysis** | Traverses both graphs to identify all directly and transitively affected components. |
| **Risk Scoring** | Multi-factor weighted scoring engine (complexity, churn, dependents, coverage, size, critical path). |
| **Test Prediction** | Predicts which tests are affected and suggests missing coverage. |
| **Report Formats** | JSON (machine-readable), Markdown (PR comments), and interactive HTML with D3.js graph. |
| **Git Hook** | Optional pre-commit hook that blocks commits exceeding a risk threshold. |
| **Configuration** | `.ciarc` files (TOML/JSON/YAML), `CIA_*` environment variables, and CLI overrides. |

## HTML Report Preview

The HTML report includes an executive summary, a risk heatmap, collapsible dependency chains, and an interactive D3.js dependency graph:

```
┌─────────────────────────────────────────────────┐
│  Change Impact Analysis Report                  │
│                                                 │
│  Risk: ██████████░░░░░░░░░░  48 / 100  MEDIUM  │
│                                                 │
│  Files changed    : 3                           │
│  Symbols affected : 12                          │
│  Modules affected : 5                           │
│  Affected tests   : 4                           │
│                                                 │
│  [Risk Breakdown] [Dependency Graph] [Tests]    │
└─────────────────────────────────────────────────┘
```

> Generate one yourself: `cia analyze --format html --output report.html`

## Usage Examples

### Analyse staged changes (default: JSON output)

```bash
cia analyze
```

### Analyse unstaged changes with Markdown output

```bash
cia analyze --unstaged --format markdown
```

### Analyse a commit range with a risk threshold

```bash
cia analyze --commit-range HEAD~5..HEAD --threshold 60
```

If the overall risk score exceeds the threshold the command exits with code **1**.

### Show only affected tests

```bash
cia analyze --test-only
```

### Detailed risk explanation

```bash
cia analyze --explain
```

### Predict affected tests and suggest missing coverage

```bash
cia test --affected-only
cia test --suggest
```

### Configuration management

```bash
# Create a default .ciarc file
cia init

# View effective configuration
cia config

# Set a value
cia config --set analysis.format=markdown

# Get a single value
cia config --get threshold

# Open in $EDITOR
cia config --edit
```

### Git hook management

```bash
# Install locally (default)
cia install-hook --block-on high

# Install globally (Git template directory)
cia install-hook --global --block-on medium

# Force-overwrite an existing hook
cia install-hook --force

# Remove the hook
cia uninstall-hook
```

### Version information

```bash
cia version
```

## Configuration Guide

CIA resolves configuration in this order (last wins):

1. **Built-in defaults** — sensible out-of-the-box values.
2. **`.ciarc` file** — project-level config in TOML (default), JSON, or YAML.
3. **Environment variables** — any `CIA_*` variable (e.g. `CIA_FORMAT=html`).
4. **CLI arguments** — always take precedence.

Run `cia init` to create a starter `.ciarc` file:

```toml
# .ciarc
[analysis]
format = "json"
threshold = 75
explain = false
unstaged = false
test_only = false

[hook]
block_on = "high"
```

### Environment variable examples

```bash
export CIA_FORMAT=markdown
export CIA_THRESHOLD=80
export CIA_EXPLAIN=true
```

## Integration Examples

### GitHub Actions — analyse every PR

Add the included workflow (`.github/workflows/cia.yml`) or create your own:

```yaml
# .github/workflows/cia-check.yml
name: CIA Check
on: [pull_request]
jobs:
  analyze:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install change-impact-analyzer
      - run: cia analyze --format markdown --commit-range origin/main..HEAD --threshold 75
```

### pre-commit hook

Add CIA to your `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: local
    hooks:
      - id: cia
        name: Change Impact Analysis
        entry: cia analyze --format json
        language: system
        types: [python]
        pass_filenames: false
        always_run: true
```

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Risk score exceeds the configured threshold |
| `2` | Runtime or configuration error |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, code style, and PR guidelines.

## License

This project is licensed under the **MIT License** — see [LICENSE](LICENSE) for details.

## Citation

If you use Change Impact Analyzer in your research, please cite:

```bibtex
@article{cia2025,
  title   = {Change Impact Analyzer: Predicting the Ripple Effects of Code
             Changes with Static Analysis and Graph Traversal},
  author  = {{Change Impact Analyzer Contributors}},
  journal = {Journal of Open Source Software},
  year    = {2025},
  doi     = {10.21105/joss.XXXXX},
  url     = {https://github.com/Eng-Elias/change_impact_analyzer}
}
```
