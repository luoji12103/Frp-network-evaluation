"""HTML report exporter."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Template

from probes.common import RunResult


TEMPLATE = Template(
    """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{{ run.project }} report</title>
  <style>
    :root { color-scheme: light; }
    body { font-family: "Segoe UI", Arial, sans-serif; margin: 32px; background: #f5f7fb; color: #1f2937; }
    h1, h2 { margin-bottom: 8px; }
    .summary { background: white; border-radius: 12px; padding: 16px 20px; margin-bottom: 20px; box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08); }
    table { width: 100%; border-collapse: collapse; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08); }
    th, td { padding: 10px 12px; border-bottom: 1px solid #e5e7eb; text-align: left; vertical-align: top; }
    th { background: #e2e8f0; }
    .bad { color: #b91c1c; font-weight: 600; }
    .ok { color: #166534; font-weight: 600; }
    code { font-family: Consolas, monospace; }
  </style>
</head>
<body>
  <h1>{{ run.project }} report</h1>
  <div class="summary">
    <p><strong>Run ID:</strong> {{ run.run_id }}</p>
    <p><strong>Started:</strong> {{ run.started_at }}</p>
    <p><strong>Finished:</strong> {{ run.finished_at }}</p>
    <p><strong>Controller:</strong> {{ run.environment.platform }}</p>
  </div>

  <h2>Conclusion</h2>
  <div class="summary">
    <ul>
    {% for line in run.conclusion %}
      <li>{{ line }}</li>
    {% endfor %}
    </ul>
  </div>

  <h2>Threshold Findings</h2>
  <table>
    <thead>
      <tr>
        <th>Path</th>
        <th>Probe</th>
        <th>Metric</th>
        <th>Threshold</th>
        <th>Actual</th>
        <th>Message</th>
      </tr>
    </thead>
    <tbody>
    {% if run.threshold_findings %}
      {% for finding in run.threshold_findings %}
      <tr>
        <td>{{ finding.path_label }}</td>
        <td>{{ finding.probe_name }}</td>
        <td>{{ finding.metric }}</td>
        <td>{{ finding.threshold }}</td>
        <td class="bad">{{ finding.actual }}</td>
        <td>{{ finding.message }}</td>
      </tr>
      {% endfor %}
    {% else %}
      <tr><td colspan="6" class="ok">No threshold violations</td></tr>
    {% endif %}
    </tbody>
  </table>

  <h2>Probe Summary</h2>
  <table>
    <thead>
      <tr>
        <th>Path</th>
        <th>Probe</th>
        <th>Source</th>
        <th>Target</th>
        <th>Success</th>
        <th>Metrics</th>
        <th>Error</th>
      </tr>
    </thead>
    <tbody>
    {% for probe in run.probes %}
      <tr>
        <td>{{ probe.metadata.get("path_label", "unknown") }}</td>
        <td>{{ probe.name }}</td>
        <td>{{ probe.source }}</td>
        <td><code>{{ probe.target }}</code></td>
        <td class="{{ 'ok' if probe.success else 'bad' }}">{{ probe.success }}</td>
        <td>
        {% for key, value in probe.metrics.items() %}
          <div><strong>{{ key }}</strong>: {{ value }}</div>
        {% endfor %}
        </td>
        <td>{{ probe.error or '' }}</td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
</body>
</html>
"""
)


def export_html(run_result: RunResult, output_dir: str | Path) -> Path:
    """Write report.html for a run result."""
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / "report.html"
    target.write_text(TEMPLATE.render(run=run_result.to_dict()), encoding="utf-8")
    return target
