"""Auto chart generation (matplotlib, Agg backend — offline)."""

import base64
import io
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

STYLE = "seaborn-v0_8-whitegrid"
MAX_COLS_PER_CHART = 1  # one histogram per numeric column
TOP_CATS = 8  # bars per categorical chart


def _save_fig_b64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("ascii")


def _apply_style():
    try:
        plt.style.use(STYLE)
    except OSError:
        pass
    plt.rcParams["font.size"] = 9


def hist_png(series: pd.Series, title: str) -> str:
    _apply_style()
    fig, ax = plt.subplots(figsize=(6, 3.5))
    ax.hist(series.dropna(), bins=30, color="#4e79a7", edgecolor="white")
    ax.set_title(title)
    ax.set_ylabel("count")
    return _save_fig_b64(fig)


def bar_png(counts: pd.Series, title: str) -> str:
    _apply_style()
    fig, ax = plt.subplots(figsize=(6, 3.5))
    counts = counts.head(TOP_CATS)
    ax.bar([str(c) for c in counts.index], counts.values, color="#59a14f")
    ax.set_title(title)
    ax.tick_params(axis="x", rotation=25)
    return _save_fig_b64(fig)


def heatmap_png(df: pd.DataFrame) -> str | None:
    numeric = df.select_dtypes(include=[np.number])
    if numeric.shape[1] < 2:
        return None
    corr = numeric.corr(numeric_only=True)
    _apply_style()
    n = len(corr.columns)
    fig, ax = plt.subplots(figsize=(max(4.5, n * 1.1), max(3.5, n * 0.9)))
    im = ax.imshow(corr.values, cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(n), [str(c) for c in corr.columns], rotation=30, ha="right")
    ax.set_yticks(range(n), [str(c) for c in corr.columns])
    for i in range(n):
        for j in range(n):
            ax.text(
                j,
                i,
                f"{corr.values[i, j]:.2f}",
                ha="center",
                va="center",
                fontsize=8,
                color="white" if abs(corr.values[i, j]) > 0.5 else "black",
            )
    ax.set_title("Correlation heatmap")
    fig.colorbar(im, ax=ax, shrink=0.8)
    return _save_fig_b64(fig)


def build_charts(df: pd.DataFrame) -> dict:
    """Return {column: b64 png} histograms, {column: b64 png} bars, heatmap."""
    numeric = df.select_dtypes(include=[np.number])
    categorical = df.select_dtypes(exclude=[np.number])

    hists, bars = {}, {}
    for col in numeric.columns:
        if df[col].dropna().nunique() >= 2:
            hists[str(col)] = hist_png(df[col], f"Histogram — {col}")
    for col in categorical.columns:
        counts = df[col].value_counts(dropna=True)
        if not counts.empty:
            bars[str(col)] = bar_png(counts, f"Top values — {col}")

    return {"histograms": hists, "bars": bars, "heatmap": heatmap_png(df)}


def save_chart_files(charts: dict, out_dir: str) -> dict:
    """Also write PNGs to disk; return {kind: {col: filepath}} mapping."""
    os.makedirs(out_dir, exist_ok=True)
    saved = {"histograms": {}, "bars": {}, "heatmap": None}
    for kind in ("histograms", "bars"):
        for col, b64 in charts[kind].items():
            safe = "".join(c if c.isalnum() else "_" for c in col)
            fp = os.path.join(out_dir, f"{kind[:-1]}_{safe}.png")
            with open(fp, "wb") as f:
                f.write(base64.b64decode(b64))
            saved[kind][col] = fp
    if charts["heatmap"]:
        fp = os.path.join(out_dir, "heatmap_correlation.png")
        with open(fp, "wb") as f:
            f.write(base64.b64decode(charts["heatmap"]))
        saved["heatmap"] = fp
    return saved
