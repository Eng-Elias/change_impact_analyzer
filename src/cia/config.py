"""Configuration management for Change Impact Analyzer.

Supports loading from:
1. ``.ciarc`` / ``.ciarc.toml`` (TOML — default)
2. ``.ciarc.json`` (JSON)
3. ``.ciarc.yaml`` / ``.ciarc.yml`` (YAML, requires PyYAML)
4. Environment variables prefixed with ``CIA_`` (override file values)
5. CLI arguments (override everything)

Resolution order (last wins):
  defaults → config file → env vars → CLI arguments
"""

from __future__ import annotations

import json
import os
import tomllib
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_CONFIG: dict[str, Any] = {
    "format": "json",
    "threshold": None,
    "explain": False,
    "unstaged": False,
    "block_on": "none",
    "verbose": False,
    "output": None,
    "test_only": False,
}

_TOML_FILES = (".ciarc", ".ciarc.toml")
_JSON_FILES = (".ciarc.json",)
_YAML_FILES = (".ciarc.yaml", ".ciarc.yml")

_ALL_RC_FILES = (*_TOML_FILES, *_JSON_FILES, *_YAML_FILES)

# The TOML template written by ``cia init``.
DEFAULT_CIARC_CONTENT = """\
# Change Impact Analyzer configuration
# See: https://github.com/change-impact-analyzer/change-impact-analyzer

[analysis]
format = "json"
# threshold = 75
explain = false
unstaged = false
test_only = false

[hook]
block_on = "none"

[output]
# path = "reports/impact"
"""


# ---------------------------------------------------------------------------
# Loading helpers
# ---------------------------------------------------------------------------


def _load_toml(path: Path) -> dict[str, Any]:
    with open(path, "rb") as fh:
        return tomllib.load(fh)


def _load_json(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    return json.loads(text)  # type: ignore[no-any-return]


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError as exc:
        raise ImportError(
            "PyYAML is required to read .ciarc.yaml files. "
            "Install it with: pip install pyyaml"
        ) from exc
    text = path.read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    return data if isinstance(data, dict) else {}


def _flatten(d: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    """Flatten a nested dict into dot-separated keys."""
    items: dict[str, Any] = {}
    for key, val in d.items():
        full = f"{prefix}{key}" if not prefix else f"{prefix}.{key}"
        if isinstance(val, dict):
            items.update(_flatten(val, full))
        else:
            items[full] = val
    return items


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def find_config_file(start: Path | None = None) -> Path | None:
    """Walk up from *start* (default: cwd) looking for a ``.ciarc*`` file.

    Returns the first match or ``None``.
    """
    directory = Path(start) if start else Path.cwd()
    directory = directory.resolve()

    for _ in range(50):  # safety limit
        for name in _ALL_RC_FILES:
            candidate = directory / name
            if candidate.is_file():
                return candidate
        parent = directory.parent
        if parent == directory:
            break
        directory = parent
    return None


def load_config_file(path: Path) -> dict[str, Any]:
    """Load and return the *flat* config dict from *path*."""
    name = path.name.lower()
    if name.endswith((".yaml", ".yml")):
        raw = _load_yaml(path)
    elif name.endswith(".json"):
        raw = _load_json(path)
    else:
        raw = _load_toml(path)
    return _flatten(raw)


def load_env_overrides() -> dict[str, Any]:
    """Return config values derived from ``CIA_*`` environment variables.

    ``CIA_FORMAT=html`` → ``{"format": "html"}``
    ``CIA_ANALYSIS_THRESHOLD=80`` → ``{"analysis.threshold": 80}``
    """
    overrides: dict[str, Any] = {}
    prefix = "CIA_"
    for key, val in os.environ.items():
        if not key.startswith(prefix):
            continue
        config_key = key[len(prefix):].lower().replace("_", ".")
        # Attempt numeric conversion
        if val.isdigit():
            overrides[config_key] = int(val)
        elif val.lower() in ("true", "false"):
            overrides[config_key] = val.lower() == "true"
        elif val.lower() == "none":
            overrides[config_key] = None
        else:
            overrides[config_key] = val
        # Also store the un-dotted version for simple keys
        simple_key = key[len(prefix):].lower()
        if "." not in simple_key and simple_key != config_key:
            pass  # only one form exists
        # Store short form (last segment) as well for convenience
        short = config_key.rsplit(".", maxsplit=1)[-1]
        if short not in overrides:
            overrides[short] = overrides[config_key]
    return overrides


def load_config(start: Path | None = None) -> dict[str, Any]:
    """Load the fully-resolved config (defaults → file → env).

    Parameters
    ----------
    start:
        Directory from which to search upward for a ``.ciarc`` file.

    Returns
    -------
    dict:
        Flat configuration dictionary.
    """
    cfg = dict(DEFAULT_CONFIG)

    rc = find_config_file(start)
    if rc is not None:
        file_cfg = load_config_file(rc)
        # Map nested keys to simple keys
        for k, v in file_cfg.items():
            short = k.rsplit(".", maxsplit=1)[-1]
            if short in cfg:
                cfg[short] = v
            cfg[k] = v

    env = load_env_overrides()
    for k, v in env.items():
        short = k.rsplit(".", maxsplit=1)[-1]
        if short in cfg:
            cfg[short] = v
        cfg[k] = v

    return cfg


def get_config_value(cfg: dict[str, Any], key: str) -> Any:
    """Retrieve *key* from *cfg*, searching both full and short forms."""
    if key in cfg:
        return cfg[key]
    # Try matching as short key
    for k, v in cfg.items():
        if k.rsplit(".", maxsplit=1)[-1] == key:
            return v
    return None


def set_config_value(path: Path, key: str, value: str) -> None:
    """Set *key* = *value* in a TOML ``.ciarc`` file.

    Creates or updates the file.  Only simple ``section.key = value``
    pairs are supported for TOML files.
    """
    # Parse the value
    parsed: Any
    if value.isdigit():
        parsed = int(value)
    elif value.lower() in ("true", "false"):
        parsed = value.lower() == "true"
    elif value.lower() == "none":
        parsed = "none"
    else:
        parsed = value

    # Load existing
    if path.exists():
        raw = _load_toml(path) if not path.name.endswith(".json") else _load_json(path)
    else:
        raw = {}

    # Split key into section.key
    parts = key.split(".", maxsplit=1)
    if len(parts) == 2:
        section, subkey = parts
        raw.setdefault(section, {})[subkey] = parsed
    else:
        raw[key] = parsed

    # Write back
    if path.name.endswith(".json"):
        path.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")
    else:
        _write_toml(path, raw)


def _write_toml(path: Path, data: dict[str, Any]) -> None:
    """Write a simple TOML file from a (possibly nested) dict."""
    lines: list[str] = []
    # Top-level scalars first
    for k, v in data.items():
        if not isinstance(v, dict):
            lines.append(f"{k} = {_toml_value(v)}")
    # Sections
    for k, v in data.items():
        if isinstance(v, dict):
            lines.append(f"\n[{k}]")
            for sk, sv in v.items():
                lines.append(f"{sk} = {_toml_value(sv)}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _toml_value(v: Any) -> str:
    """Format a Python value as a TOML literal."""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return str(v)
    return f'"{v}"'
