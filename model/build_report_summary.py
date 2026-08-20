"""Build the small, public aggregate used by the refreshed report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--orders-config", required=True)
    parser.add_argument("--revenue-config", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    frame = pd.read_csv(args.input)
    frame["date"] = pd.to_datetime(frame["date"])
    with open(args.orders_config, encoding="utf8") as handle:
        orders = json.load(handle)
    with open(args.revenue_config, encoding="utf8") as handle:
        revenue = json.load(handle)

    end = frame["date"].max()
    start = end - pd.Timedelta(days=364)
    frame = frame[frame["date"].between(start, end)].copy()
    geos = list(frame[orders["geo_column"]].drop_duplicates())
    views = {"Total": frame}
    views.update({geo: frame[frame[orders["geo_column"]].eq(geo)] for geo in geos})

    result = {
        "date_min": start.date().isoformat(),
        "date_max": end.date().isoformat(),
        "period_days": 365,
        "scenario_relative_change": orders["scenario"]["relative_change"],
        "views": {},
    }
    for view_name, subset in views.items():
        source = {}
        for channel, settings in orders["channels"].items():
            column = settings["column"]
            is_spend = column.startswith("spend_")
            source[channel] = {
                "spend": float(subset[column].sum()) if is_spend else None,
                "exposure": float(subset[column].sum()),
                "exposure_type": "spend" if is_spend else "delivered messages",
            }
        result["views"][view_name] = {
            "sources": source,
            "orders": {
                destination: float(subset[column].sum())
                for destination, column in orders["destinations"].items()
            },
            "revenue": {
                destination: float(subset[column].sum())
                for destination, column in revenue["destinations"].items()
            },
        }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf8")
    print(f"Wrote report summary to {output}")


if __name__ == "__main__":
    main()
