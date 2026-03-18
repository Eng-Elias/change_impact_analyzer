# Sample Project

A minimal Python package demonstrating Change Impact Analyzer (CIA).

## Structure

```
sample_project/
├── __init__.py          # Package root
├── main.py              # Entry point — depends on utils and models
├── models.py            # Data structures — depended on by main
├── utils.py             # Utility functions — depended on by main
├── .ciarc               # CIA configuration
├── tests/
│   ├── test_utils.py    # Tests for utils
│   └── test_models.py   # Tests for models
└── README.md            # This file
```

## Try It

```bash
# From the repository root:
cd examples/sample_project

# Initialise a Git repo (CIA requires one)
git init && git add -A && git commit -m "init"

# Make a change
echo "NEW_CONST = 42" >> utils.py
git add utils.py

# Analyse the impact
cia analyze --format markdown --explain

# See affected tests
cia analyze --test-only

# Generate an HTML report
cia analyze --format html --output report.html
```

## Dependency Graph

```
main.py ──▶ utils.py
   │
   └──────▶ models.py
```

Changing `utils.py` affects `main.py` (direct dependent).
Changing `models.py` affects `main.py` (direct dependent).

## Example JSON Output

```json
{
  "schema_version": "1.0.0",
  "summary": {
    "total_files_changed": 1,
    "total_symbols_affected": 2,
    "total_modules_affected": 1
  },
  "risk": {
    "overall_score": 32.0,
    "level": "medium",
    "factor_scores": {
      "complexity": 15.0,
      "change_size": 10.0,
      "dependents": 45.0,
      "test_coverage": 0.0,
      "churn": 20.0,
      "critical_path": 30.0
    }
  }
}
```
