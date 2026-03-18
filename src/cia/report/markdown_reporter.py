"""Markdown report generation — GitHub / GitLab compatible."""

from __future__ import annotations

from pathlib import Path

from cia.analyzer.impact_analyzer import ImpactReport

# ---------------------------------------------------------------------------
# Emoji helpers (for GitHub / GitLab rendering)
# ---------------------------------------------------------------------------

_LEVEL_EMOJI = {
    "low": "\U0001f7e2",       # green circle
    "medium": "\U0001f7e1",    # yellow circle
    "high": "\U0001f7e0",      # orange circle
    "critical": "\U0001f534",  # red circle
}


# ---------------------------------------------------------------------------
# MarkdownReporter
# ---------------------------------------------------------------------------


class MarkdownReporter:
    """Generates Markdown reports suitable for PR comments."""

    def generate(self, report: ImpactReport) -> str:
        """Generate a Markdown string from the *ImpactReport*."""
        lines: list[str] = []
        analysis = report.analysis
        risk = report.risk

        # -- Executive Summary --
        lines.append("# Change Impact Analysis Report\n")
        lines.append("## Executive Summary\n")
        if risk is not None:
            emoji = _LEVEL_EMOJI.get(risk.level.value, "")
            lines.append(
                f"**Risk:** {emoji} **{risk.level.value.upper()}** "
                f"({risk.overall_score:.1f}/100)"
            )
        lines.append(f"- **Files changed:** {analysis.total_files_changed}")
        lines.append(f"- **Symbols affected:** {analysis.total_symbols_affected}")
        lines.append(f"- **Modules affected:** {analysis.total_modules_affected}")
        if report.affected_tests:
            lines.append(f"- **Tests to run:** {len(report.affected_tests)}")
        lines.append("")

        # -- Change Overview --
        if analysis.impacts:
            lines.append("## Change Overview\n")
            lines.append("| File | Type | Added | Deleted |")
            lines.append("|------|------|------:|--------:|")
            for impact in analysis.impacts:
                c = impact.change
                lines.append(
                    f"| `{c.file_path}` | {c.change_type} "
                    f"| {len(c.added_lines)} | {len(c.deleted_lines)} |"
                )
            lines.append("")

        # -- Dependency Impact --
        if report.affected_modules:
            lines.append("## Dependency Impact\n")
            lines.append("Affected modules:\n")
            for mod in report.affected_modules:
                lines.append(f"- `{mod}`")
            lines.append("")

        for impact in analysis.impacts:
            if impact.directly_affected or impact.transitively_affected:
                lines.append(f"### {impact.change.file_path}\n")
                if impact.directly_affected:
                    lines.append("**Directly affected:**\n")
                    for name in impact.directly_affected:
                        lines.append(f"- `{name}`")
                    lines.append("")
                if impact.transitively_affected:
                    lines.append("**Transitively affected:**\n")
                    for name in impact.transitively_affected:
                        lines.append(f"- `{name}`")
                    lines.append("")

        # -- Risk Breakdown --
        if risk is not None and risk.factor_scores:
            lines.append("## Risk Breakdown\n")
            lines.append("| Factor | Score |")
            lines.append("|--------|------:|")
            for name, score in risk.factor_scores.items():
                lines.append(f"| {name} | {score:.1f} |")
            lines.append("")

            if risk.explanations:
                lines.append("**Explanations:**\n")
                for exp in risk.explanations:
                    lines.append(f"- {exp}")
                lines.append("")

        # -- Test Recommendations --
        if report.affected_tests:
            lines.append("## Test Recommendations\n")
            lines.append("Run these test files:\n")
            for t in report.affected_tests:
                lines.append(f"- `{t}`")
            lines.append("")

        # -- Action Items --
        if report.recommendations:
            lines.append("## Action Items\n")
            for i, rec in enumerate(report.recommendations, 1):
                lines.append(f"{i}. {rec}")
            lines.append("")

        if risk is not None and risk.suggestions:
            lines.append("### Risk-Based Suggestions\n")
            for s in risk.suggestions:
                lines.append(f"- {s}")
            lines.append("")

        return "\n".join(lines)

    def write(self, report: ImpactReport, output_path: Path) -> Path:
        """Write the Markdown report to a file."""
        content = self.generate(report)
        output_path.write_text(content, encoding="utf-8")
        return output_path
