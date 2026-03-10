# Change Impact Analyzer (CIA)

[![CI](https://github.com/Eng-Elias/change_impact_analyzer/actions/workflows/ci.yml/badge.svg)](https://github.com/Eng-Elias/change_impact_analyzer/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

A Git-based tool that predicts the potential impact of code changes on other parts of the codebase before they are committed.

## Features

- **Static Analysis** — Parses Python source code to extract functions, classes, methods, and their dependencies.
- **Dependency Graph** — Builds module-level import dependency graphs using NetworkX.
- **Call Graph** — Constructs function/method-level call graphs for fine-grained impact tracking.
- **Change Detection** — Analyzes Git diffs to identify which symbols have been modified.
- **Impact Analysis** — Traverses graphs to find directly and transitively affected components.
- **Risk Scoring** — Computes a weighted multi-factor risk score for each change.
- **Multiple Report Formats** — Generates reports in JSON, Markdown, and HTML.
- **Git Hook Integration** — Optional pre-commit hook for automatic analysis.

## Installation

```bash
pip install change-impact-analyzer
```

### Development Installation

```bash
git clone https://github.com/Eng-Elias/change_impact_analyzer.git
cd change_impact_analyzer
pip install -e ".[dev]"
```

## Quick Start

### Analyze staged changes

```bash
cia analyze
```

### Analyze a specific directory

```bash
cia analyze /path/to/project --format markdown --output report.md
```

### Build a dependency graph

```bash
cia graph /path/to/project
```

### Install Git hook

```bash
cia hook --install
```

## Usage

```
Usage: cia [OPTIONS] COMMAND [ARGS]...

  Change Impact Analyzer - Predict the impact of code changes.

Options:
  --version      Show the version and exit.
  -v, --verbose  Enable verbose output.
  --help         Show this message and exit.

Commands:
  analyze  Analyze the impact of staged changes in a Git repository.
  graph    Build and display the dependency graph for a project.
  hook     Manage Git hooks for automatic impact analysis.
```

## How It Works

1. **Parse** — Source files are parsed with `astroid` to extract symbols and their relationships.
2. **Build Graphs** — Module-level dependency graphs and function-level call graphs are constructed.
3. **Detect Changes** — Git diffs identify which files and symbols have changed.
4. **Analyze Impact** — Graph traversal determines all directly and transitively affected components.
5. **Score Risk** — A multi-factor scoring engine quantifies the risk of each change.
6. **Report** — Results are presented in the requested format (JSON, Markdown, or HTML).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

## Citation

If you use CIA in your research, please cite:

```bibtex
@article{cia2024,
  title = {Change Impact Analyzer: A Git-based Tool for Predicting Code Change Impact},
  journal = {Journal of Open Source Software},
  year = {2024},
}
```
