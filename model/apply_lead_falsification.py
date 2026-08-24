"""Apply directed future-exposure falsification to an adjusted halo model."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from validate_placebos import (
    apply_lead_falsification,
    build_lead_falsification,
    parse_lead_days,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Geo-time panel CSV")
    parser.add_argument("--config", required=True)
    parser.add_argument("--adjusted-input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--lead-days", type=parse_lead_days, default=(1, 2, 3, 7, 14))
    parser.add_argument("--total-business", action="store_true")
    args = parser.parse_args()

    frame = pd.read_csv(args.input)
    with open(args.config, encoding="utf8") as handle:
        config = json.load(handle)
    if args.total_business:
        from build_incrementality import build_total_config

        frame, config = build_total_config(frame, config)
    with open(args.adjusted_input, encoding="utf8") as handle:
        adjusted = json.load(handle)

    reference, lead_models = build_lead_falsification(frame, config, args.lead_days)
    result = apply_lead_falsification(adjusted, reference, lead_models, args.lead_days)
    Path(args.output).write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf8")
    total = result["views"]["Total"]["cells"].values()
    print(json.dumps({
        "lead_days": list(args.lead_days),
        "passed_lead_falsification": sum(cell["passes_lead_falsification"] for cell in total),
        "passed_all_validation": sum(cell["passes_validation"] for cell in total),
        "tested": len(result["views"]["Total"]["cells"]),
    }, indent=2))


if __name__ == "__main__":
    main()
