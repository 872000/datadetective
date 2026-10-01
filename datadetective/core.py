"""Data profiling and outlier detection (pandas + numpy)."""

import numpy as np
import pandas as pd

MISSING_SENTINELS = {"", "NA", "N/A", "null", "NULL", "None", "-", "?"}


def load_csv(path: str) -> pd.DataFrame:
    """Load a CSV, treating common placeholders as missing values."""
    return pd.read_csv(path, na_values=sorted(MISSING_SENTINELS - {""}))


def profile_csv(path: str) -> dict:
    """Build a data profile for a CSV file.

    Returns a dict with: path, shape, dtypes, missing_pct, cardinality,
    numeric_summary, top_values (categoricals), memory_kb.
    """
    df = load_csv(path)
    n_rows, n_cols = df.shape

    dtypes = {col: str(df[col].dtype) for col in df.columns}
    missing_pct = {
        col: round(df[col].isna().mean() * 100, 2) for col in df.columns
    }
    cardinality = {col: int(df[col].nunique(dropna=True)) for col in df.columns}

    numeric = df.select_dtypes(include=[np.number])
    numeric_summary = {}
    for col in numeric.columns:
        desc = numeric[col].describe()
        numeric_summary[col] = {
            "count": int(desc["count"]),
            "mean": round(float(desc["mean"]), 4),
            "std": round(float(desc["std"]), 4),
            "min": round(float(desc["min"]), 4),
            "q25": round(float(desc["25%"]), 4),
            "median": round(float(desc["50%"]), 4),
            "q75": round(float(desc["75%"]), 4),
            "max": round(float(desc["max"]), 4),
        }

    top_values = {}
    categorical = df.select_dtypes(exclude=[np.number])
    for col in categorical.columns:
        vc = df[col].value_counts(dropna=True).head(5)
        top_values[col] = {str(k): int(v) for k, v in vc.items()}

    return {
        "path": path,
        "n_rows": int(n_rows),
        "n_cols": int(n_cols),
        "dtypes": dtypes,
        "missing_pct": missing_pct,
        "cardinality": cardinality,
        "numeric_summary": numeric_summary,
        "top_values": top_values,
        "memory_kb": round(df.memory_usage(deep=True).sum() / 1024, 1),
    }


def find_outliers(df: pd.DataFrame, top_n: int = 10) -> dict:
    """Flag outliers per numeric column using IQR and z-score methods.

    Returns {column: {"iqr": [...row indices...], "zscore": [...],
                       "top": [{"row": i, "value": v, "methods": [...]}]}}
    """
    results = {}
    numeric = df.select_dtypes(include=[np.number])
    for col in numeric.columns:
        series = numeric[col].dropna()
        if series.empty or series.nunique() < 2:
            continue

        q1 = series.quantile(0.25)
        q3 = series.quantile(0.75)
        iqr = q3 - q1
        lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        iqr_mask = (series < lower) | (series > upper)

        mean, std = series.mean(), series.std()
        z = (series - mean) / std if std else pd.Series(0, index=series.index)
        zscore_mask = z.abs() > 3

        iqr_idx = sorted(iqr_mask[iqr_mask].index.tolist())
        z_idx = sorted(zscore_mask[zscore_mask].index.tolist())

        flagged = sorted(set(iqr_idx) | set(z_idx))
        severity = {
            i: (abs(z.loc[i]) if i in z.index else 0.0) for i in flagged
        }
        flagged.sort(key=lambda i: severity[i], reverse=True)
        top = [
            {
                "row": int(i),
                "value": round(float(series.loc[i]), 4),
                "methods": [
                    m
                    for m, idxs in (("IQR", iqr_idx), ("z-score", z_idx))
                    if i in idxs
                ],
            }
            for i in flagged[:top_n]
        ]

        results[str(col)] = {
            "iqr": iqr_idx,
            "zscore": z_idx,
            "n_iqr": len(iqr_idx),
            "n_zscore": len(z_idx),
            "top": top,
        }
    return results
