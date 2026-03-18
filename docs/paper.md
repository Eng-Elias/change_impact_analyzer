---
title: 'Change Impact Analyzer: Predicting the Ripple Effects of Code Changes with Static Analysis and Graph Traversal'
tags:
  - Python
  - static analysis
  - software engineering
  - dependency analysis
  - change impact analysis
  - git
authors:
  - name: Change Impact Analyzer Contributors
    orcid: 0000-0000-0000-0000
    affiliation: 1
affiliations:
  - name: Independent
    index: 1
date: 2026
bibliography: paper.bib
---

# Summary

Change Impact Analyzer (CIA) is an open-source Python tool that predicts the
potential impact of code changes on other parts of a codebase before they are
committed. CIA combines static analysis with Git integration to build
module-level dependency graphs and function-level call graphs, then traverses
those graphs to identify every component — module, class, or function — that
may be affected by a proposed change. A weighted multi-factor risk scoring
engine quantifies the severity of each change across six dimensions:
complexity, file churn, downstream dependents, test coverage, change size, and
critical-path position. Results are presented as JSON, Markdown, or interactive
HTML reports. CIA integrates into the developer workflow through a command-line
interface, Git pre-commit hooks, and GitHub Actions workflows, providing
continuous feedback with minimal disruption. The tool targets Python 3.11+
projects and is distributed via PyPI under the MIT licence.

# Statement of Need

Modern software systems consist of deeply interconnected modules, yet
developers routinely modify code without a complete view of downstream
dependencies. Studies by Lehnert [@lehnert2011taxonomy] and Li et al.
[@li2013survey] show that incomplete understanding of change propagation is a
leading cause of software regressions. Existing solutions either require
heavyweight IDE plugins, operate only at the file level, or lack integration
with version control workflows.

CIA fills this gap by providing a **lightweight, Git-native tool** that:

- Works at both module and function granularity.
- Runs automatically on every commit via pre-commit hooks.
- Integrates into CI/CD pipelines (GitHub Actions) to gate pull requests.
- Produces human-readable and machine-readable reports.
- Requires no runtime instrumentation or test execution.

The target audience is Python developers, team leads, and DevOps engineers who
want early, automated feedback on the risk profile of pending changes.

# Key Features

- **Dual-graph analysis** — module-level dependency graph and function-level
  call graph built from AST analysis with `astroid` and `networkx`.
- **Git-aware change detection** — analyses staged, unstaged, or commit-range
  diffs to map changed lines to symbols.
- **Multi-factor risk scoring** — six weighted risk factors with configurable
  weights and human-readable explanations.
- **Test impact prediction** — identifies affected tests and suggests missing
  coverage.
- **Three report formats** — JSON (CI integration), Markdown (PR comments),
  and interactive HTML (D3.js graph visualisation).
- **Git hook integration** — optional pre-commit hook that blocks commits
  exceeding a configurable risk threshold.
- **Configuration cascade** — `.ciarc` files (TOML/JSON/YAML), `CIA_*`
  environment variables, and CLI argument overrides.

# Technical Implementation

CIA's architecture consists of five layered components:

```
┌─────────────┐   ┌──────────────┐   ┌────────────┐
│  CLI / Hook  │──▶│  Analyzer    │──▶│  Reporter   │
└──────┬──────┘   │  Engine      │   │ JSON/MD/HTML│
       │          └──────┬───────┘   └────────────┘
       ▼                 ▼
┌─────────────┐   ┌──────────────┐
│  Git Layer  │   │  Graph Layer │
│  (GitPython)│   │  (NetworkX)  │
└─────────────┘   └──────────────┘
```

1. **Parser** (`cia.parser`) — uses `astroid` to walk the AST of every Python
   file, extracting `Function`, `Class`, `Import`, and `Variable` symbols into
   a `ParsedModule` data structure.
2. **Graph Layer** (`cia.graph`) — constructs a `DependencyGraph`
   (module-to-module edges from imports) and a `CallGraph` (function-to-function
   edges from call sites).
3. **Analyzer Engine** (`cia.analyzer`) — the `ChangeDetector` maps Git diff
   hunks to symbols; the `ImpactAnalyzer` performs breadth-first traversal on
   both graphs; the `TestAnalyzer` predicts affected tests.
4. **Risk Scorer** (`cia.risk`) — computes a composite score from six factors,
   each with an independent weight, and produces natural-language explanations
   and actionable suggestions.
5. **Reporter** (`cia.report`) — renders `ImpactReport` objects into JSON
   (with a stable schema), GitHub-flavoured Markdown, or a self-contained HTML
   page with D3.js force-directed graph.

# Example Usage

```bash
$ cd my-python-project
$ git add -p                          # stage changes
$ cia analyze --format markdown --explain

# Change Impact Analysis Report
# Risk: 48/100 (MEDIUM)
#
# Complexity of changed code: 32/100
# Number of downstream dependents: 65/100
# ...
#
# Suggestions:
#   - Consider adding tests for uncovered modules
#   - Break large change into smaller commits
```

Programmatic JSON output for CI pipelines:

```bash
$ cia analyze --format json --threshold 75
$ echo $?    # 0 = OK, 1 = threshold exceeded
```

# Impact

CIA improves the development workflow in three ways:

1. **Early feedback** — developers see risk assessments before pushing,
   reducing the cost of regressions caught later in the pipeline.
2. **Automated gating** — CI workflows and pre-commit hooks enforce
   team-agreed risk thresholds without manual review overhead.
3. **Test guidance** — test-impact prediction focuses testing effort on
   the modules most likely to be affected, saving CI time.

# Acknowledgements

CIA builds on several excellent open-source projects: `astroid` for AST
analysis, `networkx` for graph algorithms, `GitPython` for repository
interaction, `click` and `rich` for the CLI, and `Jinja2` and `D3.js` for
report rendering.

# References
