# CIA MCP Server — Design Document

> Design proposal for exposing the **Change Impact Analyzer** as a
> [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server
> so that any AI coding assistant (Windsurf/Cascade, Cursor, Claude Code,
> VS Code Copilot, Continue, Cline, …) can natively query impact analysis,
> risk scores, dependency graphs and test predictions.

---

## Table of Contents

1. [Goals & Non-Goals](#1-goals--non-goals)
2. [Architecture Overview](#2-architecture-overview)
3. [Transport & Configuration](#3-transport--configuration)
4. [Tools](#4-tools)
5. [Resources](#5-resources)
6. [AI Skills](#6-ai-skills)
7. [AI Agents](#7-ai-agents)
8. [Slash Commands](#8-slash-commands)
9. [Data Models](#9-data-models)
10. [Implementation Plan](#10-implementation-plan)
11. [Client Integration Guide](#11-client-integration-guide)
12. [Security Considerations](#12-security-considerations)
13. [Open Questions](#13-open-questions)

---

## 1. Goals & Non-Goals

### Goals

- **Universal AI assistant integration** — any MCP-compatible client can
  consume CIA capabilities without custom plugins.
- **Structured output** — return JSON objects the LLM can reason over,
  not human-formatted text.
- **Composable primitives** — tools are fine-grained enough for the AI to
  chain them (e.g. detect changes → score risk → suggest tests → generate
  code).
- **Zero-config startup** — `cia-mcp` discovers the nearest `.ciarc` and
  Git repo automatically.
- **Safe by default** — read-only tools are the norm; write tools (hook
  install, config set) require explicit confirmation.

### Non-Goals

- Replacing the CLI (the CLI remains the primary human interface).
- Building a web UI or REST API.
- Supporting non-Python codebases in v1 (mirrors current CIA scope).

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────┐
│  AI Coding Assistant (Windsurf / Cursor / …)    │
│                                                 │
│   ┌─────────┐  ┌──────────┐  ┌──────────────┐  │
│   │  Tools  │  │Resources │  │   Prompts    │  │
│   └────┬────┘  └────┬─────┘  └──────┬───────┘  │
│        │            │               │           │
│        └────────────┼───────────────┘           │
│                     │  MCP (stdio / SSE)        │
└─────────────────────┼───────────────────────────┘
                      │
┌─────────────────────┼───────────────────────────┐
│          cia-mcp server process                 │
│                     │                           │
│  ┌─────────────────────────────────────┐        │
│  │         MCP Protocol Layer          │        │
│  │  (mcp-python-sdk / FastMCP)         │        │
│  └──────────────┬──────────────────────┘        │
│                 │                               │
│  ┌──────────────┴──────────────────────┐        │
│  │      CIA Core Library (src/cia)     │        │
│  │                                     │        │
│  │  ChangeDetector · RiskScorer        │        │
│  │  DependencyGraph · TestAnalyzer     │        │
│  │  ImpactAnalyzer · Config · Hooks    │        │
│  └──────────────┬──────────────────────┘        │
│                 │                               │
│          Git repo (working tree)                │
└─────────────────────────────────────────────────┘
```

The server is a **thin adapter** — it translates MCP requests into calls
to the existing CIA library classes and returns structured JSON.

---

## 3. Transport & Configuration

### Transport Options

| Transport | Use Case | Notes |
|-----------|----------|-------|
| **stdio** | Local IDE assistants (default) | Windsurf, Cursor, Claude Code |
| **SSE** | Remote / browser-based clients | HTTP server on configurable port |
| **Streamable HTTP** | Future MCP spec evolution | Planned for v2 |

### Server Entry Point

```bash
# stdio (default — used by most IDE integrations)
cia-mcp serve

# SSE transport
cia-mcp serve --transport sse --port 3001

# With explicit repo path
cia-mcp serve --repo /path/to/project
```

### Client Configuration Example

```jsonc
// .windsurf/mcp_config.json (or equivalent for other clients)
{
  "mcpServers": {
    "cia": {
      "command": "cia-mcp",
      "args": ["serve"],
      "cwd": "${workspaceFolder}",
      "env": {}
    }
  }
}
```

---

## 4. Tools

Tools are **actions** the AI can invoke. Each returns structured JSON.

### 4.1 Change Detection & Impact Analysis

#### `cia_analyze`

Analyze the impact of current changes and return a full risk report.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `path` | string | No | `.` | Repository path |
| `staged` | boolean | No | `true` | Analyze staged changes (false = unstaged) |
| `commit_range` | string | No | `null` | Git range e.g. `HEAD~3..HEAD` |
| `include_explanation` | boolean | No | `true` | Include human-readable risk explanations |

**Returns:**

```json
{
  "risk": {
    "overall_score": 58.1,
    "level": "high",
    "factor_scores": {
      "complexity": 15.0,
      "churn": 0.0,
      "dependents": 100.0,
      "test_coverage": 40.0,
      "change_size": 12.0,
      "critical_path": 8.9
    },
    "explanations": [
      "100/100 dependents — 11 modules depend on changed files",
      "40/100 test_coverage — partial coverage detected"
    ],
    "suggestions": [
      "Add tests for flag_definition before committing",
      "Consider splitting this change into smaller commits"
    ]
  },
  "changes": {
    "files_changed": 1,
    "total_additions": 3,
    "total_deletions": 2,
    "affected_modules": ["flag_definition", "engine", "client", "..."]
  }
}
```

#### `cia_detect_changes`

Lightweight change detection without full risk scoring.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `path` | string | No | `.` | Repository path |
| `staged` | boolean | No | `true` | Staged vs unstaged |
| `commit_range` | string | No | `null` | Git range |

**Returns:** List of changed files with added/deleted line counts and affected symbols.

---

### 4.2 Dependency Graph

#### `cia_graph`

Return the project's full dependency graph.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `path` | string | No | `.` | Repository path |
| `format` | string | No | `json` | `json`, `dot`, `text` |

**Returns (JSON format):**

```json
{
  "modules": ["engine", "flag_definition", "client", "..."],
  "edges": [
    {"from": "engine", "to": "flag_definition"},
    {"from": "client", "to": "engine"}
  ],
  "module_count": 9,
  "edge_count": 13,
  "cycles": []
}
```

#### `cia_get_dependents`

Get all modules that depend on a given module (direct + transitive).

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `module` | string | Yes | — | Module name (e.g. `flag_definition`) |
| `transitive` | boolean | No | `true` | Include transitive dependents |

**Returns:**

```json
{
  "module": "flag_definition",
  "direct_dependents": ["engine", "client", "flag_store"],
  "transitive_dependents": ["engine", "client", "flag_store", "middleware", "changelog"]
}
```

#### `cia_get_dependencies`

Get all modules that a given module imports (direct + transitive).

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `module` | string | Yes | — | Module name |
| `transitive` | boolean | No | `true` | Include transitive dependencies |

---

### 4.3 Test Intelligence

#### `cia_predict_tests`

Predict which tests are affected by current changes.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `path` | string | No | `.` | Repository path |
| `staged` | boolean | No | `true` | Staged vs unstaged |
| `commit_range` | string | No | `null` | Git range |

**Returns:**

```json
{
  "affected_tests": ["tests/test_flags.py", "tests/test_evaluation.py"],
  "pytest_expression": "test_flags or test_evaluation",
  "pytest_args": ["-k", "test_flags or test_evaluation"]
}
```

#### `cia_suggest_tests`

Identify changed code lacking test coverage and suggest new tests.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `path` | string | No | `.` | Repository path |
| `staged` | boolean | No | `true` | Staged vs unstaged |

**Returns:**

```json
{
  "suggestions": [
    {
      "entity": "flag_store::FlagStore.batch_toggle",
      "reason": "New method with no test coverage",
      "suggested_file": "tests/test_flag_store.py"
    }
  ]
}
```

---

### 4.4 Risk Assessment

#### `cia_score_risk`

Score risk for a specific set of files or modules (without requiring a Git diff).

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `files` | string[] | Yes | — | List of file paths to evaluate |
| `path` | string | No | `.` | Repository path |

**Returns:** Same risk object as `cia_analyze`.

#### `cia_explain_risk`

Given a risk score, provide detailed human-readable explanation and actionable suggestions.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `risk_score` | object | Yes | — | Risk score object from `cia_analyze` |

---

### 4.5 Configuration & Setup

#### `cia_init`

Initialize CIA in a project directory.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `path` | string | No | `.` | Project root |

#### `cia_config_get`

Read a configuration value.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `key` | string | Yes | — | Config key (e.g. `format`, `threshold`) |
| `path` | string | No | `.` | Project root |

#### `cia_config_set`

Write a configuration value. *(Requires confirmation.)*

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `key` | string | Yes | — | Config key |
| `value` | string | Yes | — | New value |
| `path` | string | No | `.` | Project root |

#### `cia_install_hook`

Install the CIA pre-commit hook. *(Requires confirmation.)*

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `path` | string | No | `.` | Repository path |
| `block_on` | string | No | `none` | `none`, `low`, `medium`, `high` |
| `force` | boolean | No | `false` | Overwrite existing hook |

#### `cia_uninstall_hook`

Remove the CIA pre-commit hook. *(Requires confirmation.)*

---

## 5. Resources

Resources are **read-only data** the AI can inspect at any time.

| URI | Description | MIME |
|-----|-------------|------|
| `cia://config` | Current effective `.ciarc` configuration | `application/json` |
| `cia://graph` | Full dependency graph (JSON) | `application/json` |
| `cia://graph/modules` | List of all parsed modules | `application/json` |
| `cia://graph/module/{name}` | Single module's imports and dependents | `application/json` |
| `cia://risk/weights` | Current risk factor weights | `application/json` |
| `cia://risk/thresholds` | Score → level mapping (LOW/MED/HIGH/CRIT) | `application/json` |
| `cia://tests/mapping` | Test file → covered modules mapping | `application/json` |
| `cia://version` | CIA version and environment info | `application/json` |

### Dynamic Resources (Subscriptions)

| URI | Description |
|-----|-------------|
| `cia://changes/staged` | Auto-updates when staged changes change |
| `cia://changes/risk` | Live risk score for current staged changes |

---

## 6. AI Skills

Skills are **multi-step workflows powered by CIA**. The AI assistant
calls CIA's CLI or MCP tools to gather analysis data, then interprets
and presents the results. CIA does the heavy lifting (parsing, graph
building, risk scoring); the skill orchestrates and communicates.

### 6.1 Pre-Commit Risk Review

> **Trigger:** "Review my changes", "is it safe to commit?", `/cia-review`

The assistant runs three CIA commands and synthesises the results:

```
 cia analyze .              →  risk score, factor breakdown, suggestions
 cia test . --affected-only →  which tests to run
 cia test . --suggest       →  coverage gaps in changed code
```

**Output the assistant produces:**

```
📋 Pre-Commit Review

Risk: HIGH (62/100)
  - dependents 100/100 — 11 modules import from flag_definition
  - test_coverage 40/100 — partial coverage

Blast Radius: 1 file changed → 11 downstream modules affected

Tests to Run:
  pytest -k "test_flags or test_evaluation or test_sdk"

Coverage Gaps:
  - FlagStore.batch_toggle — new method, no tests → tests/test_flag_store.py

Verdict: ⛔ HIGH RISK — add tests for batch_toggle before committing.
```

**Decision rules the assistant follows:**
- Score ≥ 60 → recommend splitting or adding tests first
- Score 30–59 → recommend running affected tests before committing
- Score < 30 → safe to commit

---

### 6.2 Blast Radius Lookup

> **Trigger:** "What breaks if I change X?", `/cia-blast <module>`

```
 cia graph . --format json   →  full dependency graph
```

The assistant reads CIA's graph output to find all direct and transitive
dependents of the target module, groups them by distance, and highlights
which ones have tests.

**Example:**

```
Blast radius for `flag_definition`:

  Depth 1 (direct): engine, client, flag_store, changelog
  Depth 2: middleware, sdk_client, test_evaluation
  Depth 3+: test_sdk, test_audit

  Total: 11 downstream modules
  Risk: HIGH — this is the most connected module in the project.
  Tests to run: pytest -k "test_flags or test_evaluation or test_sdk"
```

---

### 6.3 Test Gap Finder

> **Trigger:** "What's untested?", "write tests for my changes", `/cia-suggest`

```
 cia test . --suggest   →  list of uncovered entities with reasons
```

The assistant reads CIA's suggestions, then reads the uncovered source
functions and writes pytest skeletons for them. CIA identifies *what*
is untested; the assistant writes the tests.

---

### 6.4 Architecture Health Check

> **Trigger:** "Audit my architecture", "find circular deps", `/cia-audit`

```
 cia graph . --format json   →  modules, edges, cycles
```

The assistant uses CIA's graph data to compute:
- **Circular dependencies** — `cia graph` reports cycles directly
- **God modules** — modules where CIA shows fan-in > 10
- **Orphan modules** — modules with 0 dependents and 0 dependencies
- **Max chain depth** — longest transitive path in the CIA graph

Outputs an A–F health grade with a table of findings.

---

### 6.5 Safe Refactor Guide

> **Trigger:** "Help me rename X safely", `/cia-refactor <symbol>`

```
 cia graph . --format json   →  who imports the target module
 cia test . --affected-only  →  tests to run after refactoring
 cia analyze .               →  risk score for the change
```

The assistant uses CIA's dependency data to list every file that imports
the symbol, builds a step-by-step refactoring checklist, and after the
user applies the change, runs the affected tests CIA identified.

---

### 6.6 PR Description Generator

> **Trigger:** "Summarize my changes for a PR", `/cia-pr-summary`

```
 cia analyze . --format json   →  risk report with changes and scores
 cia test . --suggest          →  coverage status
```

The assistant reads CIA's analysis output and writes a structured PR
description: what changed, risk level, blast radius, tests run, and
coverage status. All data comes from CIA's JSON output.

---

### 6.7 Live Risk Monitor

> **Trigger:** Runs in the background via CIA resource subscriptions.

The MCP server exposes `cia://changes/risk` as a dynamic resource.
When the assistant subscribes, it receives updated risk scores from CIA
whenever staged changes change. If the risk level transitions (e.g.
LOW → HIGH), the assistant proactively notifies the user with CIA's
risk breakdown.

---

## 7. AI Agents

Agents are **personas that use CIA as their data source**. They don't
build analysis tools — they *consume* CIA's risk scores, dependency
graphs, test predictions, and change detection to make informed decisions
and give evidence-based advice.

### 7.1 Code Review Agent

> **Role:** Reviews code changes using CIA's impact data.

Every recommendation this agent makes is backed by a CIA command:

| Agent action | CIA data used |
|---|---|
| "This change is high risk" | `cia analyze` → risk score |
| "11 modules depend on this file" | `cia graph` → dependents count |
| "batch_toggle has no tests" | `cia test --suggest` → coverage gaps |
| "Run these 3 test files" | `cia test --affected-only` → pytest args |

**Behavior:**

```yaml
agent: code_review
persona: >
  You are a senior code reviewer. Before giving any opinion on code
  changes, you ALWAYS run `cia analyze` to get the risk score and
  `cia test --suggest` to check coverage. You cite CIA's numbers in
  every review. You never approve without data.

on_user_request:
  1. Run: cia analyze .
  2. Run: cia test . --affected-only
  3. Run: cia test . --suggest
  4. Interpret CIA's JSON output and present a review

rules:
  - CITE CIA scores: "risk 62/100" not "seems risky"
  - CITE CIA dependents: "11 modules import this" not "many modules"
  - CITE CIA coverage: "batch_toggle has 0 tests" not "needs tests"
  - RECOMMEND based on CIA thresholds: score ≥60 → block, 30-59 → warn
```

**Example:**

```
User: review my staged changes

Agent: [runs cia analyze, cia test --affected-only, cia test --suggest]

📋 Code Review — CIA Risk: HIGH (62/100)

CIA reports `flag_definition.py` has 11 downstream dependents (score 100/100).
CIA found 1 uncovered entity: FlagStore.batch_toggle (new method, 0 tests).

Action items (from CIA data):
1. Add tests → CIA suggests `tests/test_flag_store.py`
2. Run affected tests → CIA says: pytest -k "test_flags or test_evaluation"
3. Risk driven by dependents — consider a feature branch for this change.
```

---

### 7.2 Test Coverage Agent

> **Role:** Ensures every change has tests, using CIA's test analyzer.

This agent's only data source is CIA's test analysis:

```yaml
agent: test_coverage
persona: >
  You ensure every code change has test coverage. You run
  `cia test --suggest` to find gaps and `cia test --affected-only`
  to identify which tests to run. You then write the missing tests.

on_file_save:
  1. Run: cia test . --suggest
  2. If CIA reports gaps → read the uncovered function and write tests
  3. Run: cia test . --affected-only → run only what CIA says is affected

rules:
  - ONLY flag what CIA flags — don't invent coverage concerns
  - USE CIA's suggested_file paths for new test placement
  - AFTER writing tests, re-run cia test --suggest to verify the gap closed
```

**Workflow:**

```
1. User saves src/storage/flag_store.py
2. Agent runs: cia test . --suggest
3. CIA reports: "FlagStore.batch_toggle — New method with no test coverage"
4. Agent reads flag_store.py, writes tests/test_flag_store.py
5. Agent runs: cia test . --suggest  (verify gap closed)
6. Agent runs: cia test . --affected-only  (get pytest command)
7. Agent says: "Tests written. Run: pytest tests/test_flag_store.py"
```

---

### 7.3 Architecture Guardian Agent

> **Role:** Monitors project structure using CIA's dependency graph.

This agent reads CIA's graph output and flags structural problems:

```yaml
agent: architecture_guardian
persona: >
  You monitor project architecture using CIA's dependency graph.
  Run `cia graph --format json` to detect issues. All alerts must
  cite CIA's graph data (module names, edge counts, cycle lists).

on_new_import:
  1. Run: cia graph . --format json
  2. Check CIA's cycle list — if new cycle appeared, alert
  3. Check dependents count — if any module exceeds 10, warn

rules:
  - CITE CIA graph: "CIA detected a cycle: A → B → C → A"
  - CITE CIA counts: "CIA shows module X has 12 dependents (was 10)"
  - NEVER guess — only report what CIA's graph data shows
```

**Example alert:**

```
🏗️ Architecture Alert (from CIA graph analysis)

CIA detected a new circular dependency:
  parser → graph → analyzer → parser

CIA shows cli.py now imports python_parser.py directly.
  cli.py has 0 dependents, but python_parser has 3.
  This bypasses the analyzer layer.

Recommendation: import through cia.analyzer instead.
```

---

### 7.4 Risk Advisor Agent

> **Role:** Interprets CIA's risk scores in context.

```yaml
agent: risk_advisor
persona: >
  You interpret CIA's risk analysis for developers. Run `cia analyze`
  and explain what the scores mean in plain language. All numbers
  come from CIA — you never estimate risk yourself.

on_user_ask:
  1. Run: cia analyze . --format json
  2. Read CIA's factor_scores, explanations, and suggestions
  3. Translate into actionable advice

rules:
  - ALL numbers come from CIA output — never make up scores
  - EXPLAIN which CIA factor is the biggest contributor
  - MAP CIA's suggestions to concrete next steps
  - COMPARE: "CIA scored this 62/100 — that's above the 60 threshold"
```

---

## 8. Slash Commands

Slash commands are **shortcuts that invoke CIA** through the AI assistant.
Each command runs one or more CIA CLI commands / MCP tools and presents
the results.

### 8.1 Command Reference

| Command | Runs CIA Command | Description |
|---------|-----------------|-------------|
| `/cia-review` | `cia analyze` + `cia test` | Full pre-commit review using CIA |
| `/cia-risk` | `cia analyze .` | Show CIA's risk score for staged changes |
| `/cia-tests` | `cia test . --affected-only` | Show tests CIA says are affected |
| `/cia-suggest` | `cia test . --suggest` | Show what CIA says is untested |
| `/cia-graph` | `cia graph .` | Show CIA's dependency graph |
| `/cia-blast <module>` | `cia graph . --format json` | Show CIA's dependents for a module |
| `/cia-audit` | `cia graph . --format json` | Architecture audit using CIA's graph |
| `/cia-refactor <sym>` | `cia graph` + `cia test` + `cia analyze` | CIA-guided safe refactoring |
| `/cia-pr-summary` | `cia analyze . --format json` | PR description from CIA's report |
| `/cia-init` | `cia init .` | Initialize CIA in the project |
| `/cia-config` | `cia config .` | Show/edit CIA configuration |
| `/cia-hook-install` | `cia install-hook .` | Install CIA's pre-commit hook |
| `/cia-status` | `cia version` + resource reads | CIA server status dashboard |

### 8.2 Windsurf Workflow Definitions

Each command maps to a `.windsurf/workflows/*.md` file:

#### `/cia-review`

```markdown
---
description: Run a full pre-commit review using CIA's analysis
---

1. Run `cia analyze .` to get CIA's risk report (JSON output).

2. Run `cia test . --affected-only` to get the tests CIA predicts
   are affected.

3. Run `cia test . --suggest` to get CIA's coverage gap report.

4. Present CIA's results as a structured review:
   - **Risk Score**: CIA's overall score and level
   - **Top Factors**: the highest-scoring factors from CIA's breakdown
   - **Blast Radius**: number of affected modules from CIA's report
   - **Tests to Run**: the pytest command from CIA's output
   - **Coverage Gaps**: entities CIA flagged as untested
   - **Verdict**: based on CIA's risk level (LOW/MEDIUM/HIGH/CRITICAL)
```

#### `/cia-blast`

```markdown
---
description: Show CIA's blast radius analysis for a module
---

1. Ask the user which module to analyze if not provided.

2. Run `cia graph . --format json` to get CIA's full dependency graph.

3. From CIA's graph data, find all modules that depend on the target
   (direct and transitive).

4. Present CIA's dependency data as:
   - Direct dependents (from CIA's graph edges)
   - Transitive dependents (walked from CIA's graph)
   - Total count and risk assessment based on CIA's data
```

#### `/cia-suggest`

```markdown
---
description: Find untested code using CIA and write the missing tests
---

1. Run `cia test . --suggest` to get CIA's coverage gap report.

2. If CIA reports no gaps, say "CIA found all changed code is tested."

3. For each entity CIA flagged:
   a. Read the source file CIA identified.
   b. Write a pytest test class for the uncovered function/method.
   c. Place it in the file path CIA suggested.

4. Ask the user if they want to create the test files.
```

#### `/cia-audit`

```markdown
---
description: Architecture health audit using CIA's dependency graph
---

1. Run `cia graph . --format json` to get CIA's dependency data.

2. From CIA's output, analyze:
   - **Cycles**: CIA's graph reports circular dependencies directly
   - **Fan-in**: count dependents per module from CIA's edges
   - **Orphans**: modules with no edges in CIA's graph
   - **Depth**: longest path in CIA's graph

3. Score health from A–F based on CIA's graph metrics.

4. Present each finding citing CIA's specific data (module names, counts).
```

#### `/cia-status`

```markdown
---
description: Show CIA status and project overview
---

1. Run `cia version` to get CIA's version info.
2. Run `cia config .` to get CIA's current configuration.
3. Run `cia graph . --format json` to get module/edge counts from CIA.

4. Present a dashboard with CIA's data:
   - CIA version and Python version
   - Config file location and key settings
   - Total modules and edges CIA parsed
   - Whether CIA's pre-commit hook is installed
```

### 8.3 Claude Code Integration

```bash
# Register CIA's MCP server with Claude Code
claude mcp add cia -- cia-mcp serve

# All /cia-* commands use CIA's tools through MCP
```

### 8.4 Generic MCP Prompts (Any Client)

For clients without slash commands, the MCP server exposes prompts
that instruct the AI to call CIA tools:

| Prompt Name | CIA Commands Used | Description |
|-------------|-------------------|-------------|
| `pre_commit_review` | `analyze` + `test` | Review using CIA's risk + test analysis |
| `blast_radius` | `graph` | Show CIA's dependents for a module |
| `test_gap_analysis` | `test --suggest` | Find gaps using CIA's test analyzer |
| `dependency_audit` | `graph` | Audit using CIA's dependency graph |
| `safe_refactor` | `graph` + `test` + `analyze` | Refactor guided by CIA's data |
| `pr_summary` | `analyze` | PR description from CIA's report |
| `risk_explanation` | `analyze` | Explain CIA's risk scores in detail |

---

## 9. Data Models

### RiskScore

```typescript
interface RiskScore {
  overall_score: number;   // 0–100
  level: "low" | "medium" | "high" | "critical";
  factor_scores: Record<RiskFactorType, number>;
  explanations: string[];
  suggestions: string[];
}

type RiskFactorType =
  | "complexity"
  | "churn"
  | "dependents"
  | "test_coverage"
  | "change_size"
  | "critical_path";
```

### ChangeSet

```typescript
interface ChangeSet {
  changes: Change[];
  total_additions: number;
  total_deletions: number;
}

interface Change {
  file_path: string;
  added_lines: number[];
  deleted_lines: number[];
  affected_symbols: string[];
}
```

### DependencyGraph

```typescript
interface DependencyGraph {
  modules: string[];
  edges: { from: string; to: string }[];
  module_count: number;
  edge_count: number;
  cycles: string[][];
}
```

### TestSuggestion

```typescript
interface TestSuggestion {
  entity: string;          // e.g. "flag_store::FlagStore.batch_toggle"
  reason: string;          // e.g. "New method with no test coverage"
  suggested_file: string;  // e.g. "tests/test_flag_store.py"
}
```

---

## 10. Implementation Plan

### Phase 1 — Core Server (MVP)

| Step | Task | Effort |
|------|------|--------|
| 1.1 | Set up `cia-mcp` package with `FastMCP` (Python MCP SDK) | 1 day |
| 1.2 | Implement `cia_analyze` tool | 1 day |
| 1.3 | Implement `cia_graph`, `cia_get_dependents`, `cia_get_dependencies` | 0.5 day |
| 1.4 | Implement `cia_predict_tests`, `cia_suggest_tests` | 0.5 day |
| 1.5 | Implement `cia_detect_changes` | 0.5 day |
| 1.6 | Add resources: `cia://config`, `cia://graph`, `cia://version` | 0.5 day |
| 1.7 | stdio transport + basic integration tests | 0.5 day |

**Deliverable:** Working MCP server with all read-only tools.

### Phase 2 — Skills & Prompts

| Step | Task | Effort |
|------|------|--------|
| 2.1 | Implement `pre_commit_review` skill/prompt | 0.5 day |
| 2.2 | Implement `blast_radius_analysis` skill/prompt | 0.5 day |
| 2.3 | Implement `test_gap_analysis` skill with test generation | 1 day |
| 2.4 | Implement `dependency_audit` skill with health scoring | 0.5 day |
| 2.5 | Implement `safe_refactor` and `change_storytelling` skills | 1 day |
| 2.6 | Add SSE transport support | 0.5 day |

**Deliverable:** MCP server with 7 skills and multi-step prompts.

### Phase 3 — Agents & Commands

| Step | Task | Effort |
|------|------|--------|
| 3.1 | Implement agent persona system (YAML config → system prompts) | 1 day |
| 3.2 | Code Review Agent with auto-trigger on staged changes | 1 day |
| 3.3 | Test Engineer Agent with test generation pipeline | 1 day |
| 3.4 | Architecture Guardian Agent with layering rules | 0.5 day |
| 3.5 | Risk Advisor Agent with session state tracking | 0.5 day |
| 3.6 | Continuous Monitoring background skill (resource subscriptions) | 1 day |

**Deliverable:** 4 autonomous agents with persistent context.

### Phase 4 — Slash Commands & Distribution

| Step | Task | Effort |
|------|------|--------|
| 4.1 | Create Windsurf workflow `.md` files for all 15 commands | 1 day |
| 4.2 | Claude Code command registration + prompt templates | 0.5 day |
| 4.3 | Generic MCP prompt definitions for any client | 0.5 day |
| 4.4 | Write tools: `cia_init`, `cia_config_set`, `cia_install_hook` | 0.5 day |
| 4.5 | Integration guides for Windsurf, Cursor, Claude Code, VS Code, Cline | 1 day |
| 4.6 | `pip install change-impact-analyzer[mcp]` packaging | 0.5 day |
| 4.7 | Comprehensive test suite (tools + skills + agents) | 1 day |

**Deliverable:** Production-ready server with universal client support.

### Tech Stack

| Component | Choice | Reason |
|-----------|--------|--------|
| MCP SDK | [`mcp`](https://pypi.org/project/mcp/) (official Python SDK) | Official SDK, FastMCP high-level API |
| Transport | stdio (default), SSE (optional) | Covers local and remote use cases |
| Packaging | Entry point in `pyproject.toml` | `cia-mcp` console script |
| Testing | pytest + MCP test client | Consistent with CIA's existing test infra |

### Project Structure

```
src/cia_mcp/
├── __init__.py
├── __main__.py              # `python -m cia_mcp`
├── server.py                # FastMCP server definition + transport setup
├── tools/
│   ├── __init__.py
│   ├── analyze.py           # cia_analyze, cia_detect_changes, cia_score_risk
│   ├── graph.py             # cia_graph, cia_get_dependents, cia_get_dependencies
│   ├── tests.py             # cia_predict_tests, cia_suggest_tests
│   ├── config.py            # cia_init, cia_config_get, cia_config_set
│   └── hooks.py             # cia_install_hook, cia_uninstall_hook
├── resources/
│   ├── __init__.py
│   ├── config.py            # cia://config
│   ├── graph.py             # cia://graph, cia://graph/modules, cia://graph/module/{name}
│   └── risk.py              # cia://risk/weights, cia://risk/thresholds
├── skills/
│   ├── __init__.py
│   ├── pre_commit_review.py # Multi-tool: analyze → predict → suggest → synthesize
│   ├── blast_radius.py      # Dependents + graph + risk heatmap
│   ├── test_gap.py          # Suggest tests + generate skeletons
│   ├── dependency_audit.py  # Graph health scoring (A–F)
│   ├── safe_refactor.py     # Guided rename/move with verification
│   ├── change_story.py      # PR description generator
│   └── monitoring.py        # Background resource subscription skill
├── agents/
│   ├── __init__.py
│   ├── base.py              # Agent persona system + state management
│   ├── code_reviewer.py     # Code Review Agent
│   ├── test_engineer.py     # Test Engineer Agent
│   ├── arch_guardian.py     # Architecture Guardian Agent
│   └── risk_advisor.py      # Risk Advisor Agent
├── prompts/
│   ├── __init__.py
│   └── templates.py         # MCP prompt definitions for any client
└── commands/
    ├── __init__.py
    └── registry.py           # Slash command → skill/tool routing

.windsurf/workflows/          # Windsurf-specific slash command workflows
├── cia-review.md
├── cia-risk.md
├── cia-tests.md
├── cia-suggest.md
├── cia-graph.md
├── cia-blast.md
├── cia-audit.md
├── cia-refactor.md
├── cia-pr-summary.md
├── cia-status.md
├── cia-init.md
├── cia-config.md
└── cia-hook-install.md
```

---

## 11. Client Integration Guide

### Windsurf / Cascade

```jsonc
// .windsurf/mcp_config.json
{
  "mcpServers": {
    "cia": {
      "command": "cia-mcp",
      "args": ["serve"],
      "cwd": "${workspaceFolder}"
    }
  }
}
```

### Claude Code

```bash
# Add to Claude Code MCP settings
claude mcp add cia -- cia-mcp serve
```

### Cursor

```jsonc
// .cursor/mcp.json
{
  "mcpServers": {
    "cia": {
      "command": "cia-mcp",
      "args": ["serve"]
    }
  }
}
```

### VS Code (Copilot / Continue)

```jsonc
// .vscode/mcp.json
{
  "servers": {
    "cia": {
      "type": "stdio",
      "command": "cia-mcp",
      "args": ["serve"]
    }
  }
}
```

### Cline

```jsonc
// cline_mcp_settings.json
{
  "mcpServers": {
    "cia": {
      "command": "cia-mcp",
      "args": ["serve"],
      "disabled": false
    }
  }
}
```

### Any Client (SSE)

```bash
# Start the server
cia-mcp serve --transport sse --port 3001

# Client connects to http://localhost:3001/sse
```

---

## 12. Security Considerations

| Concern | Mitigation |
|---------|------------|
| **File system access** | Server only reads files within the Git repo; respects `.gitignore` |
| **Write operations** | `cia_config_set`, `cia_install_hook`, `cia_init` are marked as requiring user confirmation; clients should prompt before executing |
| **Git operations** | Read-only Git access (diff, log); no push/pull/commit |
| **Code execution** | No `eval()` or subprocess; AST parsing only |
| **Secrets** | No API keys required; no network calls |
| **Path traversal** | All paths resolved relative to repo root; symlinks not followed outside repo |

---

## 13. Open Questions

1. **Caching** — Should the server cache the dependency graph between
   tool calls? Pros: faster. Cons: stale data if files change mid-session.
   *Proposed: cache with file-watcher invalidation.*

2. **Multi-repo** — Should one server instance support multiple repos?
   *Proposed: one server per repo (matches MCP patterns).*

3. **Streaming** — Should `cia_analyze` stream progress updates for large
   repos? *Proposed: v2, using MCP progress notifications.*

4. **Language support** — When CIA adds support for other languages
   (TypeScript, Java, …), the MCP tools automatically gain those
   capabilities. No MCP-layer changes needed.

5. **MCP Sampling** — Should the server use MCP sampling to ask the LLM
   to generate test code for `test_gap_analysis`? Or return suggestions
   and let the client-side LLM handle generation?

---

## Quick Start (After Implementation)

```bash
# Install
pip install change-impact-analyzer[mcp]

# Verify
cia-mcp serve --help

# Add to your AI assistant's MCP config (see Section 10)

# Then ask your AI assistant:
#   "Run a CIA pre-commit review of my staged changes"
#   "What's the blast radius if I change the User model?"
#   "What tests am I missing for my recent changes?"
```
