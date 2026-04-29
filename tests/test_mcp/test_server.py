"""Tests for the CIA MCP server tools, resources, and prompts."""

from __future__ import annotations

import json

import pytest

from cia_mcp.server import (
    cia_config_get,
    cia_get_dependencies,
    cia_get_dependents,
    cia_graph,
    cia_init,
    cia_score_risk,
    cia_suggest_tests,
    create_server,
)

# ---------------------------------------------------------------------------
# Server creation
# ---------------------------------------------------------------------------


class TestCreateServer:
    """Test server factory."""

    def test_create_server_returns_fastmcp(self):
        server = create_server()
        assert server.name == "cia"

    def test_server_has_tools(self):
        server = create_server()
        tool_names = [t.name for t in server._tool_manager._tools.values()]
        assert "cia_analyze" in tool_names
        assert "cia_graph" in tool_names
        assert "cia_predict_tests" in tool_names
        assert "cia_suggest_tests" in tool_names
        assert "cia_get_dependents" in tool_names
        assert "cia_get_dependencies" in tool_names
        assert "cia_score_risk" in tool_names
        assert "cia_detect_changes" in tool_names
        assert "cia_init" in tool_names
        assert "cia_config_get" in tool_names
        assert "cia_config_set" in tool_names

    def test_server_tool_count(self):
        server = create_server()
        assert len(server._tool_manager._tools) == 11


# ---------------------------------------------------------------------------
# Tools — cia_graph
# ---------------------------------------------------------------------------


class TestCiaGraph:
    """Test the cia_graph tool."""

    def test_graph_json(self, tmp_path):
        (tmp_path / "a.py").write_text("import b\n")
        (tmp_path / "b.py").write_text("x = 1\n")
        result = json.loads(cia_graph(str(tmp_path), "json"))
        assert "modules" in result
        assert "dependencies" in result
        assert "summary" in result
        assert result["summary"]["module_count"] >= 2

    def test_graph_text(self, tmp_path):
        (tmp_path / "a.py").write_text("import b\n")
        (tmp_path / "b.py").write_text("x = 1\n")
        result = cia_graph(str(tmp_path), "text")
        assert "a" in result
        assert "b" in result

    def test_graph_dot(self, tmp_path):
        (tmp_path / "a.py").write_text("import b\n")
        (tmp_path / "b.py").write_text("x = 1\n")
        result = cia_graph(str(tmp_path), "dot")
        assert "digraph" in result
        assert '"a"' in result

    def test_graph_empty_dir(self, tmp_path):
        result = json.loads(cia_graph(str(tmp_path), "json"))
        assert result["modules"] == {}


# ---------------------------------------------------------------------------
# Tools — cia_get_dependents / cia_get_dependencies
# ---------------------------------------------------------------------------


class TestCiaDependents:
    """Test dependents and dependencies tools."""

    def test_direct_dependents(self, tmp_path):
        (tmp_path / "core.py").write_text("x = 1\n")
        (tmp_path / "engine.py").write_text("import core\n")
        result = json.loads(cia_get_dependents("core", str(tmp_path)))
        assert "engine" in result["direct_dependents"]

    def test_transitive_dependents(self, tmp_path):
        (tmp_path / "core.py").write_text("x = 1\n")
        (tmp_path / "engine.py").write_text("import core\n")
        (tmp_path / "app.py").write_text("import engine\n")
        result = json.loads(cia_get_dependents("core", str(tmp_path), transitive=True))
        assert result["total_count"] >= 2

    def test_direct_dependencies(self, tmp_path):
        (tmp_path / "core.py").write_text("x = 1\n")
        (tmp_path / "engine.py").write_text("import core\n")
        result = json.loads(cia_get_dependencies("engine", str(tmp_path)))
        assert "core" in result["direct_dependencies"]

    def test_no_dependents(self, tmp_path):
        (tmp_path / "orphan.py").write_text("x = 1\n")
        result = json.loads(cia_get_dependents("orphan", str(tmp_path)))
        assert result["direct_count"] == 0


