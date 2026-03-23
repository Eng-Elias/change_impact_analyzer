# Tutorial: Feature Flag System — Step-by-Step with CIA

This hands-on tutorial walks you through building a **Feature Flag System** from scratch while using **Change Impact Analyzer (CIA)** to catch mistakes, assess risk, and predict test impact at every step.

You will copy-paste real code, commit incrementally, and run every CIA command in realistic developer scenarios — including mistakes that CIA helps you avoid.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Project Overview](#2-project-overview)
3. [Phase 1 — Project Setup & CIA Init](#3-phase-1--project-setup--cia-init)
4. [Phase 2 — Core Models](#4-phase-2--core-models)
5. [Phase 3 — Evaluation Engine](#5-phase-3--evaluation-engine)
6. [Phase 4 — Storage & Audit](#6-phase-4--storage--audit)
7. [Phase 5 — SDK Layer](#7-phase-5--sdk-layer)
8. [Phase 6 — Tests](#8-phase-6--tests)
9. [Phase 7 — CIA Configuration & Hooks](#9-phase-7--cia-configuration--hooks)
10. [Scenario 1 — Dangerous Field Rename](#10-scenario-1--dangerous-field-rename)
11. [Scenario 2 — Silent Format Change](#11-scenario-2--silent-format-change)
12. [Scenario 3 — Algorithm Swap with Hidden Blast Radius](#12-scenario-3--algorithm-swap-with-hidden-blast-radius)
13. [Scenario 4 — New Feature Without Tests](#13-scenario-4--new-feature-without-tests)
14. [Scenario 5 — Pre-Commit Hook Blocks a Risky Commit](#14-scenario-5--pre-commit-hook-blocks-a-risky-commit)
15. [Scenario 6 — Targeted Test Runs](#15-scenario-6--targeted-test-runs)
16. [CIA Command Reference](#16-cia-command-reference)

---

## 1. Prerequisites

```bash
# Install CIA (requires Python 3.11+)
pip install change-impact-analyzer

# Verify
cia version
```

You also need **Git** installed and available in your PATH.

---

## 2. Project Overview

We are building a **Feature Flag System** — the kind of infrastructure that powers A/B tests, gradual rollouts, and kill switches at companies like GitHub, Netflix, and LaunchDarkly.

**Architecture:**

```
feature_flags/
├── flags/
│   ├── __init__.py
│   ├── flag_definition.py     # Flag & Variant data models
│   └── targeting.py           # UserContext, Segment, TargetingRule
├── evaluation/
│   ├── __init__.py
│   ├── engine.py              # FlagEvaluator — core decision logic
│   └── percentage_rollout.py  # Hash-based consistent rollout
├── storage/
│   ├── __init__.py
│   └── flag_store.py          # JSON file persistence
├── audit/
│   ├── __init__.py
│   └── changelog.py           # AuditLog — compliance trail
├── sdk/
│   ├── __init__.py
│   ├── client.py              # FeatureFlagClient — app-facing SDK
│   └── middleware.py          # FeatureFlagMiddleware — request-level
└── tests/
    ├── test_flags.py
    ├── test_evaluation.py
    ├── test_storage.py
    ├── test_audit.py
    └── test_sdk.py
```

**Dependency flow:**

```
flag_definition ◄── targeting
      │                │
      ▼                ▼
   engine ◄── percentage_rollout
      │
      ▼
  flag_store ──► changelog
      │               │
      ▼               ▼
   client ◄───── middleware
```

Every module depends on `flag_definition`. A change there ripples everywhere.

---

## 3. Phase 1 — Project Setup & CIA Init

### Step 1: Create the project and initialize Git

```bash
mkdir feature_flags
cd feature_flags
git init

# Create the directory structure
mkdir -p flags evaluation storage audit sdk tests
```

### Step 2: Create `__init__.py` files

Create empty init files so Python treats each directory as a package:

```bash
touch flags/__init__.py
touch evaluation/__init__.py
touch storage/__init__.py
touch audit/__init__.py
touch sdk/__init__.py
touch tests/__init__.py
```

### Step 3: Initial commit

```bash
git add -A
git commit -m "chore: initial project structure"
```

### Step 4: Initialize CIA

```bash
cia init .
```

This creates a `.ciarc` configuration file. You should see:

```
Created .ciarc in /path/to/feature_flags
```

### Step 5: Explore CIA commands

```bash
# See all available commands
cia --help

# Check version and platform info
cia version
```

---

## 4. Phase 2 — Core Models

### Step 1: Create `flags/flag_definition.py`

This is the foundation — every other module imports from here.

```python
# flags/flag_definition.py
from dataclasses import dataclass, field


@dataclass
class Variant:
    """A variant of a feature flag (e.g., 'control', 'treatment_a')."""

    name: str
    value: str
    weight: int = 1  # Used for percentage rollouts


@dataclass
class Flag:
    """A feature flag definition."""

    name: str
    description: str
    enabled: bool = False
    variants: list[Variant] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    def default_variant(self) -> Variant | None:
        """Return the first variant, or None if no variants defined."""
        return self.variants[0] if self.variants else None

    def is_boolean(self) -> bool:
        """Return True if this is a simple on/off flag with no variants."""
        return len(self.variants) == 0
```

### Step 2: Create `flags/targeting.py`

```python
# flags/targeting.py
from dataclasses import dataclass, field


@dataclass
class UserContext:
    """Context about the current user for targeting evaluation."""

    user_id: str
    email: str = ""
    country: str = ""
    plan: str = "free"
    attributes: dict[str, str] = field(default_factory=dict)


@dataclass
class Segment:
    """A named group of users matching certain criteria."""

    name: str
    conditions: list[dict[str, str]] = field(default_factory=list)

    def matches(self, context: UserContext) -> bool:
        """Check if a user context matches all conditions in this segment."""
        for condition in self.conditions:
            attr = condition.get("attribute", "")
            operator = condition.get("operator", "equals")
            value = condition.get("value", "")

            user_value = getattr(
                context, attr, context.attributes.get(attr, "")
            )

            if operator == "equals" and str(user_value) != value:
                return False
            if operator == "not_equals" and str(user_value) == value:
                return False
            if operator == "contains" and value not in str(user_value):
                return False
        return True


@dataclass
class TargetingRule:
    """A rule that maps a segment to a specific variant."""

    segment: Segment
    variant_name: str
    priority: int = 0
```

### Step 3: Stage, analyze, and commit

```bash
git add flags/

# Run CIA on your staged changes — your first analysis!
cia analyze . --format markdown --explain
```

**What you should see:** A low risk score (likely 5–15/100) because this is a
new file with no downstream dependents yet. The explanation will show:

- **Complexity:** Low (simple dataclasses)
- **Dependents:** 0 (nothing imports this yet)
- **Test coverage:** High risk (no tests yet!)

```bash
git commit -m "feat: add Flag, Variant, UserContext, Segment models"
```

> **CIA insight:** Even at this early stage, CIA flags the lack of test
> coverage. It's telling you to write tests before the codebase grows.

---

## 5. Phase 3 — Evaluation Engine

### Step 1: Create `evaluation/percentage_rollout.py`

```python
# evaluation/percentage_rollout.py
import hashlib

from flags.flag_definition import Variant


class PercentageRollout:
    """Hash-based percentage rollout for consistent variant assignment."""

    def assign_variant(
        self, flag_name: str, user_id: str, variants: list[Variant]
    ) -> Variant:
        """Assign a variant based on consistent hashing.

        The same user always gets the same variant for a given flag.
        """
        hash_key = f"{flag_name}:{user_id}"
        hash_value = int(
            hashlib.md5(hash_key.encode()).hexdigest(), 16
        )

        total_weight = sum(v.weight for v in variants)
        if total_weight == 0:
            return variants[0]

        bucket = hash_value % total_weight
        cumulative = 0
        for variant in variants:
            cumulative += variant.weight
            if bucket < cumulative:
                return variant

        return variants[-1]  # Fallback

    def get_percentage(
        self, flag_name: str, user_id: str
    ) -> float:
        """Get the rollout percentage bucket (0.0-100.0) for a user."""
        hash_key = f"{flag_name}:{user_id}"
        hash_value = int(
            hashlib.md5(hash_key.encode()).hexdigest(), 16
        )
        return (hash_value % 10000) / 100.0
```

### Step 2: Create `evaluation/engine.py`

```python
# evaluation/engine.py
from flags.flag_definition import Flag, Variant
from flags.targeting import TargetingRule, UserContext
from evaluation.percentage_rollout import PercentageRollout


class FlagEvaluator:
    """Core evaluation engine for feature flags."""

    def __init__(self) -> None:
        self._rules: dict[str, list[TargetingRule]] = {}
        self._rollout = PercentageRollout()

    def add_rule(self, flag_name: str, rule: TargetingRule) -> None:
        """Register a targeting rule for a flag."""
        if flag_name not in self._rules:
            self._rules[flag_name] = []
        self._rules[flag_name].append(rule)
        self._rules[flag_name].sort(
            key=lambda r: r.priority, reverse=True
        )

    def evaluate(
        self, flag: Flag, context: UserContext
    ) -> Variant | None:
        """Evaluate a flag for a given user context.

        Returns the matched variant or None if the flag is disabled.
        """
        if not flag.enabled:
            return None

        # Check targeting rules first (highest priority wins)
        rules = self._rules.get(flag.name, [])
        for rule in rules:
            if rule.segment.matches(context):
                for variant in flag.variants:
                    if variant.name == rule.variant_name:
                        return variant

        # Fall back to percentage rollout
        if flag.variants:
            return self._rollout.assign_variant(
                flag.name, context.user_id, flag.variants
            )

        # Boolean flag: enabled means "on"
        return flag.default_variant()

    def evaluate_bool(
        self, flag: Flag, context: UserContext
    ) -> bool:
        """Evaluate a boolean flag. Returns True if enabled."""
        if flag.is_boolean():
            return flag.enabled
        result = self.evaluate(flag, context)
        return result is not None
```

### Step 3: Stage and analyze

```bash
git add evaluation/

# Analyze — now there are dependencies!
cia analyze . --format markdown --explain
```

**What you should see:** The risk score climbs (likely 20–35/100) because:

- **Dependents:** `engine.py` imports from `flag_definition`, `targeting`, and
  `percentage_rollout`
- **Complexity:** Moderate (conditional logic, hash computation)
- **Test coverage:** Still no tests — CIA keeps warning you

```bash
# View the dependency graph
cia graph .

git commit -m "feat: add FlagEvaluator and PercentageRollout"
```

---

## 6. Phase 4 — Storage & Audit

### Step 1: Create `storage/flag_store.py`

```python
# storage/flag_store.py
import json
from pathlib import Path

from flags.flag_definition import Flag, Variant


class FlagStore:
    """Persistent storage for feature flags using JSON files."""

    def __init__(self, storage_path: str = "flags.json") -> None:
        self._path = Path(storage_path)
        self._flags: dict[str, Flag] = {}
        if self._path.exists():
            self._load()

    def _load(self) -> None:
        """Load flags from the JSON file."""
        data = json.loads(self._path.read_text())
        for name, flag_data in data.items():
            variants = [
                Variant(
                    name=v["name"],
                    value=v["value"],
                    weight=v.get("weight", 1),
                )
                for v in flag_data.get("variants", [])
            ]
            self._flags[name] = Flag(
                name=name,
                description=flag_data.get("description", ""),
                enabled=flag_data.get("enabled", False),
                variants=variants,
                tags=flag_data.get("tags", []),
            )

    def save(self) -> None:
        """Persist all flags to the JSON file."""
        data = {}
        for name, flag in self._flags.items():
            data[name] = {
                "description": flag.description,
                "enabled": flag.enabled,
                "variants": [
                    {
                        "name": v.name,
                        "value": v.value,
                        "weight": v.weight,
                    }
                    for v in flag.variants
                ],
                "tags": flag.tags,
            }
        self._path.write_text(json.dumps(data, indent=2))

    def get(self, name: str) -> Flag | None:
        """Retrieve a flag by name."""
        return self._flags.get(name)

    def list_flags(self) -> list[Flag]:
        """Return all stored flags."""
        return list(self._flags.values())

    def create(self, flag: Flag) -> None:
        """Add a new flag to the store."""
        self._flags[flag.name] = flag
        self.save()

    def update(self, flag: Flag) -> None:
        """Update an existing flag."""
        if flag.name not in self._flags:
            raise KeyError(f"Flag '{flag.name}' not found")
        self._flags[flag.name] = flag
        self.save()

    def delete(self, name: str) -> None:
        """Remove a flag from the store."""
        if name not in self._flags:
            raise KeyError(f"Flag '{name}' not found")
        del self._flags[name]
        self.save()

    def toggle(self, name: str) -> bool:
        """Toggle a flag's enabled state. Returns the new state."""
        flag = self._flags.get(name)
        if flag is None:
            raise KeyError(f"Flag '{name}' not found")
        flag.enabled = not flag.enabled
        self.save()
        return flag.enabled
```

### Step 2: Create `audit/changelog.py`

```python
# audit/changelog.py
from dataclasses import dataclass
from datetime import datetime

from flags.flag_definition import Flag


@dataclass
class AuditEntry:
    """A single audit log entry for a flag change."""

    timestamp: str
    flag_name: str
    action: str  # "created", "updated", "deleted", "toggled"
    changed_by: str
    old_value: str = ""
    new_value: str = ""


class AuditLog:
    """Tracks all changes to feature flags for compliance."""

    def __init__(self) -> None:
        self._entries: list[AuditEntry] = []

    def log_create(
        self, flag: Flag, user: str
    ) -> AuditEntry:
        """Log a flag creation event."""
        entry = AuditEntry(
            timestamp=datetime.now().isoformat(),
            flag_name=flag.name,
            action="created",
            changed_by=user,
            new_value=f"enabled={flag.enabled}",
        )
        self._entries.append(entry)
        return entry

    def log_toggle(
        self, flag: Flag, old_state: bool, user: str
    ) -> AuditEntry:
        """Log a flag toggle event."""
        entry = AuditEntry(
            timestamp=datetime.now().isoformat(),
            flag_name=flag.name,
            action="toggled",
            changed_by=user,
            old_value=f"enabled={old_state}",
            new_value=f"enabled={flag.enabled}",
        )
        self._entries.append(entry)
        return entry

    def log_update(
        self, flag: Flag, changes: str, user: str
    ) -> AuditEntry:
        """Log a flag update event."""
        entry = AuditEntry(
            timestamp=datetime.now().isoformat(),
            flag_name=flag.name,
            action="updated",
            changed_by=user,
            new_value=changes,
        )
        self._entries.append(entry)
        return entry

    def log_delete(
        self, flag_name: str, user: str
    ) -> AuditEntry:
        """Log a flag deletion event."""
        entry = AuditEntry(
            timestamp=datetime.now().isoformat(),
            flag_name=flag_name,
            action="deleted",
            changed_by=user,
        )
        self._entries.append(entry)
        return entry

    def get_history(self, flag_name: str) -> list[AuditEntry]:
        """Get all audit entries for a specific flag."""
        return [
            e for e in self._entries if e.flag_name == flag_name
        ]

    def get_recent(self, limit: int = 10) -> list[AuditEntry]:
        """Get the most recent audit entries."""
        return self._entries[-limit:]

    def search(
        self,
        user: str | None = None,
        action: str | None = None,
    ) -> list[AuditEntry]:
        """Search audit entries by user and/or action."""
        results = self._entries
        if user:
            results = [
                e for e in results if e.changed_by == user
            ]
        if action:
            results = [
                e for e in results if e.action == action
            ]
        return results
```

### Step 3: Stage and analyze

```bash
git add storage/ audit/

cia analyze . --format markdown --explain
```

**What you should see:** Risk rises further because `flag_store.py` imports from
`flag_definition` (serializes/deserializes `Flag` and `Variant`), and
`changelog.py` also imports `Flag`. The dependency web is growing.

```bash
# Check what tests would be affected (none yet!)
cia test . --suggest

git commit -m "feat: add FlagStore persistence and AuditLog"
```

---

## 7. Phase 5 — SDK Layer

### Step 1: Create `sdk/client.py`

This is the top-level module that ties everything together:

```python
# sdk/client.py
from flags.flag_definition import Flag, Variant
from flags.targeting import UserContext
from evaluation.engine import FlagEvaluator
from storage.flag_store import FlagStore
from audit.changelog import AuditLog


class FeatureFlagClient:
    """High-level SDK for application developers."""

    def __init__(
        self,
        store: FlagStore,
        evaluator: FlagEvaluator | None = None,
    ) -> None:
        self._store = store
        self._evaluator = evaluator or FlagEvaluator()
        self._audit = AuditLog()

    def is_enabled(
        self, flag_name: str, context: UserContext
    ) -> bool:
        """Check if a flag is enabled for the given user."""
        flag = self._store.get(flag_name)
        if flag is None:
            return False
        return self._evaluator.evaluate_bool(flag, context)

    def get_variant(
        self, flag_name: str, context: UserContext
    ) -> Variant | None:
        """Get the active variant for a flag and user."""
        flag = self._store.get(flag_name)
        if flag is None:
            return None
        return self._evaluator.evaluate(flag, context)

    def get_variant_value(
        self,
        flag_name: str,
        context: UserContext,
        default: str = "",
    ) -> str:
        """Get the variant value, or default if missing."""
        variant = self.get_variant(flag_name, context)
        return variant.value if variant else default

    def create_flag(
        self, flag: Flag, user: str = "system"
    ) -> None:
        """Create a new flag and log the action."""
        self._store.create(flag)
        self._audit.log_create(flag, user)

    def toggle_flag(
        self, flag_name: str, user: str = "system"
    ) -> bool:
        """Toggle a flag and log the action."""
        flag = self._store.get(flag_name)
        if flag is None:
            raise KeyError(f"Flag '{flag_name}' not found")
        old_state = flag.enabled
        new_state = self._store.toggle(flag_name)
        flag = self._store.get(flag_name)
        if flag:
            self._audit.log_toggle(flag, old_state, user)
        return new_state

    def get_audit_history(
        self, flag_name: str
    ) -> list[dict]:
        """Get audit trail for a flag."""
        entries = self._audit.get_history(flag_name)
        return [
            {
                "timestamp": e.timestamp,
                "action": e.action,
                "changed_by": e.changed_by,
                "old_value": e.old_value,
                "new_value": e.new_value,
            }
            for e in entries
        ]
```

### Step 2: Create `sdk/middleware.py`

```python
# sdk/middleware.py
from flags.targeting import UserContext
from sdk.client import FeatureFlagClient


class FeatureFlagMiddleware:
    """Middleware that evaluates flags for every request."""

    def __init__(
        self,
        client: FeatureFlagClient,
        flag_names: list[str],
    ) -> None:
        self._client = client
        self._flag_names = flag_names

    def get_flags_for_user(
        self, context: UserContext
    ) -> dict[str, bool]:
        """Evaluate all registered flags for a user."""
        results: dict[str, bool] = {}
        for flag_name in self._flag_names:
            results[flag_name] = self._client.is_enabled(
                flag_name, context
            )
        return results

    def get_variants_for_user(
        self, context: UserContext
    ) -> dict[str, str]:
        """Get variant values for all registered flags."""
        results: dict[str, str] = {}
        for flag_name in self._flag_names:
            results[flag_name] = self._client.get_variant_value(
                flag_name, context, default="off"
            )
        return results

    def should_show_feature(
        self, flag_name: str, context: UserContext
    ) -> bool:
        """Quick check: should this feature be visible?"""
        if flag_name not in self._flag_names:
            return False
        return self._client.is_enabled(flag_name, context)
```

### Step 3: Stage and analyze — this is where it gets interesting

```bash
git add sdk/

# Full analysis with explanation
cia analyze . --format markdown --explain
```

**What you should see:** The risk score is now significant (35–55/100) because
`client.py` imports from **5 different modules** (`flag_definition`, `targeting`,
`engine`, `flag_store`, `changelog`). CIA will report:

- **Dependents:** High — this is a hub module
- **Change size:** Moderate (two new files)
- **Test coverage:** Critical — still no tests!
- **Suggestions:** "Add tests for `sdk/client.py`", "Consider breaking large
  change into smaller commits"

```bash
# View the full dependency graph
cia graph .

git commit -m "feat: add FeatureFlagClient SDK and middleware"
```

---

## 8. Phase 6 — Tests

Now let's add tests. CIA has been warning us about missing coverage since Phase 2.

### Step 1: Create `tests/test_flags.py`

```python
# tests/test_flags.py
from flags.flag_definition import Flag, Variant
from flags.targeting import Segment, TargetingRule, UserContext


def test_flag_creation():
    flag = Flag(name="dark_mode", description="Enable dark mode")
    assert flag.name == "dark_mode"
    assert flag.enabled is False
    assert flag.is_boolean() is True
    assert flag.default_variant() is None


def test_flag_with_variants():
    variants = [
        Variant(name="control", value="old_ui", weight=50),
        Variant(name="treatment", value="new_ui", weight=50),
    ]
    flag = Flag(
        name="redesign",
        description="UI redesign",
        variants=variants,
    )
    assert not flag.is_boolean()
    assert flag.default_variant().name == "control"


def test_user_context():
    ctx = UserContext(
        user_id="user_123", email="test@example.com", plan="pro"
    )
    assert ctx.user_id == "user_123"
    assert ctx.plan == "pro"


def test_segment_matches():
    segment = Segment(
        name="pro_users",
        conditions=[
            {
                "attribute": "plan",
                "operator": "equals",
                "value": "pro",
            }
        ],
    )
    pro_user = UserContext(user_id="u1", plan="pro")
    free_user = UserContext(user_id="u2", plan="free")
    assert segment.matches(pro_user) is True
    assert segment.matches(free_user) is False


def test_segment_not_equals():
    segment = Segment(
        name="non_free",
        conditions=[
            {
                "attribute": "plan",
                "operator": "not_equals",
                "value": "free",
            }
        ],
    )
    pro_user = UserContext(user_id="u1", plan="pro")
    free_user = UserContext(user_id="u2", plan="free")
    assert segment.matches(pro_user) is True
    assert segment.matches(free_user) is False


def test_segment_contains():
    segment = Segment(
        name="gmail_users",
        conditions=[
            {
                "attribute": "email",
                "operator": "contains",
                "value": "gmail",
            }
        ],
    )
    gmail = UserContext(user_id="u1", email="user@gmail.com")
    other = UserContext(user_id="u2", email="user@outlook.com")
    assert segment.matches(gmail) is True
    assert segment.matches(other) is False


def test_targeting_rule():
    segment = Segment(name="beta", conditions=[])
    rule = TargetingRule(
        segment=segment, variant_name="treatment", priority=10
    )
    assert rule.priority == 10
    assert rule.variant_name == "treatment"
```

### Step 2: Create `tests/test_evaluation.py`

```python
# tests/test_evaluation.py
from flags.flag_definition import Flag, Variant
from flags.targeting import Segment, TargetingRule, UserContext
from evaluation.engine import FlagEvaluator
from evaluation.percentage_rollout import PercentageRollout


def test_evaluate_disabled_flag():
    evaluator = FlagEvaluator()
    flag = Flag(name="test", description="Test", enabled=False)
    ctx = UserContext(user_id="user_1")
    assert evaluator.evaluate(flag, ctx) is None


def test_evaluate_boolean_flag():
    evaluator = FlagEvaluator()
    flag = Flag(name="test", description="Test", enabled=True)
    ctx = UserContext(user_id="user_1")
    assert evaluator.evaluate_bool(flag, ctx) is True


def test_evaluate_with_targeting_rule():
    evaluator = FlagEvaluator()
    variants = [
        Variant(name="control", value="old"),
        Variant(name="treatment", value="new"),
    ]
    flag = Flag(
        name="redesign",
        description="Redesign",
        enabled=True,
        variants=variants,
    )

    segment = Segment(
        name="pro_users",
        conditions=[
            {
                "attribute": "plan",
                "operator": "equals",
                "value": "pro",
            }
        ],
    )
    rule = TargetingRule(segment=segment, variant_name="treatment")
    evaluator.add_rule("redesign", rule)

    pro_user = UserContext(user_id="u1", plan="pro")
    result = evaluator.evaluate(flag, pro_user)
    assert result is not None
    assert result.name == "treatment"


def test_evaluate_falls_back_to_rollout():
    evaluator = FlagEvaluator()
    variants = [
        Variant(name="control", value="old", weight=50),
        Variant(name="treatment", value="new", weight=50),
    ]
    flag = Flag(
        name="experiment",
        description="AB test",
        enabled=True,
        variants=variants,
    )
    ctx = UserContext(user_id="user_42")
    result = evaluator.evaluate(flag, ctx)
    assert result is not None
    assert result.name in ("control", "treatment")


def test_percentage_rollout_consistent():
    rollout = PercentageRollout()
    variants = [
        Variant(name="a", value="1", weight=50),
        Variant(name="b", value="2", weight=50),
    ]
    result1 = rollout.assign_variant("flag", "user_1", variants)
    result2 = rollout.assign_variant("flag", "user_1", variants)
    assert result1.name == result2.name


def test_percentage_rollout_distribution():
    rollout = PercentageRollout()
    variants = [
        Variant(name="a", value="1", weight=50),
        Variant(name="b", value="2", weight=50),
    ]
    counts = {"a": 0, "b": 0}
    for i in range(1000):
        result = rollout.assign_variant(
            "test_flag", f"user_{i}", variants
        )
        counts[result.name] += 1
    assert counts["a"] > 300
    assert counts["b"] > 300


def test_get_percentage():
    rollout = PercentageRollout()
    pct = rollout.get_percentage("flag", "user_1")
    assert 0.0 <= pct <= 100.0
```

### Step 3: Create `tests/test_storage.py`

```python
# tests/test_storage.py
from flags.flag_definition import Flag, Variant
from storage.flag_store import FlagStore


def test_create_and_get(tmp_path):
    store = FlagStore(str(tmp_path / "flags.json"))
    flag = Flag(name="dark_mode", description="Dark mode toggle")
    store.create(flag)
    result = store.get("dark_mode")
    assert result is not None
    assert result.name == "dark_mode"


def test_list_flags(tmp_path):
    store = FlagStore(str(tmp_path / "flags.json"))
    store.create(Flag(name="flag_a", description="A"))
    store.create(Flag(name="flag_b", description="B"))
    flags = store.list_flags()
    assert len(flags) == 2


def test_toggle(tmp_path):
    store = FlagStore(str(tmp_path / "flags.json"))
    store.create(
        Flag(name="test", description="Test", enabled=False)
    )
    new_state = store.toggle("test")
    assert new_state is True
    new_state = store.toggle("test")
    assert new_state is False


def test_update(tmp_path):
    store = FlagStore(str(tmp_path / "flags.json"))
    store.create(Flag(name="test", description="Original"))
    store.update(Flag(name="test", description="Updated"))
    flag = store.get("test")
    assert flag.description == "Updated"


def test_delete(tmp_path):
    store = FlagStore(str(tmp_path / "flags.json"))
    store.create(Flag(name="test", description="Test"))
    store.delete("test")
    assert store.get("test") is None


def test_persistence(tmp_path):
    path = str(tmp_path / "flags.json")
    store1 = FlagStore(path)
    store1.create(
        Flag(
            name="persistent",
            description="Survives reload",
            enabled=True,
            variants=[Variant(name="v1", value="val1")],
        )
    )
    store2 = FlagStore(path)
    flag = store2.get("persistent")
    assert flag is not None
    assert flag.enabled is True
    assert len(flag.variants) == 1
```

### Step 4: Create `tests/test_audit.py`

```python
# tests/test_audit.py
from flags.flag_definition import Flag
from audit.changelog import AuditLog


def test_log_create():
    log = AuditLog()
    flag = Flag(name="test", description="Test", enabled=True)
    entry = log.log_create(flag, "admin")
    assert entry.action == "created"
    assert entry.changed_by == "admin"
    assert "enabled=True" in entry.new_value


def test_log_toggle():
    log = AuditLog()
    flag = Flag(name="test", description="Test", enabled=False)
    entry = log.log_toggle(flag, old_state=True, user="admin")
    assert entry.action == "toggled"
    assert "enabled=True" in entry.old_value
    assert "enabled=False" in entry.new_value


def test_get_history():
    log = AuditLog()
    flag = Flag(name="test", description="Test")
    log.log_create(flag, "admin")
    log.log_toggle(flag, old_state=False, user="admin")
    history = log.get_history("test")
    assert len(history) == 2


def test_search_by_user():
    log = AuditLog()
    flag = Flag(name="test", description="Test")
    log.log_create(flag, "alice")
    log.log_toggle(flag, old_state=False, user="bob")
    assert len(log.search(user="alice")) == 1
    assert len(log.search(user="bob")) == 1


def test_get_recent():
    log = AuditLog()
    for i in range(20):
        flag = Flag(name=f"flag_{i}", description="Test")
        log.log_create(flag, "admin")
    recent = log.get_recent(limit=5)
    assert len(recent) == 5
```

### Step 5: Create `tests/test_sdk.py`

```python
# tests/test_sdk.py
from flags.flag_definition import Flag, Variant
from flags.targeting import UserContext
from storage.flag_store import FlagStore
from sdk.client import FeatureFlagClient
from sdk.middleware import FeatureFlagMiddleware


def test_client_is_enabled(tmp_path):
    store = FlagStore(str(tmp_path / "flags.json"))
    store.create(
        Flag(name="dark_mode", description="Dark", enabled=True)
    )
    client = FeatureFlagClient(store)
    ctx = UserContext(user_id="user_1")
    assert client.is_enabled("dark_mode", ctx) is True


def test_client_disabled_flag(tmp_path):
    store = FlagStore(str(tmp_path / "flags.json"))
    store.create(
        Flag(name="beta", description="Beta", enabled=False)
    )
    client = FeatureFlagClient(store)
    ctx = UserContext(user_id="user_1")
    assert client.is_enabled("beta", ctx) is False


def test_client_missing_flag(tmp_path):
    store = FlagStore(str(tmp_path / "flags.json"))
    client = FeatureFlagClient(store)
    ctx = UserContext(user_id="user_1")
    assert client.is_enabled("nonexistent", ctx) is False


def test_client_get_variant(tmp_path):
    store = FlagStore(str(tmp_path / "flags.json"))
    variants = [
        Variant(name="control", value="old_ui"),
        Variant(name="treatment", value="new_ui"),
    ]
    store.create(
        Flag(
            name="redesign",
            description="Redesign",
            enabled=True,
            variants=variants,
        )
    )
    client = FeatureFlagClient(store)
    ctx = UserContext(user_id="user_1")
    variant = client.get_variant("redesign", ctx)
    assert variant is not None
    assert variant.name in ("control", "treatment")


def test_client_toggle(tmp_path):
    store = FlagStore(str(tmp_path / "flags.json"))
    store.create(
        Flag(name="test", description="Test", enabled=False)
    )
    client = FeatureFlagClient(store)
    new_state = client.toggle_flag("test", user="admin")
    assert new_state is True


def test_client_audit_history(tmp_path):
    store = FlagStore(str(tmp_path / "flags.json"))
    client = FeatureFlagClient(store)
    flag = Flag(name="test", description="Test")
    client.create_flag(flag, user="admin")
    history = client.get_audit_history("test")
    assert len(history) == 1
    assert history[0]["action"] == "created"


def test_middleware_get_flags(tmp_path):
    store = FlagStore(str(tmp_path / "flags.json"))
    store.create(
        Flag(name="dark_mode", description="Dark", enabled=True)
    )
    store.create(
        Flag(name="beta", description="Beta", enabled=False)
    )
    client = FeatureFlagClient(store)
    middleware = FeatureFlagMiddleware(
        client, ["dark_mode", "beta"]
    )
    ctx = UserContext(user_id="user_1")
    flags = middleware.get_flags_for_user(ctx)
    assert flags["dark_mode"] is True
    assert flags["beta"] is False


def test_middleware_should_show_feature(tmp_path):
    store = FlagStore(str(tmp_path / "flags.json"))
    store.create(
        Flag(name="dark_mode", description="Dark", enabled=True)
    )
    client = FeatureFlagClient(store)
    middleware = FeatureFlagMiddleware(client, ["dark_mode"])
    ctx = UserContext(user_id="user_1")
    assert middleware.should_show_feature("dark_mode", ctx) is True
    assert middleware.should_show_feature("unknown", ctx) is False
```

### Step 6: Stage, analyze, and commit

```bash
git add tests/

# Now CIA can see we've added tests — risk should drop
cia analyze . --format markdown --explain

# See affected tests
cia test .

git commit -m "test: add comprehensive test suite for all modules"
```

**What you should see:** The risk score drops noticeably because CIA now detects
test coverage for the changed modules. The "Lack of test coverage" factor falls
from high to low.

---

## 9. Phase 7 — CIA Configuration & Hooks

### Step 1: Configure CIA

```bash
# View the current configuration
cia config .

# Set the default output format to markdown
cia config . --set format=markdown

# Set a risk threshold — anything above 60 is a warning
cia config . --set threshold=60

# Verify
cia config . --get format
cia config . --get threshold
```

### Step 2: Install the pre-commit hook

```bash
# Install a pre-commit hook that blocks commits with HIGH risk
cia install-hook . --block-on high

# Verify it's installed
cat .git/hooks/pre-commit
```

Now CIA will automatically analyze every commit and block it if the risk score
reaches "high" level (51+).

### Step 3: Commit the configuration

```bash
git add .ciarc
git commit -m "chore: add CIA configuration"
```

---

Now the project is fully built. Time for the fun part — **real developer
mistakes** and how CIA catches them.

---

## 10. Scenario 1 — Dangerous Field Rename

### The mistake

A developer decides to rename `Flag.enabled` to `Flag.is_active` for "better
readability." This seems like a harmless refactor, but the field is used in
**every module** in the project.

### Step 1: Make the change

Edit `flags/flag_definition.py` — change `enabled` to `is_active`:

```python
@dataclass
class Flag:
    """A feature flag definition."""

    name: str
    description: str
    is_active: bool = False          # <-- RENAMED from 'enabled'
    variants: list[Variant] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
```

### Step 2: Stage and analyze

```bash
git add flags/flag_definition.py

cia analyze . --format markdown --explain
```

### What CIA reveals

**Risk: 72/100 (HIGH)**

CIA shows the blast radius of this "simple" rename:

```
Affected Modules:
  - flags/flag_definition.py (changed)
  - evaluation/engine.py         ← reads flag.enabled in evaluate()
  - storage/flag_store.py        ← reads/writes flag.enabled in _load() and save()
  - audit/changelog.py           ← formats f"enabled={flag.enabled}"
  - sdk/client.py                ← calls flag.enabled in toggle_flag()
  - sdk/middleware.py             ← transitively via client
  - tests/test_flags.py          ← asserts flag.enabled
  - tests/test_evaluation.py     ← creates flags with enabled=True
  - tests/test_storage.py        ← creates flags with enabled=True
  - tests/test_sdk.py            ← creates flags with enabled=True
  - tests/test_audit.py          ← creates flags with enabled=True

Risk Breakdown:
  Downstream dependents: 85/100
  Test coverage risk:    45/100
  Complexity:            30/100

Suggestions:
  - This change affects 6+ downstream modules — consider a phased rename
  - Update all references before committing
  - Run the full test suite: pytest
```

### Step 3: Try to commit — the hook blocks it!

```bash
git commit -m "refactor: rename enabled to is_active"
```

Output:

```
CIA Pre-Commit Hook — Change Impact Analysis
Risk Score: 72/100 (HIGH)
❌ Commit blocked: risk level HIGH exceeds threshold HIGH
Run 'cia analyze . --explain' for details.
```

### The lesson

Without CIA, this rename would have been committed, pushed, and broken every
other module at runtime. CIA caught it **before** it ever left the developer's
machine.

### Step 4: Clean up

```bash
# Revert the change
git checkout -- flags/flag_definition.py
```

---

## 11. Scenario 2 — Silent Format Change

### The mistake

A developer changes the targeting condition format from flat dicts to nested
objects, thinking only `targeting.py` needs updating.

### Step 1: Make the change

Edit `flags/targeting.py` — change the `matches()` method to expect nested
conditions:

```python
    def matches(self, context: UserContext) -> bool:
        """Check if a user context matches all conditions."""
        for condition in self.conditions:
            # CHANGED: now expects condition["rule"]["attribute"]
            # instead of condition["attribute"]
            rule = condition.get("rule", condition)
            attr = rule.get("attribute", "")
            operator = rule.get("operator", "equals")
            value = rule.get("value", "")
```

### Step 2: Stage and analyze

```bash
git add flags/targeting.py
cia analyze . --format markdown --explain
```

### What CIA reveals

**Risk: 48/100 (MEDIUM)**

```
Affected Modules:
  - flags/targeting.py        (changed)
  - evaluation/engine.py      ← calls segment.matches()
  - sdk/client.py             ← transitively via engine
  - sdk/middleware.py          ← transitively via client
  - tests/test_flags.py       ← constructs Segment with old format
  - tests/test_evaluation.py  ← constructs Segment with old format

Suggestions:
  - 4 downstream modules depend on the changed interface
  - Existing tests use the old condition format — they will fail silently
    or pass incorrectly
```

### Step 3: See which tests are affected

```bash
cia test . --affected-only
```

Output:

```json
{
  "affected_tests": [
    "tests/test_flags.py",
    "tests/test_evaluation.py"
  ],
  "pytest_expression": "tests/test_flags.py or tests/test_evaluation.py"
}
```

### The lesson

The format change is backwards-compatible in the code (the `get("rule",
condition)` fallback means old-format dicts still work), but CIA correctly
identifies that the **test data** and **downstream callers** construct conditions
in the old format. Any new code would use the new format, creating an
inconsistency that's hard to debug later.

### Step 4: Clean up

```bash
git checkout -- flags/targeting.py
```

---

## 12. Scenario 3 — Algorithm Swap with Hidden Blast Radius

### The mistake

A developer switches the rollout hash from MD5 to SHA256 for "better
distribution." This is a one-line change. What could go wrong?

### Step 1: Make the change

Edit `evaluation/percentage_rollout.py`:

```python
    def assign_variant(
        self, flag_name: str, user_id: str, variants: list[Variant]
    ) -> Variant:
        hash_key = f"{flag_name}:{user_id}"
        # CHANGED: md5 → sha256
        hash_value = int(
            hashlib.sha256(hash_key.encode()).hexdigest(), 16
        )
```

Also change `get_percentage()` the same way.

### Step 2: Stage and analyze

```bash
git add evaluation/percentage_rollout.py

cia analyze . --format json --threshold 40
echo $?
```

### What CIA reveals

**Risk: 45/100 (MEDIUM) — threshold exceeded!**

Exit code: `1` (threshold exceeded)

```json
{
  "summary": {
    "risk_score": 45,
    "risk_level": "MEDIUM"
  },
  "affected_modules": [
    "evaluation/percentage_rollout.py",
    "evaluation/engine.py",
    "sdk/client.py",
    "sdk/middleware.py"
  ],
  "explanations": [
    "Number of downstream dependents: 62/100",
    "Size of the change (lines): 15/100"
  ],
  "suggestions": [
    "This change affects the rollout hash — all existing users will be reassigned to different variants",
    "Consider a migration strategy for in-flight experiments"
  ]
}
```

### The lesson

Changing a hash function doesn't break any API. All tests still pass. But **every
user gets reassigned to a different variant**, silently disrupting every running
A/B test. This is the kind of bug that costs companies millions because it
corrupts experiment results. CIA flags the blast radius even though the code
"works."

### Step 3: Clean up

```bash
git checkout -- evaluation/percentage_rollout.py
```

---

## 13. Scenario 4 — New Feature Without Tests

### The mistake

A developer adds a batch toggle feature to the store but forgets to write tests.

### Step 1: Add the new method

Edit `storage/flag_store.py` — add this method at the end of the class:

```python
    def batch_toggle(self, names: list[str]) -> dict[str, bool]:
        """Toggle multiple flags at once. Returns new states."""
        results = {}
        for name in names:
            results[name] = self.toggle(name)
        return results
```

### Step 2: Stage and analyze

```bash
git add storage/flag_store.py

# Ask CIA specifically about test coverage
cia test . --suggest
```

### What CIA reveals

```json
{
  "suggestions": [
    {
      "entity": "storage/flag_store.py::FlagStore.batch_toggle",
      "reason": "New method with no test coverage",
      "suggested_file": "tests/test_storage.py"
    }
  ]
}
```

CIA tells you exactly:
- **Which function** is untested (`batch_toggle`)
- **Where** to add the test (`tests/test_storage.py`)

### Step 3: Follow CIA's suggestion — write the missing test

Add to `tests/test_storage.py`:

```python
def test_batch_toggle(tmp_path):
    store = FlagStore(str(tmp_path / "flags.json"))
    store.create(Flag(name="a", description="A", enabled=False))
    store.create(Flag(name="b", description="B", enabled=True))
    results = store.batch_toggle(["a", "b"])
    assert results["a"] is True   # was False, now True
    assert results["b"] is False  # was True, now False
```

```bash
git add storage/flag_store.py tests/test_storage.py

# Re-analyze — risk drops because we added the test
cia analyze . --format markdown --explain

git commit -m "feat: add batch_toggle with tests"
```

### The lesson

CIA acts as a code reviewer that never forgets to ask "where's the test?"

---

## 14. Scenario 5 — Pre-Commit Hook Blocks a Risky Commit

### The scenario

A developer makes a large, multi-file change all at once: modifying the `Flag`
dataclass, the store serialization, and the engine evaluation — without updating
tests.

### Step 1: Make multiple risky changes at once

Edit `flags/flag_definition.py` — add a new required field:

```python
@dataclass
class Flag:
    name: str
    description: str
    enabled: bool = False
    version: int = 1                  # <-- NEW FIELD
    variants: list[Variant] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
```

Edit `storage/flag_store.py` — add version to save but forget to load:

```python
    def save(self) -> None:
        data = {}
        for name, flag in self._flags.items():
            data[name] = {
                "description": flag.description,
                "enabled": flag.enabled,
                "version": flag.version,        # <-- Added to save
                # ... rest unchanged
```

Edit `evaluation/engine.py` — add version check:

```python
    def evaluate(self, flag: Flag, context: UserContext) -> Variant | None:
        if not flag.enabled:
            return None
        if flag.version < 1:                     # <-- NEW CHECK
            return None
```

### Step 2: Try to commit

```bash
git add flags/flag_definition.py storage/flag_store.py evaluation/engine.py

git commit -m "feat: add flag versioning"
```

### What happens

The pre-commit hook runs CIA automatically:

```
CIA Pre-Commit Hook — Change Impact Analysis

Risk Score: 68/100 (HIGH)

Changed:
  - flags/flag_definition.py
  - storage/flag_store.py
  - evaluation/engine.py

Affected (downstream):
  - audit/changelog.py
  - sdk/client.py
  - sdk/middleware.py
  - tests/test_flags.py
  - tests/test_evaluation.py
  - tests/test_storage.py
  - tests/test_sdk.py
  - tests/test_audit.py

Risk Breakdown:
  Downstream dependents:  78/100  ← flag_definition affects everything
  Change size:            55/100  ← 3 files modified
  Test coverage:          65/100  ← no tests updated
  Complexity:             40/100  ← conditional logic added

❌ Commit blocked: risk level HIGH exceeds threshold HIGH

Suggestions:
  1. Update tests for the new 'version' field
  2. Add version handling to _load() in flag_store.py
  3. Consider splitting into smaller commits:
     - One for the model change
     - One for the store update
     - One for the engine logic

Run 'cia analyze . --explain' for full details.
```

### The lesson

The hook caught **three problems**:
1. Tests aren't updated for the new field
2. `_load()` doesn't deserialize `version` (data loss on reload)
3. The change is too large — should be split into smaller, reviewable commits

### Step 3: Clean up

```bash
git checkout -- flags/flag_definition.py storage/flag_store.py evaluation/engine.py
```

---

## 15. Scenario 6 — Targeted Test Runs

After a long day of coding, you want to run only the tests affected by your
changes, not the entire suite.

### Step 1: Make a small change

Edit `audit/changelog.py` — add a new method:

```python
    def count_by_action(self) -> dict[str, int]:
        """Count entries grouped by action type."""
        counts: dict[str, int] = {}
        for entry in self._entries:
            counts[entry.action] = counts.get(entry.action, 0) + 1
        return counts
```

### Step 2: Ask CIA which tests to run

```bash
git add audit/changelog.py

cia test . --affected-only
```

Output:

```json
{
  "affected_tests": [
    "tests/test_audit.py",
    "tests/test_sdk.py"
  ],
  "pytest_expression": "tests/test_audit.py or tests/test_sdk.py"
}
```

### Step 3: Run only the affected tests

```bash
pytest tests/test_audit.py tests/test_sdk.py -v
```

Instead of running 30+ tests across 5 files, you run only the 11 tests that
could possibly be affected. CIA saved you time and focused your attention.

### Step 4: Get test suggestions

```bash
cia test . --suggest
```

```json
{
  "suggestions": [
    {
      "entity": "audit/changelog.py::AuditLog.count_by_action",
      "reason": "New method with no test coverage",
      "suggested_file": "tests/test_audit.py"
    }
  ]
}
```

### Step 5: Clean up

```bash
git checkout -- audit/changelog.py
```

---

## 16. CIA Command Reference

Every command used in this tutorial, with the context in which it was used:

| Command | When to use | Example |
|---------|-------------|---------|
| `cia init .` | Once, at project setup | Creates `.ciarc` config file |
| `cia analyze .` | Before every commit | `cia analyze . --format markdown --explain` |
| `cia analyze . --format json` | In CI pipelines | Machine-readable output |
| `cia analyze . --threshold 60` | To enforce risk limits | Exit code 1 if exceeded |
| `cia test . --affected-only` | To run targeted tests | Shows only affected test files |
| `cia test . --suggest` | To find missing tests | Suggests where to add tests |
| `cia graph .` | To visualize dependencies | Shows module dependency graph |
| `cia config .` | To view configuration | Shows effective `.ciarc` settings |
| `cia config . --set key=val` | To change settings | `cia config . --set format=markdown` |
| `cia config . --get key` | To read a setting | `cia config . --get threshold` |
| `cia install-hook .` | Once, to enable auto-check | `cia install-hook . --block-on high` |
| `cia uninstall-hook .` | To remove the hook | Removes pre-commit hook |
| `cia version` | To check installation | Shows version and platform |

### Exit codes

| Code | Meaning |
|------|---------|
| `0` | Success — risk is within threshold |
| `1` | Risk threshold exceeded |
| `2` | Runtime error (not a git repo, invalid config, etc.) |

### Output formats

```bash
# JSON — for CI/CD pipelines and scripts
cia analyze . --format json

# Markdown — for PR comments and terminal reading
cia analyze . --format markdown

# HTML — for interactive reports with D3.js graph
cia analyze . --format html --output report.html

# All formats at once
cia analyze . --format all --output report
# Creates: report.json, report.md, report.html
```

---

## Summary

In this tutorial you:

1. **Built a real project** (Feature Flag System) from scratch with 8 modules
2. **Used CIA at every commit** to track growing risk and dependencies
3. **Caught 5 realistic developer mistakes** before they reached production:
   - Dangerous field rename affecting 10+ files
   - Silent format change that passes tests but creates inconsistency
   - Hash algorithm swap that reassigns all A/B test users
   - New feature shipped without tests
   - Large multi-file commit that skips critical updates
4. **Ran targeted tests** using CIA's impact prediction
5. **Configured a pre-commit hook** that automatically blocks risky commits

CIA integrates into your workflow without disruption — it analyzes what Git
already tracks and gives you actionable feedback in seconds.

For more details, see the [README](../README.md) and [API Reference](api.md).
