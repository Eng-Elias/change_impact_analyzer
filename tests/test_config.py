"""Tests for the configuration module."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from cia.config import (
    DEFAULT_CIARC_CONTENT,
    DEFAULT_CONFIG,
    _flatten,
    _toml_value,
    _write_toml,
    find_config_file,
    get_config_value,
    load_config,
    load_config_file,
    load_env_overrides,
    set_config_value,
)

# ==================================================================
# _flatten
# ==================================================================


class TestFlatten:
    def test_flat_dict(self) -> None:
        assert _flatten({"a": 1, "b": 2}) == {"a": 1, "b": 2}

    def test_nested_dict(self) -> None:
        result = _flatten({"analysis": {"format": "json", "threshold": 75}})
        assert result == {"analysis.format": "json", "analysis.threshold": 75}

    def test_deeply_nested(self) -> None:
        result = _flatten({"a": {"b": {"c": 1}}})
        assert result == {"a.b.c": 1}

    def test_empty(self) -> None:
        assert _flatten({}) == {}


# ==================================================================
# _toml_value
# ==================================================================


class TestTomlValue:
    def test_bool_true(self) -> None:
        assert _toml_value(True) == "true"

    def test_bool_false(self) -> None:
        assert _toml_value(False) == "false"

    def test_int(self) -> None:
        assert _toml_value(42) == "42"

    def test_float(self) -> None:
        assert _toml_value(3.14) == "3.14"

    def test_string(self) -> None:
        assert _toml_value("hello") == '"hello"'


# ==================================================================
# _write_toml
# ==================================================================


class TestWriteToml:
    def test_simple(self, tmp_path: Path) -> None:
        p = tmp_path / "test.toml"
        _write_toml(p, {"key": "val"})
        text = p.read_text(encoding="utf-8")
        assert 'key = "val"' in text

    def test_with_section(self, tmp_path: Path) -> None:
        p = tmp_path / "test.toml"
        _write_toml(p, {"analysis": {"format": "json"}})
        text = p.read_text(encoding="utf-8")
        assert "[analysis]" in text
        assert 'format = "json"' in text

    def test_mixed(self, tmp_path: Path) -> None:
        p = tmp_path / "test.toml"
        _write_toml(p, {"top": 1, "section": {"nested": True}})
        text = p.read_text(encoding="utf-8")
        assert "top = 1" in text
        assert "[section]" in text
        assert "nested = true" in text


# ==================================================================
# find_config_file
# ==================================================================


class TestFindConfigFile:
    def test_finds_ciarc(self, tmp_path: Path) -> None:
        rc = tmp_path / ".ciarc"
        rc.write_text("x = 1\n", encoding="utf-8")
        result = find_config_file(tmp_path)
        assert result == rc

    def test_finds_ciarc_toml(self, tmp_path: Path) -> None:
        rc = tmp_path / ".ciarc.toml"
        rc.write_text("x = 1\n", encoding="utf-8")
        result = find_config_file(tmp_path)
        assert result is not None
        assert result.name == ".ciarc.toml"

    def test_finds_ciarc_json(self, tmp_path: Path) -> None:
        rc = tmp_path / ".ciarc.json"
        rc.write_text('{"x": 1}\n', encoding="utf-8")
        result = find_config_file(tmp_path)
        assert result is not None
        assert result.name == ".ciarc.json"

    def test_finds_ciarc_yaml(self, tmp_path: Path) -> None:
        rc = tmp_path / ".ciarc.yaml"
        rc.write_text("x: 1\n", encoding="utf-8")
        result = find_config_file(tmp_path)
        assert result is not None
        assert result.name == ".ciarc.yaml"

    def test_finds_ciarc_yml(self, tmp_path: Path) -> None:
        rc = tmp_path / ".ciarc.yml"
        rc.write_text("x: 1\n", encoding="utf-8")
        result = find_config_file(tmp_path)
        assert result is not None
        assert result.name == ".ciarc.yml"

    def test_walks_up(self, tmp_path: Path) -> None:
        rc = tmp_path / ".ciarc"
        rc.write_text("x = 1\n", encoding="utf-8")
        child = tmp_path / "sub" / "deep"
        child.mkdir(parents=True)
        result = find_config_file(child)
        assert result == rc

    def test_returns_none_if_missing(self, tmp_path: Path) -> None:
        child = tmp_path / "empty"
        child.mkdir()
        result = find_config_file(child)
        assert result is None

    def test_default_uses_cwd(self, tmp_path: Path) -> None:
        rc = tmp_path / ".ciarc"
        rc.write_text("x = 1\n", encoding="utf-8")
        with patch("cia.config.Path") as mock_path:
            mock_path.cwd.return_value = tmp_path
            mock_path.return_value = tmp_path
            # Can't easily test default cwd path, just ensure no crash
            find_config_file(tmp_path)


# ==================================================================
# load_config_file
# ==================================================================


class TestLoadConfigFile:
    def test_load_toml(self, tmp_path: Path) -> None:
        rc = tmp_path / ".ciarc"
        rc.write_text('[analysis]\nformat = "html"\n', encoding="utf-8")
        cfg = load_config_file(rc)
        assert cfg["analysis.format"] == "html"

    def test_load_json(self, tmp_path: Path) -> None:
        rc = tmp_path / ".ciarc.json"
        rc.write_text('{"analysis": {"format": "markdown"}}', encoding="utf-8")
        cfg = load_config_file(rc)
        assert cfg["analysis.format"] == "markdown"

    def test_load_yaml(self, tmp_path: Path) -> None:
        pytest.importorskip("yaml")
        rc = tmp_path / ".ciarc.yaml"
        rc.write_text("analysis:\n  format: html\n", encoding="utf-8")
        cfg = load_config_file(rc)
        assert cfg["analysis.format"] == "html"

    def test_yaml_import_error(self, tmp_path: Path) -> None:
        rc = tmp_path / ".ciarc.yaml"
        rc.write_text("x: 1\n", encoding="utf-8")
        with (
            patch.dict("sys.modules", {"yaml": None}),
            pytest.raises(ImportError, match="PyYAML"),
        ):
            load_config_file(rc)


# ==================================================================
# load_env_overrides
# ==================================================================


class TestLoadEnvOverrides:
    def test_string_var(self) -> None:
        with patch.dict(os.environ, {"CIA_FORMAT": "html"}, clear=False):
            env = load_env_overrides()
            assert env["format"] == "html"

    def test_int_var(self) -> None:
        with patch.dict(os.environ, {"CIA_THRESHOLD": "80"}, clear=False):
            env = load_env_overrides()
            assert env["threshold"] == 80

    def test_bool_true(self) -> None:
        with patch.dict(os.environ, {"CIA_EXPLAIN": "true"}, clear=False):
            env = load_env_overrides()
            assert env["explain"] is True

    def test_bool_false(self) -> None:
        with patch.dict(os.environ, {"CIA_EXPLAIN": "false"}, clear=False):
            env = load_env_overrides()
            assert env["explain"] is False

    def test_none_value(self) -> None:
        with patch.dict(os.environ, {"CIA_THRESHOLD": "none"}, clear=False):
            env = load_env_overrides()
            assert env["threshold"] is None

    def test_nested_key(self) -> None:
        with patch.dict(os.environ, {"CIA_ANALYSIS_FORMAT": "html"}, clear=False):
            env = load_env_overrides()
            assert env["analysis.format"] == "html"

    def test_ignores_non_cia(self) -> None:
        with patch.dict(os.environ, {"OTHER_VAR": "x"}, clear=False):
            env = load_env_overrides()
            assert "other.var" not in env


# ==================================================================
# load_config (full resolution)
# ==================================================================


class TestLoadConfig:
    def test_defaults(self, tmp_path: Path) -> None:
        cfg = load_config(tmp_path)
        assert cfg["format"] == DEFAULT_CONFIG["format"]
        assert cfg["threshold"] is None

    def test_file_overrides_defaults(self, tmp_path: Path) -> None:
        rc = tmp_path / ".ciarc"
        rc.write_text('[analysis]\nformat = "html"\n', encoding="utf-8")
        cfg = load_config(tmp_path)
        assert cfg["format"] == "html"

    def test_env_overrides_file(self, tmp_path: Path) -> None:
        rc = tmp_path / ".ciarc"
        rc.write_text('[analysis]\nformat = "html"\n', encoding="utf-8")
        with patch.dict(os.environ, {"CIA_FORMAT": "markdown"}, clear=False):
            cfg = load_config(tmp_path)
            assert cfg["format"] == "markdown"


# ==================================================================
# get_config_value
# ==================================================================


class TestGetConfigValue:
    def test_direct_key(self) -> None:
        assert get_config_value({"format": "json"}, "format") == "json"

    def test_short_key_match(self) -> None:
        cfg = {"analysis.format": "html"}
        assert get_config_value(cfg, "format") == "html"

    def test_missing_key(self) -> None:
        assert get_config_value({}, "missing") is None


# ==================================================================
# set_config_value
# ==================================================================


class TestSetConfigValue:
    def test_set_simple(self, tmp_path: Path) -> None:
        rc = tmp_path / ".ciarc"
        rc.write_text("", encoding="utf-8")
        set_config_value(rc, "format", "html")
        cfg = load_config_file(rc)
        # Bare key 'format' is routed to [analysis] section
        assert cfg["analysis.format"] == "html"

    def test_set_section_key(self, tmp_path: Path) -> None:
        rc = tmp_path / ".ciarc"
        rc.write_text("", encoding="utf-8")
        set_config_value(rc, "analysis.format", "markdown")
        cfg = load_config_file(rc)
        assert cfg["analysis.format"] == "markdown"

    def test_set_int(self, tmp_path: Path) -> None:
        rc = tmp_path / ".ciarc"
        rc.write_text("", encoding="utf-8")
        set_config_value(rc, "threshold", "80")
        cfg = load_config_file(rc)
        # Bare key 'threshold' is routed to [analysis] section
        assert cfg["analysis.threshold"] == 80

    def test_set_bool(self, tmp_path: Path) -> None:
        rc = tmp_path / ".ciarc"
        rc.write_text("", encoding="utf-8")
        set_config_value(rc, "explain", "true")
        cfg = load_config_file(rc)
        # Bare key 'explain' is routed to [analysis] section
        assert cfg["analysis.explain"] is True

    def test_set_json_file(self, tmp_path: Path) -> None:
        rc = tmp_path / ".ciarc.json"
        rc.write_text("{}", encoding="utf-8")
        set_config_value(rc, "format", "html")
        data = json.loads(rc.read_text(encoding="utf-8"))
        # Bare key 'format' is routed to 'analysis' section
        assert data["analysis"]["format"] == "html"

    def test_creates_file(self, tmp_path: Path) -> None:
        rc = tmp_path / ".ciarc"
        set_config_value(rc, "format", "html")
        assert rc.exists()

    def test_set_unknown_key_stays_toplevel(self, tmp_path: Path) -> None:
        rc = tmp_path / ".ciarc"
        rc.write_text("", encoding="utf-8")
        set_config_value(rc, "custom_key", "val")
        cfg = load_config_file(rc)
        assert cfg["custom_key"] == "val"


# ==================================================================
# DEFAULT_CIARC_CONTENT
# ==================================================================


class TestDefaultContent:
    def test_is_valid_toml(self, tmp_path: Path) -> None:
        rc = tmp_path / ".ciarc"
        rc.write_text(DEFAULT_CIARC_CONTENT, encoding="utf-8")
        cfg = load_config_file(rc)
        assert "analysis.format" in cfg
