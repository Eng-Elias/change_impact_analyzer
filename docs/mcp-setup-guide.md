# CIA MCP Server -- Setup Guide

Install the Change Impact Analyzer MCP server and connect it to your AI
coding assistant in one command.

---

## Quick Start

### 1. Install

```bash
pip install change-impact-analyzer[mcp]
```

Or from source (for development):

```bash
git clone https://github.com/Eng-Elias/change_impact_analyzer.git
cd change_impact_analyzer
pip install -e ".[mcp]"
```

### 2. Connect to Your Assistant

**Automatic setup** (detects installed assistants):

```bash
python scripts/setup-mcp.py
```

**Specific assistant:**

```bash
python scripts/setup-mcp.py windsurf
python scripts/setup-mcp.py claude-code
python scripts/setup-mcp.py opencode
python scripts/setup-mcp.py cursor
python scripts/setup-mcp.py vscode
python scripts/setup-mcp.py cline
python scripts/setup-mcp.py all
```

### 3. Verify

```bash
cia-mcp --help
```

---

## Manual Setup Per Assistant

### Windsurf / Cascade

The setup script writes the global config at `~/.codeium/windsurf/mcp_config.json`
and project-level `.windsurf/mcp_config.json`, plus workflow files.

**Manual alternative** -- add to `~/.codeium/windsurf/mcp_config.json`:

```json
{
  "mcpServers": {
    "cia": {
      "command": "cia-mcp",
      "args": []
    }
  }
}
```

Workflows are in `.windsurf/workflows/cia-*.md`. Available commands:

| Workflow | Description |
|----------|-------------|
| `/cia-review` | Full pre-commit review |
| `/cia-risk` | Show risk score |
| `/cia-tests` | Show affected tests |
| `/cia-suggest` | Find and write missing tests |
| `/cia-blast` | Module blast radius |
| `/cia-audit` | Architecture health audit |
| `/cia-graph` | Show dependency graph |
| `/cia-refactor` | CIA-guided safe refactoring |
| `/cia-pr-summary` | Generate PR description |
| `/cia-init` | Initialize CIA config |

### Claude Code

**One command:**

```bash
claude mcp add cia -- cia-mcp
```

Or run the setup script:

```bash
python scripts/setup-mcp.py claude-code
```

### OpenCode

Place `mcp.json` in your project root:

```json
{
  "mcpServers": {
    "cia": {
      "command": "cia-mcp",
      "args": []
    }
  }
}
```

Or run:

```bash
python scripts/setup-mcp.py opencode
```

Then start OpenCode normally -- it reads `mcp.json` from the working directory.

### Cursor

Add to `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "cia": {
      "command": "cia-mcp",
      "args": []
    }
  }
}
```

Or run:

```bash
python scripts/setup-mcp.py cursor
```

### VS Code Copilot

Add to `.vscode/mcp.json`:

```json
{
  "servers": {
    "cia": {
      "type": "stdio",
      "command": "cia-mcp",
      "args": []
    }
  }
}
```

Or run:

```bash
python scripts/setup-mcp.py vscode
```

### Cline

Add to `.cline/mcp_settings.json`:

```json
{
  "mcpServers": {
    "cia": {
      "command": "cia-mcp",
      "args": [],
      "disabled": false,
      "autoApprove": []
    }
  }
}
```

Or run:

```bash
python scripts/setup-mcp.py cline
```

### Continue

Add to your Continue config (`.continue/config.json`):

```json
{
  "experimental": {
    "modelContextProtocolServers": [
      {
        "transport": {
          "type": "stdio",
          "command": "cia-mcp",
          "args": []
        }
      }
    ]
  }
}
```

---

## Available MCP Tools

| Tool | Description |
|------|-------------|
| `cia_analyze` | Full impact analysis with risk scoring |
| `cia_detect_changes` | Detect changed files and symbols |
| `cia_graph` | Build dependency graph (json/text/dot) |
| `cia_get_dependents` | Find downstream modules |
| `cia_get_dependencies` | Find upstream modules |
| `cia_predict_tests` | Predict affected tests |
| `cia_suggest_tests` | Find test coverage gaps |
| `cia_score_risk` | Score risk for specific files |
| `cia_init` | Initialize .ciarc config |
| `cia_config_get` | Read configuration |
| `cia_config_set` | Write configuration |

## Available MCP Resources

| URI | Description |
|-----|-------------|
| `cia://version` | CIA version and environment |
| `cia://config` | Effective configuration |
| `cia://risk/weights` | Risk factor weights |
| `cia://risk/thresholds` | Score-to-level mapping |

## Available MCP Prompts

| Prompt | Description |
|--------|-------------|
| `pre_commit_review` | Full risk + test + coverage review |
| `blast_radius` | Module blast radius deep-dive |
| `test_gap_analysis` | Find and fill test coverage gaps |
| `dependency_audit` | Architecture health audit |
| `safe_refactor` | CIA-guided rename/move |
| `pr_summary` | PR description generator |
| `risk_explanation` | Detailed risk factor breakdown |

---

## Transport Options

**stdio** (default -- local assistants):

```bash
cia-mcp
```

**SSE** (remote / web clients):

```bash
cia-mcp --transport sse --port 8080
```

---

## Troubleshooting

**cia-mcp not found after install:**

```bash
# Verify installation
pip show change-impact-analyzer
# Run as module instead
python -m cia_mcp
```

**MCP tools not appearing in assistant:**

1. Verify `cia-mcp --help` works in your terminal
2. Check the config file path matches your assistant's expected location
3. Restart your AI assistant after adding the config
4. Check assistant logs for MCP connection errors

**"Not a Git repository" error:**

CIA requires a Git repository. Run `git init` if your project has not been initialized.
