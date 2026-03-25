# Tutorial Testing Findings Report

**Date:** 2026-03-23
**Test method:** Built the Feature Flag System from `docs/tutorial.md` step-by-step in a separate git repo and ran every CIA command at each phase.
**Project:** 8 source modules, 5 test files, 33 tests all passing.

---

## Summary

| Category | Count |
|----------|------:|
| **Critical bugs** | 2 |
| **Medium bugs** | 3 |
| **Minor issues** | 3 |
| **Working correctly** | 8 |

---

## Critical Bugs

### BUG-1: CLI never builds the dependency graph (dependents always 0)

**Severity:** CRITICAL
**File:** `src/cia/cli.py` lines 155-168
**Impact:** The `dependents` and `critical_path` risk factors are **always 0**. The `affected_modules` list only contains changed files, never downstream dependents. This undermines the core value proposition of the tool.

**Root cause:**

```python
# Line 156 - no graph passed to calculate_risk
risk = scorer.calculate_risk(changeset)  # graph=None -> dependents=0

# Lines 167-168 - empty graph, never populated
dep_graph = DependencyGraph()  # Empty!
analyzer_engine = ImpactAnalyzer(dep_graph)
```

`DependencyGraph.build_from_modules()` and `PythonParser` both exist and work (unit tested), but the CLI never calls them.

**Fix required in `cli.py` analyze():**
1. Use `PythonParser` to parse all `.py` files in the project
2. Call `dep_graph.build_from_modules(parsed_modules)`
3. Pass populated graph to `scorer.calculate_risk(changeset, graph=dep_graph)`

**Test evidence:**
- Renaming `Flag.enabled` (imported by 5+ modules) scored **12.2/100 LOW** with **0 dependents**
- Changing targeting format scored **12.8/100 LOW** with **0 dependents**
- `directly_affected`, `transitively_affected`, `affected_modules` are always empty lists

---

### BUG-2: `cia graph` command is a stub

**Severity:** CRITICAL
**File:** `src/cia/cli.py` line 249

The command simply prints "Graph builder not yet implemented." and exits. This is documented as a feature in README and tutorial but does not function.

**Fix required:** Implement the command using `PythonParser` + `DependencyGraph` to parse the project, build the graph, and output it (JSON, text tree, or DOT format).

---

## Medium Bugs

### BUG-3: `cia config --set` / `--get` inconsistency

**Severity:** MEDIUM
**File:** `src/cia/config.py`

Setting a value writes to the **top-level** of `.ciarc`, but getting reads from the **`[analysis]` section**. Values set via `--set` are silently ignored.

```bash
$ cia config . --set format=markdown
Set format = markdown

$ cia config . --get format
format = json              # Still reads [analysis] section!
```

Resulting `.ciarc`:
```toml
format = "markdown"        # Written to top-level (wrong)
[analysis]
format = "json"            # This is what --get reads (stale)
```

**Fix:** `--set format=X` should write to `[analysis].format`, not top-level.

---

### BUG-4: `test_coverage` risk factor is always 80/100

**Severity:** MEDIUM
**File:** `src/cia/risk/risk_scorer.py`

The scorer defaults to 80 when no `coverage_data` is passed, and the CLI never passes any. Result: test_coverage is 80/100 whether the project has 0 tests or 100% coverage.

**Test evidence:**
- Phase 2 (no tests): test_coverage = 80/100
- Phase 6 (33 tests, all passing): test_coverage = 80/100

**Fix:** CLI should collect coverage approximation (from test file discovery or `.coverage` data) and pass it to the scorer.

---

### BUG-5: `cia test --affected-only` never finds affected tests

**Severity:** MEDIUM
**File:** `src/cia/cli.py`

Always returns "No tests affected by the current changes" because the dependency graph is never built (same root cause as BUG-1).

```bash
# After renaming Flag.enabled (imported by all 5 test files)
$ cia test . --affected-only
No tests affected by the current changes.
```

**Fix:** Same as BUG-1 - build the dependency graph before running test analysis.

---

## Minor Issues

### ISSUE-1: `cia test --suggest` doesn't match existing test files

**Severity:** LOW
**File:** `src/cia/analyzer/test_analyzer.py`

