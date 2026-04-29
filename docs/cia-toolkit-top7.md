# CIA Toolkit for AI Coding Assistants — Top 7 Recommendations

> The **Change Impact Analyzer (CIA)** provides risk scoring, dependency
> graphs, test prediction, and change detection for Python projects.
> This document proposes the **7 highest-value items** to package as a
> toolkit/plugin that any AI coding assistant can use via MCP.

---

## At a Glance

| # | Item | Type | CIA Commands Used | Value |
|---|------|------|-------------------|-------|
| 1 | [Pre-Commit Review](#1-pre-commit-review-skill) | Skill | `analyze` + `test` | Prevents risky commits |
| 2 | [Impact Explorer](#2-impact-explorer-mcp-tool) | MCP Tool | `graph` + `analyze` | Answers "what breaks if I change X?" |
| 3 | [Test Gap Agent](#3-test-gap-agent) | Agent | `test --suggest` | Finds and writes missing tests |
| 4 | [Risk Score Resource](#4-live-risk-score-resource) | MCP Resource | `analyze` | Real-time risk in the sidebar |
| 5 | [Architecture Audit](#5-architecture-audit-command) | Command | `graph` | One-click project health check |
| 6 | [Code Review Agent](#6-code-review-agent) | Agent | `analyze` + `test` + `graph` | Evidence-based PR reviews |
| 7 | [Safe Refactor Guide](#7-safe-refactor-guide-skill) | Skill | `graph` + `test` | CIA-guided rename/move |

---

## 1. Pre-Commit Review (Skill)

**Why number 1:** This is the single most impactful feature. Every developer
commits code and CIA can gate that moment with data.

**CIA commands used:**

```
cia analyze .              ->  risk score (0-100), level, factor breakdown
cia test . --affected-only ->  which existing tests to run
cia test . --suggest       ->  what new tests are needed
```

**Example output:**

```
Pre-Commit Review (powered by CIA)

Risk: HIGH (62/100)
  Top factor: dependents 100/100  --  11 modules import flag_definition

Tests to run: pytest -k "test_flags or test_evaluation or test_sdk"
Coverage gap: FlagStore.batch_toggle has no tests

Recommendation: Add tests before committing.
```

**Integration:**

- **Windsurf:** `/cia-review` workflow
- **Claude Code:** `pre_commit_review` MCP prompt
- **Any MCP client:** tool calls to `cia_analyze` + `cia_predict_tests` + `cia_suggest_tests`

**Why it matters:** Catches high-risk commits before they reach CI.
Replaces gut-feel with CIA quantified risk scores. Suggests concrete
actions (specific tests, specific files).

---

## 2. Impact Explorer (MCP Tool)

**Why number 2:** Developers constantly ask "if I change this, what else
is affected?" CIA dependency graph answers this instantly.

**CIA commands used:**

```
cia graph . --format json  ->  full dependency graph with edges
```

The MCP tool `cia_get_dependents` wraps this and returns structured data:

```json
{
  "module": "flag_definition",
  "direct_dependents": ["engine", "client", "flag_store", "changelog"],
  "transitive_dependents": ["middleware", "sdk_client", "test_evaluation"],
  "total": 11
}
```

**Example interaction:**

The developer asks "what breaks if I change flag_definition?" and the
assistant runs `cia graph` to answer:

```
CIA shows flag_definition has 11 downstream dependents:
  Depth 1: engine, client, flag_store, changelog
  Depth 2: middleware, sdk_client, test_evaluation
  Depth 3: test_sdk, test_audit

This is the most connected module in the project.
Affected tests: pytest -k "test_flags or test_evaluation or test_sdk"
```

**Why it matters:** No more guessing about impact. CIA graph data gives
the exact list of affected modules and the tests that cover them.

---

## 3. Test Gap Agent

**Why number 3:** Missing test coverage is the number one source of
regressions. CIA identifies exactly what is untested.

**CIA commands used:**

```
cia test . --suggest  ->  list of uncovered entities with reasons
```

**How the agent works:**

1. The agent runs `cia test . --suggest`
2. CIA reports: "FlagStore.batch_toggle -- New method with no test coverage"
3. The agent reads the source function CIA identified
4. The agent writes a pytest test skeleton for that function
5. The agent re-runs `cia test . --suggest` to verify the gap closed

**Key principle:** CIA identifies WHAT is untested. The AI agent writes
the tests. CIA is the data source, the agent is the executor.

**Example CIA output the agent consumes:**

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

The agent reads `batch_toggle` source code, then writes tests in the file
path CIA suggested.

**Why it matters:** Developers get test skeletons written automatically
for exactly the code CIA flags as uncovered. No manual coverage analysis.

---

## 4. Live Risk Score (MCP Resource)

**Why number 4:** Provides passive, always-on awareness of change risk
without the developer needing to ask.

**CIA commands used:**

```
cia analyze . --format json  ->  risk score updated on each change
```

**How it works:**

The MCP server exposes `cia://changes/risk` as a dynamic resource.
The AI assistant subscribes to it. Whenever the developer stages files,
CIA re-computes the risk score and the assistant gets the update.

**When the assistant speaks up:**

The assistant stays silent when risk is LOW. It only notifies on
transitions:

```
CIA Notice: Your staged changes just crossed into HIGH risk (score: 62).
  Main driver: 8 downstream modules depend on flag_definition.
  Run /cia-review for details.
```

**Why it matters:** Risk awareness without friction. The developer never
has to remember to run an analysis -- CIA watches in the background and
the assistant alerts only when it matters.

---

## 5. Architecture Audit (Command)

**Why number 5:** Project health degrades silently. CIA graph data
reveals structural problems that are invisible in day-to-day coding.

**CIA commands used:**

```
cia graph . --format json  ->  modules, edges, cycles
```

**What the assistant computes from CIA data:**

| Metric | Source in CIA output |
|--------|-------------------|
| Circular dependencies | CIA graph cycle detection |
| God modules (fan-in above 10) | Count edges pointing to each module |
| Orphan modules | Modules with 0 edges in CIA graph |
| Max dependency depth | Longest path in CIA graph |

**Example output:**

```
Architecture Audit (powered by CIA graph analysis)

Grade: B (score 28/100)

Findings:
  OK    Circular dependencies: 0 cycles
  WARN  God modules: flag_definition has 11 dependents
  OK    Orphan modules: 0
  OK    Max depth: 4 (threshold: 8)

Recommendation: Consider splitting flag_definition into
flag_types and flag_evaluation to reduce its fan-in.
```

**Slash command:** `/cia-audit`

**Why it matters:** One command gives a full project health check backed
entirely by CIA data. No manual graph inspection needed.

---

## 6. Code Review Agent

**Why number 6:** Combines CIA risk, dependency, and test data into a
single evidence-based review persona.

**CIA commands used:**

```
cia analyze .              ->  risk score and factor breakdown
cia test . --affected-only ->  tests to run
cia test . --suggest       ->  coverage gaps
cia graph . --format json  ->  dependency context
```

**Agent behavior:**

Every statement the agent makes cites CIA data:

```yaml
agent: code_review
persona: >
  You review code changes using CIA data. Before any opinion, you run
  cia analyze and cia test. You cite CIA scores and counts in every
  review. You never approve without checking CIA blast radius.

rules:
  - CITE CIA scores: "CIA risk 62/100" not "seems risky"
  - CITE CIA dependents: "CIA shows 11 dependents" not "many modules"
  - CITE CIA coverage: "CIA found 0 tests for batch_toggle"
  - RECOMMEND based on CIA thresholds
```

**Example review:**

```
Code Review (CIA data)

CIA Risk: HIGH (62/100)
CIA reports flag_definition.py has 11 downstream dependents.
CIA found 1 uncovered entity: FlagStore.batch_toggle (0 tests).

Action items:
1. Add tests -- CIA suggests tests/test_flag_store.py
2. Run affected tests -- CIA says: pytest -k "test_flags or test_evaluation"
3. Consider a feature branch -- CIA dependents score is 100/100
```

**Why it matters:** Code reviews grounded in data, not opinion.
Every recommendation traces back to a specific CIA metric.

---

## 7. Safe Refactor Guide (Skill)

**Why number 7:** Renaming or moving code is risky without knowing who
depends on it. CIA graph tells you exactly.

**CIA commands used:**

```
cia graph . --format json  ->  who imports the target symbol
cia test . --affected-only ->  tests to run after the refactor
cia analyze .              ->  risk score for the change
```

**How the skill works:**

1. The developer says "help me rename FlagStore to FeatureFlagStore"
2. The assistant runs `cia graph` to find every module that imports FlagStore
3. CIA reports: engine.py, client.py, middleware.py, and 4 test files
4. The assistant builds a checklist:
   - Rename class in flag_store.py
   - Update import in engine.py (CIA edge: engine -> flag_store)
   - Update import in client.py (CIA edge: client -> flag_store)
   - Update import in middleware.py (CIA edge: middleware -> flag_store)
   - Update 4 test files
5. After applying changes, the assistant runs `cia test --affected-only`
6. CIA provides the pytest command to verify nothing broke

**Example output:**

```
Safe Refactor Guide (powered by CIA)

Renaming: FlagStore -> FeatureFlagStore

CIA found 7 files that import FlagStore:
  src/engine.py           (line 3: from flag_store import FlagStore)
  src/client.py           (line 5: from flag_store import FlagStore)
  src/middleware.py        (line 2: from flag_store import FlagStore)
  tests/test_flag_store.py
  tests/test_engine.py
  tests/test_client.py
  tests/test_middleware.py

CIA risk for this refactor: MEDIUM (45/100)
After refactoring, run: pytest -k "test_flag or test_engine or test_client"
```

**Why it matters:** Zero guesswork about what to update. CIA graph data
guarantees you find every reference. CIA tests guarantee you verify the
result.

---

## Packaging as a Toolkit

### What Ships Together

```
cia-mcp-toolkit/
  mcp-server/          MCP server wrapping CIA CLI
    tools/             cia_analyze, cia_graph, cia_test, etc.
    resources/         cia://changes/risk, cia://graph, etc.
    prompts/           pre_commit_review, blast_radius, etc.
  skills/              Multi-step workflows (items 1, 7)
  agents/              Persona definitions (items 3, 6)
  commands/            Slash command definitions (item 5)
  windsurf-workflows/  .windsurf/workflows/*.md files
  claude-code-config/  Claude Code MCP registration
```

### One Install, All Assistants

```bash
pip install change-impact-analyzer[mcp]
```

This installs the `cia-mcp` command. Each AI assistant connects
to it through its own config:

| Assistant | Config |
|-----------|--------|
| Windsurf | `.windsurf/mcp_config.json` + workflows |
| Claude Code | `claude mcp add cia -- cia-mcp serve` |
| Cursor | `.cursor/mcp.json` |
| VS Code Copilot | `.vscode/mcp.json` |
| Cline | `.cline/mcp_settings.json` |
| Open Code | `--mcp-config mcp.json` |

### Priority Order for Implementation

| Phase | Items | Effort |
|-------|-------|--------|
| Phase 1 (MVP) | MCP tools + item 1 (Pre-Commit Review) + item 2 (Impact Explorer) | 3 days |
| Phase 2 | Item 3 (Test Gap Agent) + item 4 (Live Risk Resource) | 3 days |
| Phase 3 | Item 5 (Audit Command) + item 6 (Code Review Agent) | 2 days |
| Phase 4 | Item 7 (Safe Refactor) + packaging + client configs | 2 days |

**Total estimated effort: 10 days to a production-ready toolkit.**

All 7 items share a single principle: **CIA does the analysis, the AI
assistant does the communication.** CIA is the engine; the toolkit is
the interface.
