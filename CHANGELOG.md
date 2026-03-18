# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-03-18

### Added

- **Parser** — Python source code parser using `astroid`, extracting functions,
  classes, methods, imports, and variables into `ParsedModule` data structures.
- **Dependency Graph** — Module-level import dependency graph built with
  `networkx`, supporting transitive dependency and dependent queries.
- **Call Graph** — Function/method-level call graph for fine-grained impact
  tracking with transitive caller/callee traversal.
- **Change Detection** — Git diff-based change detector supporting staged,
  unstaged, and commit-range diffs with symbol-level mapping.
- **Impact Analyzer** — Orchestrator combining graph traversal, risk scoring,
  test-impact prediction, and recommendation generation into `ImpactReport`.
- **Test Analyzer** — Predicts affected tests from code changes and suggests
  missing test coverage.
- **Risk Scoring** — Weighted multi-factor risk engine scoring complexity,
  churn, dependents, test coverage, change size, and critical-path position
  with natural-language explanations and actionable suggestions.
- **JSON Reporter** — Machine-readable JSON output with stable `schema_version`.
- **Markdown Reporter** — GitHub-flavoured Markdown with risk badges, tables,
  and numbered action items.
- **HTML Reporter** — Interactive report with D3.js force-directed dependency
  graph, risk heatmap, and collapsible sections.
- **CLI** — Click-based command-line interface with commands: `analyze`, `test`,
  `install-hook`, `uninstall-hook`, `config`, `init`, `version`, `graph`.
- **Configuration** — `.ciarc` file support (TOML/JSON/YAML), `CIA_*`
  environment variables, and CLI argument overrides with cascading resolution.
- **Git Hook** — Pre-commit hook with configurable risk threshold blocking
  (`--block-on`), local and global installation, and `--force` overwrite.
- **CI/CD** — GitHub Actions workflows for CI (lint, typecheck, matrix test,
  dogfood), release (test → build → PyPI → GitHub Release), and self-analysis
  on pull requests with sticky PR comment.
- **Pre-commit Config** — Hooks for Black, Ruff, mypy, pytest, and CIA
  self-analysis.
- **tox** — Multi-environment configuration for testing, linting, type
  checking, formatting, and docs building.
- **Documentation** — README, CONTRIBUTING, CODE_OF_CONDUCT, CHANGELOG, API
  reference, JOSS paper, and example project.

[Unreleased]: https://github.com/Eng-Elias/change_impact_analyzer/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Eng-Elias/change_impact_analyzer/releases/tag/v0.1.0
