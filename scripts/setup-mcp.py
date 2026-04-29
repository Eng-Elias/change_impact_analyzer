#!/usr/bin/env python3
"""Setup CIA MCP server for any AI coding assistant.

Usage:
    python scripts/setup-mcp.py                  # auto-detect assistant
    python scripts/setup-mcp.py windsurf         # specific assistant
    python scripts/setup-mcp.py claude-code      # Claude Code
    python scripts/setup-mcp.py opencode         # OpenCode
    python scripts/setup-mcp.py cursor           # Cursor
    python scripts/setup-mcp.py vscode           # VS Code Copilot
    python scripts/setup-mcp.py cline            # Cline
    python scripts/setup-mcp.py all              # all assistants
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

# CIA MCP server command
CIA_MCP_CMD = "cia-mcp"

# Config templates
STDIO_CONFIG = {
    "mcpServers": {
        "cia": {
            "command": CIA_MCP_CMD,
            "args": [],
        }
    }
}


def _write_json(path: Path, data: dict) -> None:
    """Write JSON config, merging with existing if present."""
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
            if "mcpServers" in existing:
                existing["mcpServers"]["cia"] = data["mcpServers"]["cia"]
            elif "servers" in existing:
                existing["servers"]["cia"] = data.get("servers", data["mcpServers"])[
                    "cia"
                ]
            else:
                existing.update(data)
            data = existing
        except (json.JSONDecodeError, KeyError):
            pass
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"  Written: {path}")


def setup_windsurf(project_root: Path) -> None:
    """Setup for Windsurf/Cascade."""
    print("\n[Windsurf] Setting up CIA MCP server...")

    # Windsurf global config: ~/.codeium/windsurf/mcp_config.json
    global_cfg = Path.home() / ".codeium" / "windsurf" / "mcp_config.json"
    _write_json(global_cfg, STDIO_CONFIG)
    print(f"  Global config: {global_cfg}")

    # Also write project-level .windsurf/mcp_config.json
    local_cfg = project_root / ".windsurf" / "mcp_config.json"
    _write_json(local_cfg, STDIO_CONFIG)

    # Copy workflow files
    workflows_src = project_root / ".windsurf" / "workflows"
    if workflows_src.exists():
        print(f"  Workflows: {workflows_src} (already present)")
    else:
        print(f"  Workflows directory: {workflows_src}")

    print("  Done! Restart Windsurf to activate CIA tools.")


def setup_claude_code(project_root: Path) -> None:
    """Setup for Claude Code."""
    print("\n[Claude Code] Setting up CIA MCP server...")
    # Claude Code uses `claude mcp add` CLI
    try:
        result = subprocess.run(
            ["claude", "mcp", "add", "cia", "--", CIA_MCP_CMD],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            print("  Registered via: claude mcp add cia -- cia-mcp")
            print("  Done! CIA tools are now available in Claude Code.")
        else:
            print(f"  Warning: claude CLI returned: {result.stderr.strip()}")
            print("  Manual setup: run `claude mcp add cia -- cia-mcp`")
    except FileNotFoundError:
        print("  claude CLI not found. Manual setup:")
        print("    claude mcp add cia -- cia-mcp")


def setup_opencode(project_root: Path) -> None:
    """Setup for OpenCode."""
    print("\n[OpenCode] Setting up CIA MCP server...")
    config_path = project_root / "mcp.json"
    _write_json(config_path, STDIO_CONFIG)
    print(
        "  Done! Run opencode with --mcp-config mcp.json "
        "or place mcp.json in project root."
    )


def setup_cursor(project_root: Path) -> None:
    """Setup for Cursor."""
    print("\n[Cursor] Setting up CIA MCP server...")
    config_path = project_root / ".cursor" / "mcp.json"
    _write_json(config_path, STDIO_CONFIG)
    print("  Done! Restart Cursor to activate CIA tools.")


def setup_vscode(project_root: Path) -> None:
    """Setup for VS Code Copilot."""
    print("\n[VS Code] Setting up CIA MCP server...")
    config_path = project_root / ".vscode" / "mcp.json"
    vscode_config = {
        "servers": {
            "cia": {
                "type": "stdio",
                "command": CIA_MCP_CMD,
                "args": [],
            }
        }
    }
    _write_json(config_path, vscode_config)
    print("  Done! Restart VS Code to activate CIA tools.")


def setup_cline(project_root: Path) -> None:
    """Setup for Cline."""
    print("\n[Cline] Setting up CIA MCP server...")
    config_path = project_root / ".cline" / "mcp_settings.json"
    cline_config = {
        "mcpServers": {
            "cia": {
                "command": CIA_MCP_CMD,
                "args": [],
                "disabled": False,
                "autoApprove": [],
            }
        }
    }
    _write_json(config_path, cline_config)
    print("  Done! Restart Cline to activate CIA tools.")


ASSISTANTS = {
    "windsurf": setup_windsurf,
    "claude-code": setup_claude_code,
    "opencode": setup_opencode,
    "cursor": setup_cursor,
    "vscode": setup_vscode,
    "cline": setup_cline,
}


def detect_assistants(project_root: Path) -> list[str]:
    """Auto-detect which assistants are present."""
    detected = []
    if (project_root / ".windsurf").exists():
        detected.append("windsurf")
    if (project_root / ".cursor").exists():
        detected.append("cursor")
    if (project_root / ".vscode").exists():
        detected.append("vscode")
    if (project_root / ".cline").exists():
        detected.append("cline")
    if shutil.which("claude"):
        detected.append("claude-code")
    if shutil.which("opencode"):
        detected.append("opencode")
    return detected


def check_installation() -> bool:
    """Check if cia-mcp is installed."""
    if shutil.which(CIA_MCP_CMD):
        return True
    # Try running as module
    try:
        result = subprocess.run(
            [sys.executable, "-m", "cia_mcp", "--help"],
            capture_output=True,
            check=False,
        )
        return result.returncode == 0
    except Exception:
        return False


def main() -> None:
    """Main entry point."""
    project_root = Path(__file__).resolve().parent.parent

    print("=" * 60)
    print("CIA MCP Server Setup")
    print("=" * 60)

    # Check installation
    if not check_installation():
        print("\ncia-mcp is not installed. Installing...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-e", f"{project_root}[mcp]"],
            check=True,
        )
        print("Installed successfully!")

    # Determine target assistants
    args = sys.argv[1:]
    if not args:
        detected = detect_assistants(project_root)
        if detected:
            print(f"\nAuto-detected assistants: {', '.join(detected)}")
            targets = detected
        else:
            print("\nNo assistants auto-detected. Setting up all configs...")
            targets = list(ASSISTANTS.keys())
    elif args[0] == "all":
        targets = list(ASSISTANTS.keys())
    elif args[0] in ASSISTANTS:
        targets = [args[0]]
    else:
        print(f"Unknown assistant: {args[0]}")
        print(f"Available: {', '.join(ASSISTANTS.keys())}, all")
        sys.exit(1)

    for target in targets:
        ASSISTANTS[target](project_root)

    print("\n" + "=" * 60)
    print("Setup complete!")
    print()
    print("Available CIA tools:")
    print("  cia_analyze          - Full impact analysis with risk scoring")
    print("  cia_detect_changes   - Detect changed files and symbols")
    print("  cia_graph            - Build dependency graph")
    print("  cia_get_dependents   - Find modules that depend on a target")
    print("  cia_get_dependencies - Find modules a target imports")
    print("  cia_predict_tests    - Predict affected tests")
    print("  cia_suggest_tests    - Find test coverage gaps")
    print("  cia_score_risk       - Score risk for specific files")
    print("  cia_init             - Initialize CIA config")
    print("  cia_config_get/set   - Read/write CIA configuration")
    print()
    print("Available prompts:")
    print("  pre_commit_review    - Full risk + test + coverage review")
    print("  blast_radius         - Module blast radius deep-dive")
    print("  test_gap_analysis    - Find and fill test coverage gaps")
    print("  dependency_audit     - Architecture health check")
    print("  safe_refactor        - CIA-guided rename/move")
    print("  pr_summary           - PR description generator")
    print("  risk_explanation     - Detailed risk factor breakdown")
    print("=" * 60)


if __name__ == "__main__":
    main()
