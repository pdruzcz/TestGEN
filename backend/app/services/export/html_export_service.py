"""Eksport HTML — Story 6.7, AC2.

Samodzielny (standalone) plik HTML: style inline w <style>, wykres severity
jako osadzone SVG z pattern fills (WCAG — wzorek dodatkowo do koloru),
bez zewnętrznych zasobów. Szablon Jinja2 z autoescape.
"""

from jinja2 import BaseLoader, Environment

from app.services.export.common import (
    REPORT_TYPE_PL,
    SEVERITY_ORDER,
    kpi_rows,
    severity_pl,
    source_pl,
)

SEVERITY_COLORS = {
    "critical": "#c62828",
    "high": "#ef6c00",
    "medium": "#f9a825",
    "low": "#2e7d32",
}

SEVERITY_PATTERNS = {
    "critical": "pat-stripes",
    "high": "pat-dots",
    "medium": "pat-hatch",
    "low": "pat-vertical",
}

_TEMPLATE = """<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="utf-8">
<title>{{ title }} — TestGEN</title>
<style>
body { font-family: "Segoe UI", Arial, sans-serif; color: #263238; margin: 0; background: #fafafa; }
.page { max-width: 960px; margin: 0 auto; padding: 24px 16px 48px; }
h1 { color: #1a237e; border-bottom: 2px solid #1565c0; padding-bottom: 8px; }
h2 { color: #1a237e; margin-top: 32px; }
.meta { color: #757575; font-size: 13px; }
table { border-collapse: collapse; width: 100%; background: #fff; }
th, td { border: 1px solid #e0e0e0; padding: 6px 10px; text-align: left; font-size: 13px; vertical-align: top; }
th { background: #f5f5f5; }
.card { background: #fff; border: 1px solid #e0e0e0; border-radius: 8px; padding: 16px; margin: 16px 0; }
.finding { border: 1px solid #e0e0e0; border-left-width: 5px; border-radius: 6px; padding: 10px 14px; margin: 12px 0; background: #fff; }
.badge { display: inline-block; font-size: 11px; font-weight: 700; padding: 2px 10px; border-radius: 10px; color: #fff; margin-right: 6px; }
.badge-meta { background: #eceff1; color: #37474f; font-weight: 400; }
pre { background: #263238; color: #eceff1; padding: 10px 12px; border-radius: 6px; overflow-x: auto; font-size: 12px; }
.recommendation { background: #e8f5e9; border-radius: 6px; padding: 8px 12px; font-size: 13px; }
ul.conclusions li { margin-bottom: 6px; line-height: 1.5; }
.legend { list-style: none; padding: 0; font-size: 13px; }
.legend li { margin-bottom: 4px; }
.legend svg { vertical-align: middle; margin-right: 6px; }
</style>
</head>
<body>
<div class="page">
<h1>{{ title }}</h1>
<p class="meta">Wygenerowano: {{ generated_at }} • Projekt: {{ project_id }} • TestGEN</p>

<h2>Kluczowe wskaźniki</h2>
<div class="card">
<table>
<tr><th>Wskaźnik</th><th>Wartość</th></tr>
{% for label, value in kpis %}<tr><td>{{ label }}</td><td>{{ value }}</td></tr>
{% endfor %}
</table>
</div>

<h2>Kluczowe wnioski</h2>
<div class="card">
<ul class="conclusions">
{% for c in conclusions %}<li>{{ c }}</li>
{% endfor %}
</ul>
</div>

{% if severity_bars %}
<h2>Rozkład problemów</h2>
<div class="card">
<svg width="520" height="{{ severity_bars|length * 34 }}" role="img" aria-label="Wykres słupkowy rozkładu problemów">
<defs>
<pattern id="pat-stripes" patternUnits="userSpaceOnUse" width="8" height="8" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="8" stroke="rgba(255,255,255,0.55)" stroke-width="3"/></pattern>
<pattern id="pat-dots" patternUnits="userSpaceOnUse" width="8" height="8"><circle cx="4" cy="4" r="1.8" fill="rgba(255,255,255,0.55)"/></pattern>
<pattern id="pat-hatch" patternUnits="userSpaceOnUse" width="8" height="8" patternTransform="rotate(-45)"><line x1="0" y1="0" x2="0" y2="8" stroke="rgba(255,255,255,0.55)" stroke-width="2"/></pattern>
<pattern id="pat-vertical" patternUnits="userSpaceOnUse" width="6" height="6"><line x1="3" y1="0" x2="3" y2="6" stroke="rgba(255,255,255,0.55)" stroke-width="2"/></pattern>
</defs>
{% for bar in severity_bars %}
<text x="0" y="{{ loop.index0 * 34 + 20 }}" font-size="12">{{ bar.label }}</text>
<rect x="110" y="{{ loop.index0 * 34 + 6 }}" width="{{ bar.width }}" height="20" rx="3" fill="{{ bar.color }}"/>
<rect x="110" y="{{ loop.index0 * 34 + 6 }}" width="{{ bar.width }}" height="20" rx="3" fill="url(#{{ bar.pattern }})"/>
<text x="{{ 116 + bar.width }}" y="{{ loop.index0 * 34 + 20 }}" font-size="12">{{ bar.count }}</text>
{% endfor %}
</svg>
</div>
{% endif %}

{% if modules %}
<h2>Zgodność według modułów</h2>
<div class="card">
<table>
<tr><th>Moduł (plik)</th><th>Zgodność [%]</th><th>Liczba problemów</th></tr>
{% for m in modules %}<tr><td>{{ m.file_path }}</td><td>{{ m.score }}</td><td>{{ m.total }}</td></tr>
{% endfor %}
</table>
</div>
{% endif %}

{% if include_findings %}
<h2>Szczegółowe ustalenia ({{ findings|length }})</h2>
{% for f in findings %}
<div class="finding" style="border-left-color: {{ f.color }}">
<p>
<span class="badge" style="background: {{ f.color }}{% if f.severity == 'medium' %}; color: #212121{% endif %}">{{ f.severity_label }}</span>
<span class="badge badge-meta">{{ f.source_label }}</span>
{% if f.cwe_id %}<span class="badge badge-meta">{{ f.cwe_id }}</span>{% endif %}
{% if f.cvss_score is not none %}<span class="badge badge-meta">CVSS {{ f.cvss_score }}</span>{% endif %}
</p>
<h3>{{ f.title }}</h3>
{% if f.description %}<p>{{ f.description }}</p>{% endif %}
{% if f.location %}<p class="meta">Powiązanie: <code>{{ f.location }}</code></p>{% endif %}
{% if f.code_snippet %}<pre>{{ f.code_snippet }}</pre>{% endif %}
{% if f.recommendation %}<p class="recommendation"><strong>Rekomendacja:</strong> {{ f.recommendation }}</p>{% endif %}
</div>
{% endfor %}
{% endif %}
</div>
</body>
</html>
"""

