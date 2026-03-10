"""Markdown report generation."""

from __future__ import annotations

from pathlib import Path

from cia.analyzer.impact_analyzer import AnalysisReport
from cia.risk.risk_scorer import RiskAssessment


class MarkdownReporter:
    """Generates impact analysis reports in Markdown format."""

    def generate(
        self,
        report: AnalysisReport,
        risk_assessments: list[RiskAssessment] | None = None,
    ) -> str:
        """Generate a Markdown string from the analysis report."""
        lines: list[str] = []
        lines.append("# Change Impact Analysis Report\n")
        lines.append("## Summary\n")
        lines.append(f"- **Files changed:** {report.total_files_changed}")
        lines.append(f"- **Symbols affected:** {report.total_symbols_affected}")
        lines.append(f"- **Modules affected:** {report.total_modules_affected}")
        lines.append("")

        for i, impact in enumerate(report.impacts):
            lines.append(f"## {impact.change.file_path}\n")
            lines.append(f"- **Change type:** {impact.change.change_type}")

            if risk_assessments and i < len(risk_assessments):
                ra = risk_assessments[i]
                lines.append(f"- **Risk score:** {ra.score:.3f} ({ra.level.value})")

            if impact.directly_affected:
                lines.append("\n### Directly Affected\n")
                for name in impact.directly_affected:
                    lines.append(f"- `{name}`")

            if impact.transitively_affected:
                lines.append("\n### Transitively Affected\n")
                for name in impact.transitively_affected:
                    lines.append(f"- `{name}`")

            if impact.affected_modules:
                lines.append("\n### Affected Modules\n")
                for name in impact.affected_modules:
                    lines.append(f"- `{name}`")

            lines.append("")

        return "\n".join(lines)

    def write(
        self,
        report: AnalysisReport,
        output_path: Path,
        risk_assessments: list[RiskAssessment] | None = None,
    ) -> Path:
        """Write the Markdown report to a file."""
        content = self.generate(report, risk_assessments)
        output_path.write_text(content, encoding="utf-8")
        return output_path
