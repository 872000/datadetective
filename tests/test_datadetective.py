"""Tests for DataDetective. Run with: python3 -m pytest"""

import io
import os

import pandas as pd
import pytest

from datadetective import find_outliers, generate_report, profile_csv
from datadetective.core import load_csv

FIXTURE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


@pytest.fixture(scope="module", autouse=True)
def fixtures():
    os.makedirs(FIXTURE_DIR, exist_ok=True)
    # Fixture 1: missingness — 10 rows, 3 of 10 missing in 'a' => 30.0%
    pd.DataFrame(
        {
            "a": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, None, None, None],
            "b": list("xxyyxxyyxx"),
            "c": list(range(10)),
        }
    ).to_csv(os.path.join(FIXTURE_DIR, "missing.csv"), index=False)
    # Fixture 2: planted outlier — one extreme value at row 5
    pd.DataFrame(
        {"value": [10, 11, 10, 12, 11, 500, 10, 12, 11, 10, 11, 12, 10, 11]}
    ).to_csv(os.path.join(FIXTURE_DIR, "outlier.csv"), index=False)
    return FIXTURE_DIR


def test_missingness_pct_correct():
    path = os.path.join(FIXTURE_DIR, "missing.csv")
    p = profile_csv(path)
    assert p["missing_pct"]["a"] == 30.0
    assert p["missing_pct"]["b"] == 0.0
    assert p["n_rows"] == 10
    assert p["n_cols"] == 3


def test_cardinality_and_top_values():
    path = os.path.join(FIXTURE_DIR, "missing.csv")
    p = profile_csv(path)
    assert p["cardinality"]["b"] == 2
    assert p["top_values"]["b"]["x"] == 6


def test_iqr_flags_planted_outlier():
    path = os.path.join(FIXTURE_DIR, "outlier.csv")
    df = load_csv(path)
    out = find_outliers(df)
    assert "value" in out
    assert 5 in out["value"]["iqr"], f"planted outlier not flagged by IQR: {out}"
    top_rows = [t["row"] for t in out["value"]["top"]]
    assert 5 in top_rows


def test_zscore_flags_planted_outlier():
    path = os.path.join(FIXTURE_DIR, "outlier.csv")
    df = load_csv(path)
    out = find_outliers(df)
    assert 5 in out["value"]["zscore"]


def test_report_html_contains_expected_sections(tmp_path):
    csv = os.path.join(FIXTURE_DIR, "missing.csv")
    out = str(tmp_path / "report.html")
    path = generate_report(csv, out)
    html = open(path, encoding="utf-8").read()
    for section in (
        "Findings",
        "Overview",
        "Columns",
        "Numeric summaries",
        "Top categorical values",
        "Charts",
    ):
        assert section in html, f"missing section: {section}"
    assert "data:image/png;base64" in html  # inline chart images
    assert "Histogram" in html


def test_all_missing_numeric_column_skipped_in_numeric_summary():
    csv = os.path.join(FIXTURE_DIR, "allmissing.csv")
    pd.DataFrame({"a": [1, 2, 3], "b": [float("nan")] * 3}).to_csv(csv, index=False)
    p = profile_csv(csv)
    assert p["missing_pct"]["b"] == 100.0
    assert "b" not in p["numeric_summary"]
    import math

    for stats in p["numeric_summary"].values():
        for v in stats.values():
            assert not (isinstance(v, float) and math.isnan(v))