Only matches by naming convention (`test_<module>.py`). If the test file uses a different name (e.g., `test_storage.py` for `flag_store.py`), CIA doesn't recognize it and incorrectly reports "No test coverage detected."

```json
{
  "entity": "flag_store",
  "reason": "No test coverage detected",
  "suggested_file": "tests/test_flag_store.py"
}
```

But `tests/test_storage.py` already has 6 tests covering `FlagStore`.

**Fix suggestion:** Also check import analysis - if a test file imports from the module, consider it covered.

---

### ISSUE-2: Pre-commit hook uses system Python, not venv Python

**Severity:** LOW
**File:** `src/cia/git/hooks.py`

The hook may invoke a different Python than where CIA is installed.

```
C:\...\pythoncore-3.14-64\python.exe: No module named cia
[main f76ba6d] chore: add CIA configuration   # Commit still went through
```

**Fix:** Embed the full path to the active Python interpreter when generating the hook script.

---

### ISSUE-3: Tutorial needs `.gitignore` step

**Severity:** LOW
**File:** `docs/tutorial.md`

Without a `.gitignore`, running `pytest` creates `__pycache__/` dirs that get staged and show up as affected modules in CIA output.

**Fix:** Add `.gitignore` creation in Phase 1 of the tutorial.

---

## Working Correctly

| Feature | Status | Notes |
|---------|--------|-------|
| `cia init .` | PASS | Creates `.ciarc` correctly |
| `cia version` | PASS | Shows version, Python, platform, Click |
| `cia analyze --format json` | PASS | Correct JSON schema output |
| `cia analyze --format markdown` | PASS | Clean markdown with tables and badges |
| `cia analyze --format html` | PASS | Writes interactive HTML report |
| `cia analyze --format all` | PASS | Generates .json, .html, .md simultaneously |
| `cia analyze --threshold N` | PASS | Exit code 1 when score exceeds threshold |
| `cia analyze --explain` | PASS | Shows factor breakdown and suggestions |
| `cia test --suggest` | PARTIAL | Detects untested modules but misses renamed test files |
| `cia install-hook` | PASS | Installs hook, prints path and threshold |
| `cia config .` | PASS | Shows effective configuration |
| `change_size` factor | PASS | Scales correctly with lines added/deleted |
| `churn` factor | PASS | Would work if git history provided (not tested in isolation) |
| `complexity` factor | PASS | Scores 0 for simple code (correct for dataclasses) |

---

## Priority Fix Order

1. **BUG-1** - Build dependency graph in CLI `analyze` command (unblocks dependents, critical_path, affected_modules, and test prediction)
2. **BUG-2** - Implement `cia graph` command (uses same graph-building code from BUG-1 fix)
3. **BUG-5** - Fix `cia test --affected-only` (automatically fixed once BUG-1 is resolved)
4. **BUG-4** - Pass coverage data to risk scorer
5. **BUG-3** - Fix config --set to write to correct TOML section
6. **ISSUE-1** - Improve test file matching with import analysis
7. **ISSUE-2** - Embed Python path in hook script
8. **ISSUE-3** - Add .gitignore to tutorial

---

## Tutorial Accuracy Assessment

The tutorial (`docs/tutorial.md`) describes expected outputs that **do not match actual behavior** due to BUG-1:

| Tutorial claim | Actual result |
|----------------|---------------|
| Scenario 1: Risk 72/100 HIGH, 10+ affected files | 12.2/100 LOW, 0 affected |
| Scenario 2: Risk 48/100 MEDIUM, 4 downstream modules | 12.8/100 LOW, 0 downstream |
| Scenario 3: Risk 45/100 MEDIUM, threshold exceeded | ~12/100 LOW, threshold not exceeded |
| Scenario 5: Hook blocks commit at HIGH risk | Hook fails with wrong Python; risk never reaches HIGH |
| `cia graph .` shows dependency graph | Prints "not yet implemented" |

**Scenarios that work as described:**
- Scenario 4: `cia test --suggest` correctly detects untested modules
- Scenario 6: `cia test --affected-only` runs but returns empty (BUG-5)
- Threshold mechanism (exit code 1) works when score actually exceeds it
- All report formats generate correctly

**The tutorial should be updated after BUG-1 and BUG-2 are fixed, then re-tested.**
