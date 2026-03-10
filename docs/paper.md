---
title: 'Change Impact Analyzer: A Git-based Tool for Predicting Code Change Impact'
tags:
  - Python
  - static analysis
  - software engineering
  - dependency analysis
  - git
authors:
  - name: Change Impact Analyzer Contributors
date: 2024
bibliography: paper.bib
---

# Summary

Change Impact Analyzer (CIA) is a Python-based tool that predicts the potential
impact of code changes on other parts of a codebase before they are committed.
By combining static analysis of source code with Git integration, CIA builds
dependency and call graphs to identify which modules, classes, and functions may
be affected by a proposed change.

# Statement of Need

Understanding the ripple effects of code changes is critical in software
development. Developers often modify code without a complete picture of which
other components depend on the changed code, leading to unexpected regressions.
CIA addresses this by providing automated impact analysis that integrates
directly into the developer workflow via Git hooks and a command-line interface.

# Methodology

CIA operates in several stages:

1. **Parsing**: Source code is parsed using `astroid` to extract symbols
   (functions, classes, methods) and their dependencies.
2. **Graph Construction**: Module-level dependency graphs and function-level
   call graphs are built using `networkx`.
3. **Change Detection**: Git diffs are analyzed to identify which symbols have
   been modified.
4. **Impact Analysis**: Graph traversal identifies directly and transitively
   affected components.
5. **Risk Scoring**: A weighted multi-factor risk score quantifies the
   potential impact of each change.

# References
