"""HTML report generation using Jinja2 templates."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jinja2 import Environment, select_autoescape

from cia.analyzer.impact_analyzer import ImpactReport

# ---------------------------------------------------------------------------
# Default HTML template (self-contained with inline CSS + D3.js)
# ---------------------------------------------------------------------------

DEFAULT_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Change Impact Analysis Report</title>
<style>
  :root {
    --low: #22c55e; --medium: #eab308; --high: #f97316; --critical: #ef4444;
  }
  * { box-sizing: border-box; }
  body { font-family: system-ui, -apple-system, sans-serif; max-width: 960px; margin: 2rem auto; padding: 0 1rem; color: #1a1a1a; }
  h1 { border-bottom: 2px solid #2563eb; padding-bottom: .5rem; }
  h2 { margin-top: 2rem; }
  .summary { background: #f0f9ff; border-radius: 8px; padding: 1rem 1.5rem; margin: 1rem 0; }
  .card { border: 1px solid #e5e7eb; border-radius: 8px; padding: 1rem 1.5rem; margin: 1rem 0; }
  .risk-low    { border-left: 4px solid var(--low); }
  .risk-medium { border-left: 4px solid var(--medium); }
  .risk-high   { border-left: 4px solid var(--high); }
  .risk-critical { border-left: 4px solid var(--critical); }
  .badge { display: inline-block; padding: .2rem .6rem; border-radius: 4px; font-size: .85rem; font-weight: 600; }
  .badge-low      { background: #dcfce7; color: #166534; }
  .badge-medium   { background: #fef9c3; color: #854d0e; }
  .badge-high     { background: #ffedd5; color: #9a3412; }
  .badge-critical { background: #fee2e2; color: #991b1b; }
  ul { padding-left: 1.5rem; }
  code { background: #f1f5f9; padding: .15rem .4rem; border-radius: 3px; font-size: .9rem; }
  table { width: 100%; border-collapse: collapse; margin: .5rem 0; }
  th, td { text-align: left; padding: .4rem .6rem; border-bottom: 1px solid #e5e7eb; }
  th { background: #f8fafc; font-size: .85rem; text-transform: uppercase; letter-spacing: .05em; }
  .heatmap-cell { display: inline-block; width: 100%; height: 1.4rem; border-radius: 3px; }
  .collapsible { cursor: pointer; user-select: none; }
  .collapsible::before { content: "\\25B6  "; font-size: .75rem; }
  .collapsible.open::before { content: "\\25BC  "; }
  .collapse-body { display: none; padding-left: 1rem; }
  .collapse-body.show { display: block; }
  #dep-graph { width: 100%; height: 320px; border: 1px solid #e5e7eb; border-radius: 8px; margin: 1rem 0; }
  .suggestion { padding: .3rem 0; }
</style>
</head>
<body>

<!-- ============ Executive Summary ============ -->
<h1>Change Impact Analysis Report</h1>

<div class="summary">
  <h2 style="margin-top:0">Executive Summary</h2>
  {% if risk %}
  <p><strong>Risk:</strong>
    <span class="badge badge-{{ risk.level }}">{{ risk.level | upper }} &mdash; {{ "%.1f" | format(risk.score) }}/100</span>
  </p>
  {% endif %}
  <p><strong>Files changed:</strong> {{ summary.total_files_changed }}</p>
  <p><strong>Symbols affected:</strong> {{ summary.total_symbols_affected }}</p>
  <p><strong>Modules affected:</strong> {{ summary.total_modules_affected }}</p>
  {% if affected_tests %}
  <p><strong>Tests to run:</strong> {{ affected_tests | length }}</p>
  {% endif %}
</div>

<!-- ============ Change Overview ============ -->
<h2>Change Overview</h2>
<div class="card">
{% if impacts %}
<table>
  <thead><tr><th>File</th><th>Type</th><th>Added</th><th>Deleted</th></tr></thead>
  <tbody>
  {% for item in impacts %}
  <tr>
    <td><code>{{ item.file_path }}</code></td>
    <td>{{ item.change_type }}</td>
    <td>{{ item.added_lines }}</td>
    <td>{{ item.deleted_lines }}</td>
  </tr>
  {% endfor %}
  </tbody>
</table>
{% else %}
<p>No changes detected.</p>
{% endif %}
</div>

<!-- ============ Dependency Impact ============ -->
<h2>Dependency Impact</h2>
<div id="dep-graph"></div>
{% if affected_modules %}
<div class="card">
  <h3 style="margin-top:0">Affected Modules</h3>
  <ul>
  {% for mod in affected_modules %}
    <li><code>{{ mod }}</code></li>
  {% endfor %}
  </ul>
</div>
{% endif %}

{% for item in impacts %}
{% if item.directly_affected or item.transitively_affected %}
<div class="card">
  <h4 class="collapsible" onclick="toggle(this)">{{ item.file_path }}</h4>
  <div class="collapse-body">
    {% if item.directly_affected %}
    <p><strong>Directly affected:</strong></p>
    <ul>{% for name in item.directly_affected %}<li><code>{{ name }}</code></li>{% endfor %}</ul>
    {% endif %}
    {% if item.transitively_affected %}
    <p><strong>Transitively affected:</strong></p>
    <ul>{% for name in item.transitively_affected %}<li><code>{{ name }}</code></li>{% endfor %}</ul>
    {% endif %}
  </div>
</div>
{% endif %}
{% endfor %}

{% if risk %}
<!-- ============ Risk Breakdown ============ -->
<h2>Risk Breakdown</h2>
<div class="card risk-{{ risk.level }}">
  <table>
    <thead><tr><th>Factor</th><th>Score</th><th>Heatmap</th></tr></thead>
    <tbody>
    {% for name, score in risk.factor_scores.items() %}
    <tr>
      <td>{{ name }}</td>
      <td>{{ "%.1f" | format(score) }}</td>
      <td><span class="heatmap-cell" style="background: {{ heatmap_color(score) }};"></span></td>
    </tr>
    {% endfor %}
    </tbody>
  </table>
  {% if risk.explanations %}
  <h4>Explanations</h4>
  <ul>
  {% for line in risk.explanations %}
    <li>{{ line }}</li>
  {% endfor %}
  </ul>
  {% endif %}
</div>
{% endif %}

{% if affected_tests %}
<!-- ============ Test Recommendations ============ -->
<h2>Test Recommendations</h2>
<div class="card">
  <p><strong>Run these {{ affected_tests | length }} test files:</strong></p>
  <ul>
  {% for t in affected_tests %}
    <li><code>{{ t }}</code></li>
  {% endfor %}
  </ul>
</div>
{% endif %}

{% if recommendations %}
<!-- ============ Action Items ============ -->
<h2>Action Items</h2>
<div class="card">
  <ol>
  {% for rec in recommendations %}
    <li class="suggestion">{{ rec }}</li>
  {% endfor %}
  </ol>
</div>
{% endif %}

{% if risk and risk.suggestions %}
<div class="card">
  <h3 style="margin-top:0">Risk-Based Suggestions</h3>
  <ul>
  {% for s in risk.suggestions %}
    <li>{{ s }}</li>
  {% endfor %}
  </ul>
</div>
{% endif %}

<!-- ============ D3.js dependency graph ============ -->
<script src="https://d3js.org/d3.v7.min.js"></script>
<script>
function toggle(el){
  el.classList.toggle("open");
  var body=el.nextElementSibling;
  if(body) body.classList.toggle("show");
}
(function(){
  var graphData = {{ graph_json }};
  if(!graphData.nodes.length) return;
  var container = document.getElementById("dep-graph");
  var width = container.clientWidth || 900;
  var height = 320;
  var svg = d3.select("#dep-graph").append("svg").attr("width", width).attr("height", height);
  var simulation = d3.forceSimulation(graphData.nodes)
    .force("link", d3.forceLink(graphData.links).id(function(d){return d.id;}).distance(80))
    .force("charge", d3.forceManyBody().strength(-200))
    .force("center", d3.forceCenter(width/2, height/2));
  var link = svg.append("g").selectAll("line").data(graphData.links).enter().append("line")
    .attr("stroke","#94a3b8").attr("stroke-width",1.5);
  var node = svg.append("g").selectAll("circle").data(graphData.nodes).enter().append("circle")
    .attr("r",8).attr("fill",function(d){return d.changed?"#ef4444":"#3b82f6";})
    .call(d3.drag().on("start",dragstart).on("drag",dragged).on("end",dragend));
  var label = svg.append("g").selectAll("text").data(graphData.nodes).enter().append("text")
    .text(function(d){return d.id;}).attr("font-size","11px").attr("dx",12).attr("dy",4);
  simulation.on("tick",function(){
    link.attr("x1",function(d){return d.source.x;}).attr("y1",function(d){return d.source.y;})
        .attr("x2",function(d){return d.target.x;}).attr("y2",function(d){return d.target.y;});
    node.attr("cx",function(d){return d.x;}).attr("cy",function(d){return d.y;});
    label.attr("x",function(d){return d.x;}).attr("y",function(d){return d.y;});
  });
  function dragstart(e,d){if(!e.active) simulation.alphaTarget(.3).restart();d.fx=d.x;d.fy=d.y;}
  function dragged(e,d){d.fx=e.x;d.fy=e.y;}
  function dragend(e,d){if(!e.active) simulation.alphaTarget(0);d.fx=null;d.fy=null;}
})();
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# HtmlReporter
# ---------------------------------------------------------------------------


def _heatmap_color(score: float) -> str:
    """Return a CSS colour string based on 0–100 score."""
    if score >= 76:
        return "#ef4444"
    if score >= 51:
        return "#f97316"
    if score >= 26:
        return "#eab308"
    return "#22c55e"


class HtmlReporter:
    """Generates impact analysis reports in HTML format."""

    def __init__(self) -> None:
        self._env = Environment(autoescape=select_autoescape(["html"]))
        self._env.globals["heatmap_color"] = _heatmap_color
        self._template = self._env.from_string(DEFAULT_HTML_TEMPLATE)

    def generate(self, report: ImpactReport) -> str:
        """Generate an HTML string from the *ImpactReport*."""
        ctx = self._build_context(report)
        return self._template.render(**ctx)

    def write(self, report: ImpactReport, output_path: Path) -> Path:
        """Write the HTML report to a file."""
        content = self.generate(report)
        output_path.write_text(content, encoding="utf-8")
        return output_path

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _build_context(report: ImpactReport) -> dict[str, Any]:
        """Transform an *ImpactReport* into template context."""
        analysis = report.analysis
        risk = report.risk

        impacts = []
        for impact in analysis.impacts:
            impacts.append({
                "file_path": str(impact.change.file_path),
                "change_type": impact.change.change_type,
                "added_lines": len(impact.change.added_lines),
                "deleted_lines": len(impact.change.deleted_lines),
                "directly_affected": impact.directly_affected,
                "transitively_affected": impact.transitively_affected,
                "affected_modules": impact.affected_modules,
            })

        risk_ctx = None
        if risk is not None:
            risk_ctx = {
                "score": risk.overall_score,
                "level": risk.level.value,
                "factor_scores": risk.factor_scores,
                "explanations": risk.explanations,
                "suggestions": risk.suggestions,
            }

        # Build D3-compatible graph JSON
        graph_data = _build_graph_data(report)

        return {
            "summary": {
                "total_files_changed": analysis.total_files_changed,
                "total_symbols_affected": analysis.total_symbols_affected,
                "total_modules_affected": analysis.total_modules_affected,
            },
            "impacts": impacts,
            "risk": risk_ctx,
            "affected_tests": [str(t) for t in report.affected_tests],
            "affected_modules": report.affected_modules,
            "recommendations": report.recommendations,
            "graph_json": json.dumps(graph_data),
        }


def _build_graph_data(report: ImpactReport) -> dict[str, Any]:
    """Build a nodes+links dict for D3 force layout."""
    node_ids: set[str] = set()
    links: list[dict[str, str]] = []
    changed_set = {
        str(imp.change.file_path.stem)
        for imp in report.analysis.impacts
    }

    for impact in report.analysis.impacts:
        src = impact.change.file_path.stem
        node_ids.add(src)
        for mod in impact.affected_modules:
            node_ids.add(mod)
            links.append({"source": src, "target": mod})

    nodes = [
        {"id": n, "changed": n in changed_set}
        for n in sorted(node_ids)
    ]
    return {"nodes": nodes, "links": links}
