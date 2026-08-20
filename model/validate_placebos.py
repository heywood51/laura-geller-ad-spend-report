"""Compare the observed halo matrix with time-shifted placebo matrices."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from halo_model import build_halo


def matrix_scores(model: dict) -> dict[str, float]:
    view = model["views"]["Total"]
    effects = np.array([cell["effect"] for cell in view["cells"].values()], dtype=float)
    row_totals = np.array(list(view["row_totals"].values()), dtype=float)
    return {
        "absolute_cell_volume": float(np.abs(effects).sum()),
        "net_cell_volume": float(effects.sum()),
        "absolute_row_volume": float(np.abs(row_totals).sum()),
        "net_row_volume": float(row_totals.sum()),
    }


def shifted_panel(frame: pd.DataFrame, config: dict, rng: np.random.Generator) -> tuple[pd.DataFrame, dict[str, int]]:
    result = frame.copy()
    date_column = config["date_column"]
    geo_column = config["geo_column"]
    dates = np.array(sorted(result[date_column].unique()))
    offsets: dict[str, int] = {}
    for channel, settings in config["channels"].items():
        offset = int(rng.integers(45, max(46, len(dates) - 45)))
        offsets[channel] = offset
        for geo in result[geo_column].unique():
            mask = result[geo_column].eq(geo)
            ordered = result.loc[mask].sort_values(date_column)
            values = ordered[settings["column"]].to_numpy(float)
            result.loc[ordered.index, settings["column"]] = np.roll(values, offset)
    return result, offsets


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--runs", type=int, default=8)
    parser.add_argument("--seed", type=int, default=20260820)
    args = parser.parse_args()

    frame = pd.read_csv(args.input)
    with open(args.config, encoding="utf8") as handle:
        config = json.load(handle)
    rng = np.random.default_rng(args.seed)
    observed_model = build_halo(frame, config)
    observed = matrix_scores(observed_model)
    placebos = []
    for run in range(args.runs):
        shifted, offsets = shifted_panel(frame, config, rng)
        scores = matrix_scores(build_halo(shifted, config))
        scores["run"] = run + 1
        scores["offsets"] = offsets
        placebos.append(scores)

    absolute = np.array([item["absolute_cell_volume"] for item in placebos])
    net = np.array([abs(item["net_cell_volume"]) for item in placebos])
    result = {
        "observed": observed,
        "placebos": placebos,
        "summary": {
            "placebo_absolute_cell_median": float(np.median(absolute)),
            "placebo_absolute_cell_max": float(np.max(absolute)),
            "observed_to_placebo_absolute_median": float(observed["absolute_cell_volume"] / np.median(absolute)),
            "placebo_abs_net_median": float(np.median(net)),
            "observed_to_placebo_abs_net_median": float(abs(observed["net_cell_volume"]) / max(np.median(net), 1e-9)),
        },
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf8")
    print(json.dumps(result["summary"], indent=2))


if __name__ == "__main__":
    main()
