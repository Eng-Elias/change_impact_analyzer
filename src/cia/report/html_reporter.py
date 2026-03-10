"""HTML report generation using Jinja2 templates."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape

from cia.analyzer.impact_analyzer import AnalysisReport
from cia.risk.risk_scorer import RiskAssessment

DEFAULT_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Change Impact Analysis Report</title>
    <style>
        body { font-family: system-ui, -apple-system, sans-serif; max-width: 900px; margin: 2rem auto; padding: 0 1rem; color: #1a1a1a; }
        h1 { border-bottom: 2px solid #2563eb; padding-bottom: 0.5rem; }
        .summary { background: #f0f9ff; border-radius: 8px; padding: 1rem 1.5rem; margin: 1rem 0; }
        .impact { border: 1px solid #e5e7eb; border-radius: 8px; padding: 1rem 1.5rem; margin: 1rem 0; }
        .risk-low { border-left: 4px solid #22c55e; }
        .risk-medium { border-left: 4px solid #eab308; }
        .risk-high { border-left: 4px solid #f97316; }
        .risk-critical { border-left: 4px solid #ef4444; }
        .badge { display: inline-block; padding: 0.2rem 0.6rem; border-radius: 4px; font-size: 0.85rem; font-weight: 600; }
        .badge-low { background: #dcfce7; color: #166534; }
        .badge-medium { background: #fef9c3; color: #854d0e; }
        .badge-high { background: #ffedd5; color: #9a3412; }
        .badge-critical { background: #fee2e2; color: #991b1b; }
        ul { padding-left: 1.5rem; }
        code { background: #f1f5f9; padding: 0.15rem 0.4rem; border-radius: 3px; font-size: 0.9rem; }
    </style>
</head>
<body>
    <h1>Change Impact Analysis Report</h1>
    <div class="summary">
        <h2>Summary</h2>
        <p><strong>Files changed:</strong> {{ summary.total_files_changed }}</p>
        <p><strong>Symbols affected:</strong> {{ summary.total_symbols_affected }}</p>
        <p><strong>Modules affected:</strong> {{ summary.total_modules_affected }}</p>
    </div>
    {% for item in impacts %}
    <div class="impact risk-{{ item.risk_level }}">
        <h3>{{ item.file_path }}</h3>
        <p><strong>Change type:</strong> {{ item.change_type }}</p>
        {% if item.risk_score is not none %}
        <p><strong>Risk:</strong> <span class="badge badge-{{ item.risk_level }}">{{ item.risk_level | upper }} ({{ "%.3f" | format(item.risk_score) }})</span></p>
        {% endif %}
        {% if item.directly_affected %}
        <h4>Directly Affected</h4>
        <ul>{% for name in item.directly_affected %}<li><code>{{ name }}</code></li>{% endfor %}</ul>
        {% endif %}
        {% if item.transitively_affected %}
        <h4>Transitively Affected</h4>
        <ul>{% for name in item.transitively_affected %}<li><code>{{ name }}</code></li>{% endfor %}</ul>
        {% endif %}
        {% if item.affected_modules %}
        <h4>Affected Modules</h4>
        <ul>{% for name in item.affected_modules %}<li><code>{{ name }}</code></li>{% endfor %}</ul>
        {% endif %}
    </div>
    {% endfor %}
</body>
</html>
"""


class HtmlReporter:
    """Generates impact analysis reports in HTML format."""

    def __init__(self) -> None:
        self._env = Environment(autoescape=select_autoescape(["html"]))
        self._template = self._env.from_string(DEFAULT_HTML_TEMPLATE)

    def generate(
        self,
        report: AnalysisReport,
        risk_assessments: list[RiskAssessment] | None = None,
    ) -> str:
        """Generate an HTML string from the analysis report."""
        impacts = []
        for i, impact in enumerate(report.impacts):
            entry = {
                "file_path": str(impact.change.file_path),
                "change_type": impact.change.change_type,
                "directly_affected": impact.directly_affected,
                "transitively_affected": impact.transitively_affected,
                "affected_modules": impact.affected_modules,
                "risk_score": None,
                "risk_level": "low",
            }
            if risk_assessments and i < len(risk_assessments):
                ra = risk_assessments[i]
                entry["risk_score"] = ra.score
                entry["risk_level"] = ra.level.value
            impacts.append(entry)

        return self._template.render(
            summary={
                "total_files_changed": report.total_files_changed,
                "total_symbols_affected": report.total_symbols_affected,
                "total_modules_affected": report.total_modules_affected,
            },
            impacts=impacts,
        )

    def write(
        self,
        report: AnalysisReport,
        output_path: Path,
        risk_assessments: list[RiskAssessment] | None = None,
    ) -> Path:
        """Write the HTML report to a file."""
        content = self.generate(report, risk_assessments)
        output_path.write_text(content, encoding="utf-8")
        return output_path
