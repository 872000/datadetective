"""DataDetective — automated exploratory data analysis.

Point at any CSV and get a data profile, outlier flags, auto charts,
and a self-contained HTML report. Everything runs offline.
"""

__version__ = "1.0.0"
__all__ = ["profile_csv", "find_outliers", "generate_report"]

from datadetective.core import profile_csv, find_outliers
from datadetective.report import generate_report
