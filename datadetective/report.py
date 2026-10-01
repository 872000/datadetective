"""Self-contained HTML report builder (inline base64 images)."""

import html
import os
from datetime import datetime

from datadetective.charts import build_charts
from datadetective.core import find_outliers, load_csv, profile_csv

CSS = """
body{font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
max-width:1000px;margin:0 auto;padding:24px;color:#1f2937;background:#f9fafb}
.card{background:#fff;border:1px solid #e5e7eb;border-radius:10px;
padding:18px;margin:16px 0;box-shadow:0 1px 2px rgba(0,0,0,.04)}
h1{color:#111827}h2{color:#1d4ed8;border-bottom:2px solid #dbeafe;padding-bottom:6px}
table{border-collapse:collapse;width:100%;font-size:14px}
th,td{border:1px solid #e5e7eb;padding:6px 10px;text-align:left}
th{background:#eff6ff}.badge{display:inline-block;padding:2px 10px;border-radius:999px;
font-size:12px;background:#dbeafe;color:#1e40af;margin-right:6px}
.warn{background:#fef3c7;color:#92400e}.ok{background:#d1fae5;color:#065f46}
img.chart{max-width:100%;border:1px solid #e5e7eb;border-radius:8px;margin:10px 0}
ul.findings li{margin:6px 0}.footer{color:#6b7280;font-size:12px;margin-top:24px}
"""


def _esc(v) -> str:
    return html.escape(str(v))


def generate_findings(profile: dict, outliers: dict) -> list[str]:
    """Plain-English summary of the most interesting facts."""
    findings = []
    n_rows, n_cols = profile["n_rows"], profile["n_cols"]
    findings.append(
        f"The dataset has {n_rows:,} rows and {n_cols} columns, "
        f"using about {profile['memory_kb']} KB in memory."
    )
    worst = sorted(
        profile["missing_pct"].items(), key=lambda kv: kv[1], reverse=True
    )
    if worst and worst[0][1] > 0:
        findings.append(
            "Missing values: " + ", ".join(
                f"{c} ({p:.1f}%)" for c, p in worst if p > 0
            )
            + ". Consider imputation or dropping before modelling."
        )
    else:
        findings.append("No missing values were found.")
    const_cols = [c for c, k in profile["cardinality"].items() if k == 1]
    if const_cols:
        findings.append(
            f"Constant column(s) {', '.join(const_cols)} carry no "
            "information and can usually be dropped."
        )
    for col, o in outliers.items():
        n = len({*o["iqr"], *o["zscore"]})
        if n:
            both = o["top"][0]["methods"] if o["top"] else []
            findings.append(
                f"Column '{col}' has {n} flagged outlier(s) "
                f"({o['n_iqr']} by IQR, {o['n_zscore']} by z-score). "
                + (
                    f"Most extreme: row {o['top'][0]['row']} = "
                    f"{o['top'][0]['value']} ({'/'.join(both)})."
                    if o["top"]
                    else ""
                )
            )
    n_num = len(profile["numeric_summary"])
    findings.append(
        f"{n_num} numeric column(s) were profiled with full distribution "
        "summaries and histograms."
    )
    return findings


def generate_report(csv_path: str, out_path: str) -> str:
    """Profile a CSV, detect outliers, chart it, and write an HTML report.

    Returns the absolute path of the written report.
    """
    df = load_csv(csv_path)
    profile = profile_csv(csv_path)
    outliers = find_outliers(df)
    charts = build_charts(df)
    findings = generate_findings(profile, outliers)

    def row(cells, header=False):
        tag = "th" if header else "td"
        return "<tr>" + "".join(f"<{tag}>{_esc(c)}</{tag}>" for c in cells) + "</tr>"

    sections = []
    sections.append(
        "<div class='card'><h2>Findings</h2><ul class='findings'>"
        + "".join(f"<li>{_esc(f)}</li>" for f in findings)
        + "</ul></div>"
    )

    meta = (
        f"<span class='badge'>{profile['n_rows']} rows</span>"
        f"<span class='badge'>{profile['n_cols']} columns</span>"
        f"<span class='badge'>{profile['memory_kb']} KB</span>"
    )
    sections.append(f"<div class='card'><h2>Overview</h2>{meta}</div>")

    col_table = row(["column", "dtype", "missing %", "cardinality"], header=True)
    for c in profile["dtypes"]:
        miss = profile["missing_pct"][c]
        cls = "warn" if miss > 10 else ("ok" if miss == 0 else "")
        col_table += (
            "<tr><td>" + _esc(c) + "</td><td>" + _esc(profile["dtypes"][c])
            + f"</td><td><span class='badge {cls}'>{miss}%</span></td>"
            + f"<td>{profile['cardinality'][c]}</td></tr>"
        )
    sections.append(f"<div class='card'><h2>Columns</h2><table>{col_table}</table></div>")

    if profile["numeric_summary"]:
        num_table = row(
            ["column", "mean", "std", "min", "25%", "median", "75%", "max"],
            header=True,
        )
        for c, s in profile["numeric_summary"].items():
            num_table += row(
                [c, s["mean"], s["std"], s["min"], s["q25"], s["median"], s["q75"], s["max"]]
            )
        sections.append(
            f"<div class='card'><h2>Numeric summaries</h2><table>{num_table}</table></div>"
        )

    if profile["top_values"]:
        tv = ""
        for c, vals in profile["top_values"].items():
            tv += f"<h3>{_esc(c)}</h3><table>" + row(["value", "count"], header=True)
            tv += "".join(row([k, v]) for k, v in vals.items()) + "</table>"
        sections.append(f"<div class='card'><h2>Top categorical values</h2>{tv}</div>")

    if outliers:
        osec = ""
        for c, o in outliers.items():
            if o["top"]:
                osec += f"<h3>{_esc(c)}</h3><table>" + row(
                    ["row", "value", "flagged by"], header=True
                )
                osec += "".join(
                    row([t["row"], t["value"], "/".join(t["methods"])])
                    for t in o["top"]
                ) + "</table>"
        if osec:
            sections.append(
                f"<div class='card'><h2>Outliers (IQR + z-score)</h2>{osec}</div>"
            )

    csec = ""
    for c, img in charts["histograms"].items():
        csec += (f"<h3>Histogram — {_esc(c)}</h3>"
                 f"<img class='chart' src='data:image/png;base64,{img}'/>")
    for c, img in charts["bars"].items():
        csec += (f"<h3>Top values — {_esc(c)}</h3>"
                 f"<img class='chart' src='data:image/png;base64,{img}'/>")
    if charts["heatmap"]:
        csec += (
            "<h3>Correlation</h3>"
            f"<img class='chart' src='data:image/png;base64,{charts['heatmap']}'/>"
        )
    sections.append(f"<div class='card'><h2>Charts</h2>{csec}</div>")

    html_doc = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>DataDetective report — {_esc(os.path.basename(csv_path))}</title>
<style>{CSS}</style></head>
<body>
<h1>🔍 DataDetective report</h1>
<p>Source: <code>{_esc(csv_path)}</code> · generated {datetime.now():%Y-%m-%d %H:%M}</p>
{''.join(sections)}
<p class="footer">Generated offline by DataDetective {_esc(__import__('datadetective').__version__)}</p>
</body></html>"""

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_doc)
    return os.path.abspath(out_path)
