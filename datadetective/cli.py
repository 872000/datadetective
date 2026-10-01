"""Command-line interface for DataDetective."""

import argparse
import os
import sys

from datadetective import find_outliers, generate_report, profile_csv
from datadetective.core import load_csv

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def _sample(name: str) -> str:
    return os.path.join(DATA_DIR, name)


def cmd_profile(args):
    p = profile_csv(args.csv)
    print(f"File: {p['path']} — {p['n_rows']} rows × {p['n_cols']} columns")
    print(f"{'column':<20}{'dtype':<12}{'missing %':<10}{'cardinality'}")
    for c in p["dtypes"]:
        print(
            f"{c:<20}{p['dtypes'][c]:<12}{p['missing_pct'][c]:<10}{p['cardinality'][c]}"
        )
    df = load_csv(args.csv)
    out = find_outliers(df)
    total = sum(len({*o["iqr"], *o["zscore"]}) for o in out.values())
    print(f"\nOutliers flagged (IQR + z-score): {total}")
    for c, o in out.items():
        if o["top"]:
            t = o["top"][0]
            print(f"  {c}: {len({*o['iqr'], *o['zscore']})} "
                  f"(extreme: row {t['row']} = {t['value']})")


def cmd_report(args):
    path = generate_report(args.csv, args.out)
    print(f"Report written to {path}")


def cmd_demo(_args):
    for name in ("sales.csv", "customers.csv", "sensors.csv"):
        csv = _sample(name)
        out = os.path.join(os.getcwd(), f"demo_report_{name.replace('.csv', '.html')}")
        path = generate_report(csv, out)
        print(f"  {name} → {path}")
    print("Demo complete.")


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="datadetective", description="Automated EDA: CSV → HTML report."
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("profile", help="Print a data profile to the terminal.")
    p.add_argument("csv", help="Path to a CSV file.")
    p.set_defaults(func=cmd_profile)

    r = sub.add_parser("report", help="Write a self-contained HTML report.")
    r.add_argument("csv", help="Path to a CSV file.")
    r.add_argument("--out", default="report.html", help="Output HTML path.")
    r.set_defaults(func=cmd_report)

    d = sub.add_parser("demo", help="Run the full pipeline on bundled sample data.")
    d.set_defaults(func=cmd_demo)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    sys.exit(main())