# ---------------------------------------------------------------------------
# Tools — cia_score_risk
# ---------------------------------------------------------------------------


class TestCiaScoreRisk:
    """Test the risk scoring tool."""

    def test_score_risk_returns_json(self, tmp_path):
        (tmp_path / "a.py").write_text("x = 1\n")
        result = json.loads(cia_score_risk(["a.py"], str(tmp_path)))
        assert "overall_score" in result
        assert "level" in result
        assert "factor_scores" in result
        assert isinstance(result["overall_score"], (int, float))


# ---------------------------------------------------------------------------
# Tools — cia_init
# ---------------------------------------------------------------------------


class TestCiaInit:
    """Test the init tool."""

    def test_init_creates_ciarc(self, tmp_path):
        result = json.loads(cia_init(str(tmp_path)))
        assert result["status"] == "created"
        assert (tmp_path / ".ciarc").exists()

    def test_init_already_exists(self, tmp_path):
        (tmp_path / ".ciarc").write_text("existing")
        result = json.loads(cia_init(str(tmp_path)))
        assert result["status"] == "exists"


# ---------------------------------------------------------------------------
# Tools — cia_config_get
# ---------------------------------------------------------------------------


class TestCiaConfigGet:
    """Test config get tool."""

    def test_get_all_config(self, tmp_path):
        result = json.loads(cia_config_get(path=str(tmp_path)))
        assert "config" in result
        assert "format" in result["config"]

    def test_get_specific_key(self, tmp_path):
        result = json.loads(cia_config_get(key="format", path=str(tmp_path)))
        assert result["key"] == "format"
        assert result["value"] is not None


# ---------------------------------------------------------------------------
# Tools — cia_suggest_tests
# ---------------------------------------------------------------------------


class TestCiaSuggestTests:
    """Test the suggest tests tool."""

    def test_suggest_on_clean_repo(self, tmp_path):
        """No git repo => should raise ValueError."""
        (tmp_path / "a.py").write_text("x = 1\n")
        with pytest.raises(ValueError, match="Not a Git repository"):
            cia_suggest_tests(str(tmp_path))


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------


class TestPrompts:
    """Test that prompts return instruction strings."""

    def test_pre_commit_review_prompt(self):
        from cia_mcp.server import pre_commit_review

        result = pre_commit_review(".")
        assert "cia_analyze" in result
        assert "cia_predict_tests" in result

    def test_blast_radius_prompt(self):
        from cia_mcp.server import blast_radius

        result = blast_radius("core", ".")
        assert "core" in result
        assert "cia_get_dependents" in result

    def test_dependency_audit_prompt(self):
        from cia_mcp.server import dependency_audit

        result = dependency_audit(".")
        assert "cia_graph" in result

    def test_safe_refactor_prompt(self):
        from cia_mcp.server import safe_refactor

        result = safe_refactor("MyClass", ".")
        assert "MyClass" in result

    def test_pr_summary_prompt(self):
        from cia_mcp.server import pr_summary

        result = pr_summary(".")
        assert "cia_analyze" in result

    def test_risk_explanation_prompt(self):
        from cia_mcp.server import risk_explanation

        result = risk_explanation(".")
        assert "cia_analyze" in result


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------


class TestResources:
    """Test MCP resources."""

    def test_version_resource(self):
        from cia_mcp.server import resource_version

        result = json.loads(resource_version())
        assert "version" in result
        assert "python" in result

    def test_config_resource(self):
        from cia_mcp.server import resource_config

        result = json.loads(resource_config())
        assert "config" in result

    def test_risk_weights_resource(self):
        from cia_mcp.server import resource_risk_weights

        result = json.loads(resource_risk_weights())
        assert "dependents" in result

    def test_risk_thresholds_resource(self):
        from cia_mcp.server import resource_risk_thresholds

        result = json.loads(resource_risk_thresholds())
        assert "low" in result
        assert "critical" in result