_env = Environment(loader=BaseLoader(), autoescape=True)
_template = _env.from_string(_TEMPLATE)


def render(report: dict, report_type: str = "both") -> bytes:
    counts = report.get("severity_counts") or {}
    max_count = max([counts.get(s, 0) for s in SEVERITY_ORDER] + [1])
    severity_bars = [
        {
            "label": severity_pl(sev),
            "count": counts.get(sev, 0),
            "width": max(2, round((counts.get(sev, 0) / max_count) * 340)),
            "color": SEVERITY_COLORS[sev],
            "pattern": SEVERITY_PATTERNS[sev],
        }
        for sev in SEVERITY_ORDER
        if counts.get(sev, 0) > 0
    ]

    findings = []
    for f in report.get("findings") or []:
        severity = (f.get("severity") or "low").lower()
        location = None
        if f.get("file_path"):
            location = f["file_path"]
            if f.get("line_start"):
                location = f"{location}:{f['line_start']}"
        findings.append(
            {
                "severity": severity,
                "severity_label": severity_pl(severity),
                "source_label": source_pl(f.get("source")),
                "color": SEVERITY_COLORS.get(severity, "#2e7d32"),
                "title": f.get("title") or "",
                "description": f.get("description") or "",
                "cwe_id": f.get("cwe_id"),
                "cvss_score": f.get("cvss_score"),
                "location": location,
                "code_snippet": f.get("code_snippet"),
                "recommendation": f.get("recommendation"),
            }
        )

    modules = [
        {
            "file_path": m.get("file_path") or "",
            "score": round(m.get("score") or 0),
            "total": m.get("total_findings", 0),
        }
        for m in report.get("module_scores") or []
    ]

    html = _template.render(
        title=REPORT_TYPE_PL.get(report_type, REPORT_TYPE_PL["both"]),
        project_id=report.get("project_id") or "",
        generated_at=report.get("generated_at") or "",
        kpis=kpi_rows(report),
        conclusions=report.get("conclusions") or [],
        severity_bars=severity_bars,
        modules=modules,
        findings=findings,
        include_findings=report_type in ("technical", "both"),
    )
    return html.encode("utf-8")
